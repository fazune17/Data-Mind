
from django.urls import path

from .views import (
    MySQLConnectionListCreateView,
    MySQLTableListView,
    MySQLTablePreviewView,
    MySQLTableEDAView,
    MySQLTableAIAnalysisView
)

urlpatterns = [

    # Create and list MySQL connections
    path(
        '',
        MySQLConnectionListCreateView.as_view(),
        name='mysql-connections'
    ),

    # Discover database tables
    path(
        '<int:pk>/tables/',
        MySQLTableListView.as_view(),
        name='mysql-tables'
    ),

    # Preview table records
    path(
        '<int:pk>/tables/<str:table_name>/preview/',
        MySQLTablePreviewView.as_view(),
        name='mysql-table-preview'
    ),

    # Automated EDA
    path(
        '<int:pk>/tables/<str:table_name>/eda/',
        MySQLTableEDAView.as_view(),
        name='mysql-table-eda'
    ),

    # Gemini AI analysis
    path(
        '<int:pk>/tables/<str:table_name>/ask/',
        MySQLTableAIAnalysisView.as_view(),
        name='mysql-table-ai'
    ),

]
