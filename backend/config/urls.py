from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import RedirectView
from django.views.static import serve
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
    path('admin/', admin.site.urls),

    path(
        'api/datasets/',
        include('datasets.urls')
    ),
    
    path(
        'api/analytics/',
        include('analytics.urls')
    ),
    path(
        'api/ai/',
        include('ai_engine.urls')
    ),
    path(
        'api/connectors/mysql/',
        include('db_connectors.urls')
    ),
    path(
        'dashboard/',
        include('frontend.urls')
    ),
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.BASE_DIR / 'static'}),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]