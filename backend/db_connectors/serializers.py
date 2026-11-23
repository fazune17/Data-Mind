
from rest_framework import serializers


class MySQLConnectionSerializer(serializers.Serializer):

    name = serializers.CharField(
        max_length=100,
        trim_whitespace=True
    )

    host = serializers.CharField(
        max_length=255,
        trim_whitespace=True
    )

    port = serializers.IntegerField(
        default=3306,
        min_value=1,
        max_value=65535
    )

    database_name = serializers.CharField(
        max_length=100,
        trim_whitespace=True
    )

    username = serializers.CharField(
        max_length=100,
        trim_whitespace=True
    )

    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        min_length=1
    )

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "Connection name cannot be empty."
            )
        return value.strip()

    def validate_host(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "MySQL host is required."
            )
        return value.strip()

    def validate_database_name(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "Database name is required."
            )
        return value.strip()

    def validate_username(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "MySQL username is required."
            )
        return value.strip()

    def validate_password(self, value):
        if not value:
            raise serializers.ValidationError(
                "MySQL password is required."
            )
        return value
