from django.urls import path
from .views import (
    dashboard,
    datasets_page,
    upload_page,
    insights_page,
    ask_ai_page,
    sql_query_page,
    history_page,
    mysql_connectors_page
)

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('datasets/', datasets_page, name='datasets-page'),
    path('upload/', upload_page, name='upload-page'),
    path('insights/', insights_page, name='insights-page'),
    path('ask/', ask_ai_page, name='ask-ai-page'),
    path('sql/', sql_query_page, name='sql-query-page'),
    path('history/', history_page, name='history-page'),
    path('mysql-connectors/', mysql_connectors_page, name='mysql_connectors'),
]
