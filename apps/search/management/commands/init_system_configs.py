"""
初始化系统配置的默认值
"""
from django.core.management.base import BaseCommand
from apps.search.config_utils import set_config


class Command(BaseCommand):
    help = '初始化系统配置的默认值'

    def handle(self, *args, **options):
        defaults = [
            ('email_rate_limit_60', '3', '邮箱限流：60秒内最多3次请求'),
            ('email_rate_limit_3600', '10', '邮箱限流：3600秒内最多10次请求'),
            ('email_rate_limit_86400', '30', '邮箱限流：86400秒内最多30次请求'),
            ('keyword_cache_ttl', '3600', '关键词缓存过期时间（秒）'),
            ('index_recent_tasks_count', '15', '首页显示最近任务数量'),
            ('square_display_count', '50', '资源广场显示数量'),
            ('square_fetch_count', '200', '资源广场去重前获取数量'),
            ('square_expire_hours', '24', '资源广场资源过期时间（小时）'),
            ('result_expire_hours', '24', '结果页面过期时间（小时）'),
            ('crawl_timeout_seconds', '1200', '爬虫超时时间（秒）'),
        ]

        created = 0
        updated = 0

        for key, value, description in defaults:
            # 检查配置是否已存在
            from apps.search.models import SystemConfig
            existing = SystemConfig.objects.filter(key=key).first()
            config = set_config(key, value, description)
            if existing:
                updated += 1
                self.stdout.write(self.style.WARNING(f'~ 更新配置: {key} = {value}'))
            else:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'✓ 创建配置: {key} = {value}'))

        self.stdout.write(self.style.SUCCESS(f'\n完成！创建 {created} 个配置，更新 {updated} 个配置'))

