from django.urls import path
from .views import (
    EDAView,
    DatasetInsightsView,
    SQLQueryView,
    AnalysisHistoryView
)

urlpatterns = [
    path('<int:pk>/', EDAView.as_view(), name='dataset-eda'),
    path('insights/', DatasetInsightsView.as_view(), name='dataset-insights-latest'),
    path('insights/<int:pk>/', DatasetInsightsView.as_view(), name='dataset-insights-detail'),
    path('sql/', SQLQueryView.as_view(), name='dataset-sql-query'),
    path('history/', AnalysisHistoryView.as_view(), name='analysis-history'),
]
