import re
import random
import yaml
import os
import base64
import hashlib

_NETDISK_RULES = []


def load_rules():
    global _NETDISK_RULES
    if not _NETDISK_RULES:
        # 使用正确的路径计算
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(BASE_DIR, 'config', 'rules.yaml')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                _NETDISK_RULES = config.get('netdisk_rules', [])
        else:
            _NETDISK_RULES = []
    return _NETDISK_RULES


def match_netdisk_link(link: str) -> str:
    link_lower = link.strip().lower()
    rules = load_rules()
    for rule in rules:
        if re.search(rule['pattern'], link_lower, re.IGNORECASE):
            return rule['name']
    return "其他"


def extract_links(text: str):
    # 增加对转义字符的处理
    text = text.replace('\\/', '/')

    # 匹配标准 URL 及 常见网盘特征
    universal_pattern = r'(https?://[^\s\"\'><]+|magnet:\?xt=urn:btih:[a-zA-Z0-9]+|thunder://[A-Za-z0-9+/=]+|ed2k://[^\s\"\'><]+)'
    raw_links = re.findall(universal_pattern, text)

    # 尝试在文本中寻找可能的 Base64 编码 (针对部分防爬站点)
    # 仅处理长度大于 20 且看起来像 Base64 的字符串
    potential_b64 = re.findall(r'[A-Za-z0-9+/]{40,}=*', text)
    for b in potential_b64:
        try:
            decoded = base64.b64decode(b).decode('utf-8', errors='ignore')
            if "http" in decoded or "magnet" in decoded:
                raw_links.extend(re.findall(universal_pattern, decoded))
        except:
            continue

    clean_results = []
    disk_types = set()
    for link in raw_links:
        link = link.rstrip('.,;)!?')
        disk_name = match_netdisk_link(link)
        if disk_name != "其他" and link not in clean_results:
            clean_results.append(link)
            disk_types.add(disk_name)

    return ", ".join(clean_results), "/".join(disk_types)


def get_browser_headers(host=None):
    v = random.choice(["120", "121", "122"])
    ua = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36"
    headers = {
        'User-Agent': ua,
        'Sec-Ch-Ua': f'"Not_A Brand";v="8", "Chromium";v="{v}", "Google Chrome";v="{v}"',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Upgrade-Insecure-Requests': '1',
    }
    if host:
        headers['Host'] = host
        headers['Referer'] = f"https://{host}/"
    return headers


def get_md5(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()