from django.db import models
from django.contrib.auth.models import User
from datasets.models import Dataset


class AnalysisHistory(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='analysis_history'
    )
    dataset = models.ForeignKey(
        Dataset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='histories'
    )
    dataset_name = models.CharField(max_length=255, default='sales_data.csv')
    dataset_type = models.CharField(max_length=50, default='CSV')
    analysis_type = models.CharField(max_length=255, default='Sales Trend Analysis')
    query_text = models.TextField(blank=True, default='')
    result_summary = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.dataset_name} - {self.analysis_type}"
