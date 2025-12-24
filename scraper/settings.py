import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-#@^-g!+@(9l&_^#5)#$#$#$#$#$#$#$#$#$#$#$#$'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True').lower() in ('1', 'true', 'yes', 'y')

# 从 SITE_BASE_URL 提取配置信息（用于 ALLOWED_HOSTS 和 CSRF_TRUSTED_ORIGINS）
from urllib.parse import urlparse
site_base_url = os.getenv('SITE_BASE_URL', 'http://127.0.0.1:8000')
parsed_url = urlparse(site_base_url)

# ALLOWED_HOSTS 配置
# 从 SITE_BASE_URL 提取域名，或使用环境变量配置（提高安全性，防止 HTTP Host 头攻击）
if DEBUG:
    ALLOWED_HOSTS = ['*']  # 开发环境允许所有主机
else:
    # 生产环境：从 SITE_BASE_URL 提取域名
    allowed_hosts = [parsed_url.hostname] if parsed_url.hostname else []
    # 也可以通过环境变量额外指定（多个域名用逗号分隔）
    extra_hosts = os.getenv('ALLOWED_HOSTS', '').split(',')
    ALLOWED_HOSTS = list(filter(None, allowed_hosts + [h.strip() for h in extra_hosts]))
    if not ALLOWED_HOSTS:
        ALLOWED_HOSTS = ['*']  # 如果没有配置，回退到允许所有（不推荐）

# CSRF 配置
# 从 SITE_BASE_URL 配置可信来源（解决 CSRF 验证失败问题）
# CSRF_TRUSTED_ORIGINS 需要完整的 URL（协议 + 域名 + 端口）
if parsed_url.scheme and parsed_url.netloc:
    # 构建完整的 origin URL（协议 + 域名 + 端口）
    csrf_origin = f"{parsed_url.scheme}://{parsed_url.netloc}"
    CSRF_TRUSTED_ORIGINS = [csrf_origin]
    # 也可以通过环境变量额外指定（多个用逗号分隔，例如：http://example.com,https://www.example.com）
    extra_origins = os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    CSRF_TRUSTED_ORIGINS.extend([o.strip() for o in extra_origins if o.strip()])
else:
    CSRF_TRUSTED_ORIGINS = []


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'apps.search',
    'django_celery_results',
]

# Celery配置
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'django-db')
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Shanghai'

# 缓存配置
# 优先使用Redis，如果没有配置则使用本地内存缓存
cache_backend = os.getenv('CACHE_BACKEND', 'redis')
if cache_backend == 'redis':
    try:
        cache_url = os.getenv('CACHE_URL', os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1'))
        CACHES = {
            'default': {
                'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                'LOCATION': cache_url,
                'KEY_PREFIX': 'crawl_res',
                'TIMEOUT': 3600,  # 默认缓存超时时间（秒）
            }
        }
    except Exception:
        # 如果Redis不可用，回退到本地内存缓存
        CACHES = {
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'LOCATION': 'crawl-res-cache',
                'TIMEOUT': 3600,
            }
        }
else:
    # 使用本地内存缓存
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'crawl-res-cache',
            'TIMEOUT': 3600,
        }
    }

# 站点基础 URL（用于邮件里生成结果链接）
SITE_BASE_URL = os.getenv('SITE_BASE_URL', 'http://127.0.0.1:8000')

# 邮件（163 SMTP）配置
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.163.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '465'))
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'true').lower() in ('1', 'true', 'yes', 'y')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'scraper.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'apps/search/templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'scraper.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.getenv('DB_NAME', 'crawl_res'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'zh-hans'

TIME_ZONE = 'Asia/Shanghai'

USE_I18N = True

USE_TZ = False  # 禁用时区支持，直接使用本地时间（北京时间）存储和显示


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
# 生产环境：收集静态文件的目录（运行 python manage.py collectstatic 后，所有静态文件会收集到这里）
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Logging 配置
# 确保 logs 目录存在
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# 日志级别：只保留 INFO 及以上级别的日志
LOG_LEVEL = 'INFO'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'file': {
            'level': LOG_LEVEL,
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'crawl_res.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,  # 保留5个备份文件
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'console': {
            'level': LOG_LEVEL,
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['file', 'console'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'apps.search': {
            'handlers': ['file', 'console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'celery': {
            'handlers': ['file', 'console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'scrapy': {
            'handlers': ['file'],  # 只使用 file handler，移除 console，避免重复输出
            'level': LOG_LEVEL,
            'propagate': False,
        },
        # 减少数据库查询日志的噪音（可选）
        'django.db.backends': {
            'handlers': ['file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}