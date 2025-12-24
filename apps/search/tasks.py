import os
import logging
import sys
import subprocess
from datetime import timedelta
from scraper.celery import app
from apps.search.models import SearchTask, SiteConfig
from apps.search.config_utils import get_result_expire_hours, get_email_config, get_crawl_timeout_seconds
import django
from django.db import close_old_connections
from django.utils import timezone

# 设置日志记录器
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 配置Scrapy日志
scrapy_logger = logging.getLogger('scrapy')
scrapy_logger.setLevel(logging.DEBUG)

# 确保Django环境已初始化
def ensure_django_initialized():
    if not hasattr(django, 'apps') or not django.apps.apps.ready:
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scraper.settings")
        django.setup()
        logger.info("Django环境已初始化")


@app.task(bind=True, max_retries=5, default_retry_delay=60)
def send_email_task(self, task_id):
    try:
        ensure_django_initialized()
        close_old_connections()

        from django.conf import settings
        from django.core.mail import EmailMultiAlternatives

        task = SearchTask.objects.filter(task_id=task_id).first()
        if not task or not task.email:
            return str(task_id)

        if not getattr(task, 'notify_email', True):
            logger.info(f"用户选择不发送邮件: {task.email}, task_id={task_id}")
            return str(task_id)

        # 处理时间显示：直接使用本地时间（北京时间）
        # USE_TZ=False 时，时间已经是本地时间，直接格式化
        submit_time = task.created_at.strftime('%Y-%m-%d %H:%M:%S')
        
        expire_time_str = ''
        if task.expire_time:
            expire_time_str = task.expire_time.strftime('%Y-%m-%d %H:%M:%S')
        
        send_time = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        email_cfg = get_email_config()
        result_url = f"{email_cfg['site_base_url']}/result?related_task_id={task.related_task_id.hex}"

        expire_hours = get_result_expire_hours()
        text_content = (
            "你好！\n"
            f"你于 {submit_time} 在 Crawl-Res 提交的搜索词 {task.keyword} 已完成检索，本次搜索结果如下：\n"
            f"查看搜索结果：{result_url}\n"
            "\n重要提示\n"
            f"1. 结果链接有效期为{expire_hours}小时，请在 {expire_time_str} 前访问查看，超时后链接将自动失效。\n"
            "2. 若链接无法打开，请检查网络状态或确认 task_id 是否正确。\n"
            "\n版权声明\n"
            "本项目是 GitHub 开源项目 Crawl-Res，旨在为用户提供公开网络资源的检索指引服务。\n"
            "本项目检索的所有资源均来源于公开网络，Crawl-Res 未存储、上传、篡改任何资源文件，也不对资源的合法性、真实性、完整性承担任何法律责任。\n"
            f"\nCrawl-Res 开源项目组\n{send_time}\n"
        )

        html_content = f"""<!doctype html>
<html lang=\"zh-CN\">
<body style=\"margin:0;padding:0;background:#f6f7fb;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,Microsoft YaHei,sans-serif;\">
  <div style=\"max-width:680px;margin:0 auto;padding:24px;\">
    <div style=\"background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;\">
      <div style=\"padding:20px 24px;background:#0f172a;color:#ffffff;\">
        <div style=\"font-size:18px;font-weight:700;\">Crawl-Res 检索完成通知</div>
      </div>
      <div style=\"padding:24px;color:#111827;line-height:1.7;\">
        <p style=\"margin:0 0 12px;\">你好！</p>
        <p style=\"margin:0 0 12px;\">你于 <strong>{submit_time}</strong> 在 Crawl-Res 提交的搜索词 <strong>{task.keyword}</strong> 已完成检索，本次搜索结果如下：</p>
        <p style=\"margin:18px 0;\">
          <a href=\"{result_url}\" target=\"_blank\" rel=\"noopener noreferrer\" style=\"display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;padding:10px 16px;border-radius:10px;font-weight:700;\">点击查看搜索结果</a>
        </p>

        <div style=\"margin:18px 0;padding:14px 16px;background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;\">
          <div style=\"font-weight:700;margin-bottom:8px;\">重要提示</div>
          <ol style=\"margin:0;padding-left:18px;\">
            <li>结果链接有效期为 <strong>{expire_hours}小时</strong>，请在 <strong>{expire_time_str}</strong> 前访问查看，超时后链接将自动失效。</li>
            <li>若链接无法打开，请检查网络状态或确认 task_id 是否正确。</li>
          </ol>
        </div>

        <div style=\"margin-top:18px;padding-top:14px;border-top:1px solid #e5e7eb;color:#374151;\">
          <div style=\"font-weight:700;margin-bottom:8px;\">版权声明</div>
          <p style=\"margin:0;\">本项目是 GitHub 开源项目 <strong>Crawl-Res</strong>，旨在为用户提供公开网络资源的检索指引服务。</p>
          <p style=\"margin:8px 0 0;\">本项目检索的所有资源均来源于公开网络，<strong>Crawl-Res</strong> 未存储、上传、篡改任何资源文件，也不对资源的合法性、真实性、完整性承担任何法律责任。</p>
        </div>

        <p style=\"margin:18px 0 0;color:#6b7280;font-size:12px;\">Crawl-Res 开源项目组<br>{send_time}</p>
      </div>
    </div>
  </div>
</body>
</html>"""

        subject = f"Crawl-Res 检索完成：{task.keyword}"
        email_cfg = get_email_config()
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=email_cfg['from_email'] or getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            to=[task.email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        logger.info(f"邮件已发送至: {task.email}, 关键词: {task.keyword}")
        
        return str(task_id)

    except Exception as e:
        # 邮件失败不影响主爬虫任务，这里独立重试
        logger.error(f"send_email_task 发送邮件失败: {e}", exc_info=True)
        raise self.retry(exc=e)
    finally:
        close_old_connections()

@app.task
def crawl_task(task_id, keyword):
    logger.info(f"开始执行爬取任务: task_id={task_id}, keyword={keyword}")
    
    try:
        # 确保Django环境已初始化
        ensure_django_initialized()

        # 标记任务运行中
        # 并补齐 expire_time（兼容历史任务/手动插入的任务）
        now = timezone.now()
        task = SearchTask.objects.filter(task_id=task_id).first()
        if task and not task.expire_time:
            task.expire_time = now + timedelta(hours=get_result_expire_hours())
            task.save(update_fields=['expire_time'])
        SearchTask.objects.filter(task_id=task_id).update(status='RUNNING')
        close_old_connections()
        
        # 获取项目根目录
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        logger.info(f"项目根目录: {BASE_DIR}")

        enabled_sites = list(SiteConfig.objects.filter(enabled=True).order_by('key'))
        logger.info(f"从数据库读取站点配置: enabled={len(enabled_sites)}")
        if not enabled_sites:
            raise RuntimeError("数据库中没有启用的站点配置（SiteConfig.enabled=True）")
        
        # 在 Celery worker 进程内直接跑 CrawlerProcess 容易卡死：Twisted reactor
        # 在同一进程中只能启动一次；Celery prefork worker 会复用进程执行多个任务。
        # 这里改为每个任务启动一个独立子进程执行 Scrapy，彻底隔离 reactor。
        logger.info("开始执行爬取（子进程模式）")

        crawl_script = r'''
import os
import sys
import django

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scraper.settings")
django.setup()

from scraper.spiders.universal import UniversalSpider
from apps.search.models import SiteConfig

task_id = os.environ.get("CRAWL_TASK_ID")
keyword = os.environ.get("CRAWL_KEYWORD")

sites = SiteConfig.objects.filter(enabled=True).order_by('key')
config = {'sites': {}}
for s in sites:
    cfg = s.config or {}
    cfg.setdefault('name', s.name)
    if s.host:
        cfg.setdefault('host', s.host)
    config['sites'][s.key] = cfg

settings = get_project_settings()
settings.set('ITEM_PIPELINES', {
    'scraper.pipelines.DebugPipeline': 200,
    'scraper.pipelines.DjangoPipeline': 300,
})
settings.set('LOG_LEVEL', 'DEBUG')
settings.set('FEED_EXPORT_ENCODING', 'utf-8')

process = CrawlerProcess(settings)
for site_name, site_cfg in config['sites'].items():
    site_cfg['task_id'] = task_id
    process.crawl(UniversalSpider, site_cfg=site_cfg, keyword=keyword)

process.start(stop_after_crawl=True)
'''

        env = os.environ.copy()
        env.update({
            'CRAWL_TASK_ID': str(task_id),
            'CRAWL_KEYWORD': str(keyword),
            'CRAWL_BASE_DIR': str(BASE_DIR),
        })

        # 超时（秒）：防止站点无响应导致任务永久挂起
        timeout_seconds = get_crawl_timeout_seconds()
        logger.info(f"启动 Scrapy 子进程: timeout={timeout_seconds}s")

        proc = subprocess.Popen(
            [sys.executable, '-c', crawl_script],
            cwd=BASE_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            stdout, stderr = proc.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            raise TimeoutError(f"Scrapy 子进程超时 {timeout_seconds}s，已终止")

        if stdout:
            logger.info("Scrapy 子进程输出(stdout):\n" + stdout[-20000:])
        if stderr:
            logger.warning("Scrapy 子进程输出(stderr):\n" + stderr[-20000:])

        if proc.returncode != 0:
            raise RuntimeError(f"Scrapy 子进程退出码异常: {proc.returncode}")
        
        # 更新任务状态为成功
        logger.info("爬取完成，更新任务状态为SUCCESS")
        SearchTask.objects.filter(task_id=task_id).update(status='SUCCESS')

        # 邮件通知拆分为独立任务（可重试，且不影响爬虫主任务状态）
        send_email_task.delay(task_id)
        
    except Exception as e:
        logger.error(f"任务执行失败: {e}", exc_info=True)
        # 更新任务状态为失败
        SearchTask.objects.filter(task_id=task_id).update(status='FAILURE')
        raise
    finally:
        close_old_connections()
        logger.info(f"爬取任务完成: task_id={task_id}")
        return task_id
