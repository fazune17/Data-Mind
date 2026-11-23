from django.urls import path

from .views import (
    DatasetUploadView,
    DatasetListView,
    DatasetPreviewView,
    DatasetProfileView
)

urlpatterns = [

    path(
        'upload/',
        DatasetUploadView.as_view(),
        name='dataset-upload'
    ),

    path(
        '',
        DatasetListView.as_view(),
        name='dataset-list'
    ),

    path(
        '<int:pk>/preview/',
        DatasetPreviewView.as_view(),
        name='dataset-preview'
    ),

    path(
        '<int:pk>/profile/',
        DatasetProfileView.as_view(),
        name='dataset-profile'
    ),

]