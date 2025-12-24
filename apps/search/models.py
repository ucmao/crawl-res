from django.db import models
import uuid


class SearchTask(models.Model):
    STATUS_CHOICES = [
        ('PENDING', '排队中'),
        ('RUNNING', '正在爬取'),
        ('SUCCESS', '检索成功'),
        ('FAILURE', '检索失败'),
    ]

    id = models.BigAutoField(primary_key=True)
    task_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    related_task_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    is_cache = models.BooleanField(default=False, db_index=True)
    keyword = models.CharField(max_length=255, verbose_name="搜索关键词")
    email = models.EmailField(verbose_name="通知邮箱")
    notify_email = models.BooleanField(default=True, db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    expire_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def masked_email(self):
        email = self.email or ''
        if '@' not in email:
            return email
        local, domain = email.split('@', 1)
        prefix = local[:2]
        return f"{prefix}{'*' * 6}@{domain}"

    class Meta:
        ordering = ['-created_at']
        db_table = 'search_tasks'


class ResourceResult(models.Model):
    task_id = models.UUIDField(db_index=True)
    title = models.CharField(max_length=500)
    disk_type = models.CharField(max_length=50, help_text="如：阿里云盘")
    url = models.TextField()
    site_source = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'resource_results'


class SiteConfig(models.Model):
    key = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    host = models.CharField(max_length=255, blank=True, default='')
    enabled = models.BooleanField(default=True, db_index=True)
    config = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'site_configs'
        ordering = ['key']


class CrawlerNode(models.Model):
    name = models.CharField(max_length=200, unique=True)
    host = models.CharField(max_length=255)
    enabled = models.BooleanField(default=True, db_index=True)
    remark = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'crawler_nodes'
        ordering = ['-created_at']


class EmailRule(models.Model):
    TYPE_ALLOW = 1
    TYPE_BLOCK = 2
    TYPE_CHOICES = [
        (TYPE_ALLOW, '白名单'),
        (TYPE_BLOCK, '黑名单'),
    ]

    id = models.BigAutoField(primary_key=True)
    rule = models.CharField(max_length=255, db_index=True)
    list_type = models.PositiveSmallIntegerField(choices=TYPE_CHOICES, db_index=True)
    regex_pattern = models.CharField(max_length=500)
    enabled = models.BooleanField(default=True, db_index=True)
    remark = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'email_rules'
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(fields=['list_type', 'rule'], name='uniq_email_rule_type_rule'),
        ]


class SystemConfig(models.Model):
    """系统配置表，存储各种可配置的系统参数"""
    KEY_CHOICES = [
        ('email_rate_limit_60', '邮箱限流-60秒内次数'),
        ('email_rate_limit_3600', '邮箱限流-3600秒内次数'),
        ('email_rate_limit_86400', '邮箱限流-86400秒内次数'),
        ('keyword_cache_ttl', '关键词缓存过期时间(秒)'),
        ('index_recent_tasks_count', '首页显示最近任务数量'),
        ('square_display_count', '资源广场显示数量'),
        ('square_fetch_count', '资源广场去重前获取数量'),
        ('square_expire_hours', '资源广场资源过期时间(小时)'),
        ('result_expire_hours', '结果页面过期时间(小时)'),
        ('email_host', '邮件服务器地址'),
        ('email_port', '邮件服务器端口'),
        ('email_use_ssl', '邮件使用SSL'),
        ('email_host_user', '邮件用户名'),
        ('email_host_password', '邮件密码'),
        ('email_from', '邮件发件人'),
        ('site_base_url', '站点基础URL'),
        ('crawl_timeout_seconds', '爬虫超时时间(秒)'),
    ]

    key = models.CharField(max_length=100, unique=True, db_index=True, choices=KEY_CHOICES, verbose_name="配置键")
    value = models.TextField(verbose_name="配置值")
    description = models.CharField(max_length=500, blank=True, default='', verbose_name="描述")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'system_configs'
        ordering = ['key']
        verbose_name = '系统配置'
        verbose_name_plural = '系统配置'

    def __str__(self):
        return f"{self.key} = {self.value}"

    def save(self, *args, **kwargs):
        """保存时清除缓存"""
        # 保存前记录旧的key和value（如果存在）
        old_key = None
        old_value = None
        if self.pk:
            try:
                old_obj = SystemConfig.objects.get(pk=self.pk)
                old_key = old_obj.key
                old_value = old_obj.value
            except SystemConfig.DoesNotExist:
                pass
        
        # 保存模型
        super().save(*args, **kwargs)
        
        # 清除缓存（无论值是否改变都清除，确保一致性）
        from django.core.cache import cache
        cache_key = f'system_config:{self.key}'
        cache.delete(cache_key)
        
        # 如果key改变了，也清除旧key的缓存
        if old_key and old_key != self.key:
            old_cache_key = f'system_config:{old_key}'
            cache.delete(old_cache_key)
        
        # 如果值改变了，确保清除缓存（即使key没变）
        if old_value is not None and old_value != self.value:
            cache.delete(cache_key)

    def delete(self, *args, **kwargs):
        """删除时清除缓存"""
        cache_key = f'system_config:{self.key}'
        from django.core.cache import cache
        # 先清除缓存，再删除
        cache.delete(cache_key)
        super().delete(*args, **kwargs)