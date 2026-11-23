from django.contrib import admin
from .models import Dataset


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'name',
        'user',
        'source_type',
        'row_count',
        'column_count',
        'created_at'
    )

    list_filter = ('source_type', 'created_at')

    search_fields = ('name', 'user__username')

    readonly_fields = ('created_at',)