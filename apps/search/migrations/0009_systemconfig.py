from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('search', '0008_searchtask_notify_email'),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemConfig',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('key', models.CharField(choices=[('email_rate_limit_60', '邮箱限流-60秒内次数'), ('email_rate_limit_3600', '邮箱限流-3600秒内次数'), ('email_rate_limit_86400', '邮箱限流-86400秒内次数'), ('keyword_cache_ttl', '关键词缓存过期时间(秒)'), ('index_recent_tasks_count', '首页显示最近任务数量'), ('square_display_count', '资源广场显示数量'), ('square_fetch_count', '资源广场去重前获取数量'), ('square_expire_hours', '资源广场资源过期时间(小时)'), ('result_expire_hours', '结果页面过期时间(小时)'), ('email_host', '邮件服务器地址'), ('email_port', '邮件服务器端口'), ('email_use_ssl', '邮件使用SSL'), ('email_host_user', '邮件用户名'), ('email_host_password', '邮件密码'), ('email_from', '邮件发件人'), ('site_base_url', '站点基础URL'), ('crawl_timeout_seconds', '爬虫超时时间(秒)')], db_index=True, max_length=100, unique=True, verbose_name='配置键')),
                ('value', models.TextField(verbose_name='配置值')),
                ('description', models.CharField(blank=True, default='', max_length=500, verbose_name='描述')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': '系统配置',
                'verbose_name_plural': '系统配置',
                'db_table': 'system_configs',
                'ordering': ['key'],
            },
        ),
    ]

