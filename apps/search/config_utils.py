"""
系统配置工具函数
用于获取和管理系统配置项
"""
from typing import Any, Optional
from django.core.cache import cache
from .models import SystemConfig


def get_config(key: str, default: Any = None, type_cast: type = str) -> Any:
    """
    获取系统配置值
    
    Args:
        key: 配置键
        default: 默认值（如果配置不存在）
        type_cast: 类型转换函数（如 int, float, bool）
    
    Returns:
        配置值，如果不存在则返回默认值
    """
    # 尝试从缓存获取
    cache_key = f'system_config:{key}'
    cached_value = cache.get(cache_key)
    if cached_value is not None:
        return _cast_value(cached_value, type_cast)
    
    # 从数据库获取
    config = SystemConfig.objects.filter(key=key).first()
    if config:
        value = config.value
        # 缓存1小时
        cache.set(cache_key, value, 3600)
        return _cast_value(value, type_cast)
    
    return default


def _cast_value(value: str, type_cast: type) -> Any:
    """类型转换"""
    if type_cast == bool:
        return value.lower() in ('1', 'true', 'yes', 'on', 'y')
    if type_cast == int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
    if type_cast == float:
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    return value


def set_config(key: str, value: str, description: str = '') -> SystemConfig:
    """
    设置系统配置值
    
    Args:
        key: 配置键
        value: 配置值（字符串）
        description: 描述
    
    Returns:
        SystemConfig对象
    """
    config, created = SystemConfig.objects.get_or_create(
        key=key,
        defaults={'value': str(value), 'description': description}
    )
    if not created:
        config.value = str(value)
        if description:
            config.description = description
        config.save(update_fields=['value', 'description', 'updated_at'])
    
    # 清除缓存
    cache_key = f'system_config:{key}'
    cache.delete(cache_key)
    
    return config


def get_email_rate_limit_windows() -> list:
    """
    获取邮箱限流窗口配置
    
    Returns:
        [(ttl, limit), ...] 格式的列表
    """
    return [
        (60, get_config('email_rate_limit_60', 3, int)),
        (3600, get_config('email_rate_limit_3600', 10, int)),
        (86400, get_config('email_rate_limit_86400', 30, int)),
    ]


def get_keyword_cache_ttl() -> int:
    """获取关键词缓存过期时间（秒）"""
    return get_config('keyword_cache_ttl', 3600, int)


def get_index_recent_tasks_count() -> int:
    """获取首页显示最近任务数量"""
    return get_config('index_recent_tasks_count', 15, int)


def get_square_display_count() -> int:
    """获取资源广场显示数量"""
    return get_config('square_display_count', 50, int)


def get_square_fetch_count() -> int:
    """获取资源广场去重前获取数量"""
    return get_config('square_fetch_count', 200, int)


def get_square_expire_hours() -> int:
    """获取资源广场资源过期时间（小时）"""
    return get_config('square_expire_hours', 24, int)


def get_result_expire_hours() -> int:
    """获取结果页面过期时间（小时）"""
    return get_config('result_expire_hours', 24, int)


def get_email_config() -> dict:
    """获取邮件配置"""
    import os
    return {
        'host': get_config('email_host', os.getenv('EMAIL_HOST', 'smtp.163.com')),
        'port': get_config('email_port', int(os.getenv('EMAIL_PORT', '465')), int),
        'use_ssl': get_config('email_use_ssl', os.getenv('EMAIL_USE_SSL', 'true').lower() in ('1', 'true', 'yes', 'y'), bool),
        'host_user': get_config('email_host_user', os.getenv('EMAIL_HOST_USER', '')),
        'host_password': get_config('email_host_password', os.getenv('EMAIL_HOST_PASSWORD', '')),
        'from_email': get_config('email_from', os.getenv('DEFAULT_FROM_EMAIL', '')),
        'site_base_url': get_config('site_base_url', os.getenv('SITE_BASE_URL', 'http://127.0.0.1:8000')),
    }


def get_crawl_timeout_seconds() -> int:
    """获取爬虫超时时间（秒）"""
    return get_config('crawl_timeout_seconds', 1200, int)

