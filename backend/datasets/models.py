
from django.db import models
from django.contrib.auth.models import User


class Dataset(models.Model):

    SOURCE_CHOICES = [
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('mysql', 'MySQL'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='datasets'
    )

    name = models.CharField(max_length=255)

    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES
    )

    file = models.FileField(
        upload_to='datasets/',
        blank=True,
        null=True
    )

    row_count = models.PositiveBigIntegerField(default=0)

    column_count = models.PositiveIntegerField(default=0)

    schema_json = models.JSONField(default=dict)

    profile_json = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
