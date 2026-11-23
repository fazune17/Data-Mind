from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
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
    path(
    'api/datasets/',
    include('datasets.urls')
    ),

]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )