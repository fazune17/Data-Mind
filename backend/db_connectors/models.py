
from django.db import models
from django.contrib.auth.models import User


class ExternalMySQLConnection(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='external_mysql_connections'
    )

    name = models.CharField(max_length=100)

    host = models.CharField(max_length=255)

    port = models.PositiveIntegerField(default=3306)

    database_name = models.CharField(max_length=100)

    username = models.CharField(max_length=100)

    encrypted_password = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    last_connected_at = models.DateTimeField(
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.name} - {self.database_name}"
