from django.urls import path
from .views import AIAnalysisView

urlpatterns = [
    path(
        'ask/',
        AIAnalysisView.as_view(),
        name='ai-analysis'
    )
]