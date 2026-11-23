from rest_framework import serializers
from .models import Dataset


class DatasetSerializer(serializers.ModelSerializer):

    class Meta:
        model = Dataset

        fields = [
            'id',
            'name',
            'source_type',
            'row_count',
            'column_count',
            'schema_json',
            'profile_json',
            'created_at'
        ]

        read_only_fields = fields

class DatasetUploadSerializer(serializers.Serializer):

    file = serializers.FileField()

    def validate_file(self, value):
        import os

        extension = os.path.splitext(value.name)[1].lower()

        if extension not in ['.csv', '.xlsx']:
            raise serializers.ValidationError(
                "Only CSV and XLSX files are supported."
            )

        if value.size > 20 * 1024 * 1024:
            raise serializers.ValidationError(
                "Maximum file size is 20 MB."
            )

        return value        