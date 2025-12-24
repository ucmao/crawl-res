from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('djadmin/', admin.site.urls),
    path('', include('apps.search.urls')),
]

# 提供静态文件服务
# 开发环境（DEBUG=True）：由 django.contrib.staticfiles 自动处理
# 生产环境（DEBUG=False）：使用 static() 函数提供静态文件
# 注意：在生产环境使用 Nginx 等 Web 服务器提供静态文件是更好的做法，性能更高
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)