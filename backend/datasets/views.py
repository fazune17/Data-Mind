from pathlib import Path

from django.db import transaction

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from .models import Dataset
from .serializers import DatasetSerializer,DatasetUploadSerializer

from .processors import (
    load_dataset,
    get_dataset_schema,
    get_dataset_profile,
    get_dataset_preview
)


MAX_FILE_SIZE = 50 * 1024 * 1024

ALLOWED_EXTENSIONS = {'.csv', '.xlsx', '.xls'}


class DatasetUploadView(generics.GenericAPIView):

    permission_classes = [IsAuthenticated]

    parser_classes = [MultiPartParser, FormParser]

    serializer_class = DatasetUploadSerializer

    def post(self, request):

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data['file']

        if not uploaded_file:
            return Response(
                {"error": "Please upload a file."},
                status=status.HTTP_400_BAD_REQUEST
            )

        extension = Path(uploaded_file.name).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            return Response(
                {"error": "Only CSV and XLSX files are supported."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if uploaded_file.size > MAX_FILE_SIZE:
            return Response(
                {"error": "Maximum file size is 20 MB."},
                status=status.HTTP_400_BAD_REQUEST
            )

        dataset = None

        try:
            import os
            from django.conf import settings
            try:
                os.makedirs(settings.MEDIA_ROOT / 'datasets', exist_ok=True)
            except Exception:
                pass

            with transaction.atomic():

                dataset = Dataset(
                    user=request.user,
                    name=uploaded_file.name,
                    source_type='csv' if extension == '.csv' else 'excel'
                )

                dataset.file.save(
                    uploaded_file.name,
                    uploaded_file,
                    save=False
                )

                dataset_path = dataset.file.path

                df = load_dataset(dataset_path)

                dataset.row_count = len(df)
                dataset.column_count = len(df.columns)

                dataset.schema_json = get_dataset_schema(df)
                dataset.profile_json = get_dataset_profile(df)

                dataset.save()

                try:
                    from analytics.models import AnalysisHistory
                    AnalysisHistory.objects.create(
                        user=request.user,
                        dataset=dataset,
                        dataset_name=dataset.name,
                        dataset_type="CSV" if extension == ".csv" else "Excel",
                        analysis_type="Sales Trend Analysis",
                        query_text="Initial upload and auto-profile",
                        result_summary=f"Processed {dataset.row_count} rows and {dataset.column_count} columns."
                    )
                except Exception:
                    pass

            return Response(
                {
                    "message": "Dataset uploaded successfully.",
                    "dataset": DatasetSerializer(dataset).data,
                    "preview": get_dataset_preview(df)
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as error:

            if dataset and dataset.file:
                dataset.file.delete(save=False)

            return Response(
                {"error": str(error)},
                status=status.HTTP_400_BAD_REQUEST
            )


class DatasetListView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        datasets = Dataset.objects.filter(
            user=request.user
        ).order_by('-created_at')

        serializer = DatasetSerializer(
            datasets,
            many=True
        )

        return Response(serializer.data)


class DatasetDetailView(APIView):

    permission_classes = [IsAuthenticated]

    def get_dataset(self, request, pk):

        try:
            return Dataset.objects.get(
                id=pk,
                user=request.user
            )

        except Dataset.DoesNotExist:
            return None


class DatasetPreviewView(DatasetDetailView):

    def get(self, request, pk):

        dataset = self.get_dataset(request, pk)

        if not dataset:
            return Response(
                {"error": "Dataset not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if not dataset.file:
            return Response(
                {"error": "This dataset has no uploaded file."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            df = load_dataset(dataset.file.path)

            return Response(
                get_dataset_preview(df, limit=10)
            )

        except Exception:
            return Response(
                {"error": "Unable to read dataset."},
                status=status.HTTP_400_BAD_REQUEST
            )


class DatasetProfileView(DatasetDetailView):

    def get(self, request, pk):

        dataset = self.get_dataset(request, pk)

        if not dataset:
            return Response(
                {"error": "Dataset not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(dataset.profile_json)