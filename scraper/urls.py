from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('djadmin/', admin.site.urls),
    path('', include('apps.search.urls')),
]

# 生产环境提供静态文件服务（开发环境由 django.contrib.staticfiles 自动处理）
# 注意：在生产环境使用 Nginx 等 Web 服务器提供静态文件是更好的做法，性能更高
if not settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)