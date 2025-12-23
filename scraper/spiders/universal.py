import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy import FormRequest
from scrapy.exceptions import CloseSpider
import yaml
import urllib.parse
import json
import re
import html
import os
from .utils import extract_links, get_browser_headers, get_md5


class UniversalSpider(scrapy.Spider):
    name = "universal_spider"

    def __init__(self, site_cfg, keyword, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.site_cfg = site_cfg
        self.keyword = keyword
        # 从site_cfg中获取task_id
        self.task_id = site_cfg.get('task_id')
        self.context = {"host": site_cfg.get('host'), "keyword": keyword}
        self.base_headers = get_browser_headers(site_cfg.get('host'))

        # 指纹去重集合与错误统计
        self.seen_resources = set()
        self.error_count = 0
        self.max_errors = 10  # 连续错误熔断阈值

    def start_requests(self):
        workflow = self.site_cfg.get('workflow', [])
        if workflow:
            yield from self.run_workflow_step(0)
        else:
            yield from self.execute_search()

    def run_workflow_step(self, index):
        step = self.site_cfg['workflow'][index]
        url = self.render_template(step['url'])
        self.logger.info(f"🔄 工作流步骤 {index + 1}: {url}")

        meta = {'handle_httpstatus_list': [403, 429]}
        yield scrapy.Request(
            url,
            headers=self.base_headers,
            callback=self.parse_workflow,
            meta=meta,
            cb_kwargs={'step_index': index},
            dont_filter=True
        )

    def parse_workflow(self, response, step_index):
        if response.status in [403, 429]:
            self.logger.warning(f"⚠️ 工作流受限 ({response.status})，站点: {self.site_cfg['name']}")
            return

        step = self.site_cfg['workflow'][step_index]
        for var_name, rule in step.get('extract', {}).items():
            val = None
            if rule.startswith('xpath:'):
                val = response.xpath(rule[6:]).get()
            elif rule.startswith('regex:'):
                match = re.search(rule[6:], response.text)
                val = match.group(1) if match else None
            if val: self.context[var_name] = val

        if step_index + 1 < len(self.site_cfg['workflow']):
            yield from self.run_workflow_step(step_index + 1)
        else:
            yield from self.execute_search()

    def execute_search(self):
        cfg = self.site_cfg
        url = self.render_template(cfg['start_url'])
        method = cfg.get('method', 'GET').upper()

        meta = {'handle_httpstatus_list': [403, 422, 429]}
        if cfg.get('handle_redirect'):
            meta['handle_redirect'] = True

        headers = self.base_headers.copy()
        if 'headers' in cfg:
            headers.update(cfg['headers'])

        if method == 'POST':
            raw_payload = cfg.get('payload', {}).copy()
            processed_payload = {}
            for k, v in raw_payload.items():
                processed_payload[k] = self.render_template(v) if isinstance(v, str) else v

            processed_payload[cfg.get('kw_field', 'keyboard')] = self.keyword

            if headers.get('Content-Type') == 'application/json':
                yield scrapy.Request(url, method='POST', body=json.dumps(processed_payload),
                                     headers=headers, callback=self.parse_result, meta=meta)
            else:
                yield FormRequest(url, formdata=processed_payload, headers=headers,
                                  callback=self.parse_result, meta=meta)
        else:
            yield scrapy.Request(url, headers=headers, callback=self.parse_result, meta=meta)

    def parse_result(self, response):
        cfg = self.site_cfg
        has_detail = cfg.get('has_detail', True)

        if response.status in [403, 422, 429]:
            self.error_count += 1
            if self.error_count >= self.max_errors:
                raise CloseSpider(f"站点 {cfg['name']} 连续报错，触发自动熔断")
            return

        self.error_count = 0
        mode = cfg.get('parse_mode', 'html')
        detail_meta = {'handle_httpstatus_list': [403], 'referer_url': response.url}

        if mode == 'json':
            try:
                data = json.loads(response.text)
                items_path = cfg.get('json_items_path', 'data')
                items = data
                for key in items_path.split('.'):
                    if isinstance(items, dict): items = items.get(key, [])

                if not isinstance(items, list): items = [items]

                for item in items:
                    title = self.get_json_value(item, cfg.get('json_title_path', 'name'))
                    # DEBUG模式下查看跳过的标题
                    if not title or (self.keyword and self.keyword.lower() not in str(title).lower()):
                        self.logger.debug(f"跳过标题: {title}")
                        continue

                    if not has_detail:
                        # 首先检查item中是否直接包含url字段
                        if 'url' in item:
                            links = item['url']
                        else:
                            item_str = json.dumps(item, ensure_ascii=False)
                            links, disks = extract_links(item_str)
                            if not links:
                                continue
                        # 调用extract_links确保能识别网盘类型并格式化链接
                        formatted_links, disks = extract_links(links)
                        if formatted_links:
                            yield from self.finalize_item_safe(title, formatted_links, response.url, disks)
                    else:
                        id_val = item.get('id') or item.get('slug') or item.get('uuid')
                        if id_val:
                            detail_url = f"https://{cfg.get('host')}/d/{id_val}"
                            headers = self.base_headers.copy()
                            headers['Referer'] = response.url
                            yield scrapy.Request(detail_url, headers=headers, callback=self.parse_detail,
                                                 meta=detail_meta, dont_filter=True)
            except Exception as e:
                self.logger.error(f"JSON 解析失败: {e}")

        elif mode == 'regex_json':
            match = re.search(cfg['extract_regex'], response.text)
            if match:
                try:
                    data = json.loads(match.group(1).replace('\\/', '/'))
                    for item in data:
                        title = item.get(cfg.get('json_title', 'title'))
                        if not has_detail:
                            links, disks = extract_links(json.dumps(item))
                            yield from self.finalize_item_safe(title, links, response.url, disks)
                        else:
                            url_val = item.get(cfg.get('json_url', 'url'))
                            if url_val:
                                full_url = response.urljoin(url_val)
                                yield scrapy.Request(full_url, callback=self.parse_detail, meta=detail_meta,
                                                     dont_filter=True)
                except:
                    pass
        else:
            rules = cfg.get('list_rules', {})
            for node in response.xpath(rules.get('item_nodes', '')):
                title = node.xpath(rules.get('title_node', './/text()')).get()
                if not title: continue

                if not has_detail:
                    links, disks = extract_links(node.get())
                    if links:
                        yield from self.finalize_item_safe(title, links, response.url, disks)
                else:
                    link = node.xpath(rules.get('detail_link', '')).get()
                    if link:
                        full_url = response.urljoin(link)
                        headers = self.base_headers.copy()
                        headers['Referer'] = response.url
                        yield scrapy.Request(full_url, headers=headers, callback=self.parse_detail, meta=detail_meta,
                                             dont_filter=True)

    def parse_detail(self, response):
        if response.status == 403: return
        fields = self.site_cfg.get('detail_rules', {}).get('fields', {})
        title_raw = response.xpath(fields.get('title', '//title/text()')).getall()
        title = "".join(title_raw).strip()
        links, disks = extract_links(response.text)
        if links:
            yield from self.finalize_item_safe(title, links, response.url, disks)

    def finalize_item_safe(self, title, links, source_url, disks=None):
        # 1. 清洗标题
        clean_title = html.unescape(re.sub(r'<[^>]+>', '', str(title or "无标题"))).strip()

        # 2. 链接清洗并去重（保持为列表）
        if isinstance(links, str):
            raw_list = [l.strip() for l in links.split(',') if l.strip()]
        else:
            raw_list = [str(l).strip() for l in links if str(l).strip()]
        
        unique_links = list(dict.fromkeys(raw_list))

        # 3. 遍历链接，每一条链接 yield 一个独立的 item
        for link in unique_links:
            fingerprint = get_md5(link)
            if fingerprint in self.seen_resources:
                continue
            self.seen_resources.add(fingerprint)

            # 重新识别单条链接的网盘类型（如果需要的话）
            # 这样每一条数据都能准确对应它的网盘类型
            from .utils import extract_links as re_extract
            _, single_disk = re_extract(link)

            self.logger.info(f"✨ 发现资源: {clean_title[:20]}... | 链接: {link[:30]}...")
            
            yield {
                'site_name': str(self.site_cfg.get('name')),
                'title': clean_title,
                'disk_type': str(single_disk or "未知"),
                'resource_url': link,  # 现在这里只有一个单独的 URL
                'source_url': str(source_url)
            }

    def get_json_value(self, obj, path):
        if not path: return None
        try:
            for key in path.split('.'):
                if isinstance(obj, dict):
                    obj = obj.get(key)
                elif isinstance(obj, list) and key.isdigit():
                    obj = obj[int(key)]
                else:
                    return None
            return obj
        except:
            return None

    def render_template(self, text):
        for k, v in self.context.items():
            val = urllib.parse.quote(str(v)) if k == "keyword" else str(v)
            text = text.replace(f"{{{k}}}", val)
        return text


def run():
    with open('sites.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    print("--- 资源采集引擎 v6.2 (Per-Site Settings Mode) ---")
    target = input("输入站点 key (输入 'all' 运行全部): ").strip()
    kw = input("搜索词: ").strip()

    output_file = 'out.jsonl'
    if os.path.exists(output_file):
        os.remove(output_file)

    # 1. 这里只放【真正的全局基础配置】
    process = CrawlerProcess(settings={
        'LOG_LEVEL': 'INFO',
        'FEEDS': {
            output_file: {
                'format': 'jsonlines',
                'overwrite': True,
                'encoding': 'utf8'
            }
        },
        'COOKIES_ENABLED': True,
        'AUTOTHROTTLE_ENABLED': True,  # 开启自动限速，配合自定义延迟
        'AUTOTHROTTLE_START_DELAY': 1.0,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'DOWNLOAD_TIMEOUT': 20,
    })

    def _crawl_site(site_key, site_cfg):
        # 2. 关键点：为每个站点动态构建个性化设置
        # 这些设置会覆盖上面的全局设置
        site_specific_settings = {
            # 如果 YAML 没写，则给个默认值
            'CONCURRENT_REQUESTS_PER_DOMAIN': site_cfg.get('concurrent', 4),
            'DOWNLOAD_DELAY': site_cfg.get('delay', 1.0),
        }

        # 3. 将设置注入到 crawl 方法中
        process.crawl(
            UniversalSpider,
            site_cfg=site_cfg,
            keyword=kw,
            # 通过 settings 参数传递，Scrapy 会自动应用
            settings=site_specific_settings
        )

    if target.lower() == 'all':
        for s_key, s_cfg in config['sites'].items():
            _crawl_site(s_key, s_cfg)
    elif target in config['sites']:
        _crawl_site(target, config['sites'][target])
    else:
        print("站点不存在！")
        return

    process.start()


if __name__ == "__main__":
    run()