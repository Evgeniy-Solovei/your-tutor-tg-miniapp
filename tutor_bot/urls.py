from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core.miniapp_views import miniapp
from core.media_views import media_file
from knowledge.admin_guide import content_guide_view
from students.views_analytics import admin_analytics_view

urlpatterns = [
    re_path(r'^media/(?P<path>.+)$', media_file, name='media-file'),
    re_path(r'^app/(?P<path>.*)$', miniapp, name='miniapp-file'),
    re_path(r'^app$', miniapp, name='miniapp-no-slash'),
    path('admin/analytics/', admin.site.admin_view(admin_analytics_view), name='admin_analytics'),
    path('admin/content-guide/', admin.site.admin_view(content_guide_view), name='content_guide'),
    path('admin/', admin.site.urls),
    path('api/tutor/', include('students.urls')),
    path('api/tutor/learning/', include('learning.urls')),
    path('api/tutor/knowledge/', include('knowledge.urls')),
    path('api/tutor/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/tutor/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    re_path(r'^(?P<path>.*)$', miniapp, name='miniapp-root'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
