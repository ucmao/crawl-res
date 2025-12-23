import os
from celery import Celery

# 使用正确的Django settings模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scraper.settings')
app = Celery('scraper')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()