from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from datasets.models import Dataset
from datasets.processors import load_dataset
from .eda import perform_eda
from .insights_service import generate_dataset_insights
from .sql_service import execute_sql_query, generate_sql_from_nl
from .models import AnalysisHistory


class EDAView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            dataset = Dataset.objects.get(id=pk, user=request.user)

            if not dataset.file:
                return Response({"error": "Uploaded file not available."}, status=400)

            df = load_dataset(dataset.file.path)
            result = perform_eda(df)

            return Response({
                "success": True,
                "dataset": dataset.name,
                "eda": result
            })

        except Dataset.DoesNotExist:
            return Response({"error": "Dataset not found."}, status=404)
        except Exception:
            return Response({"error": "EDA processing failed."}, status=400)


class DatasetInsightsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        try:
            if pk:
                dataset = Dataset.objects.get(id=pk, user=request.user)
            else:
                dataset = Dataset.objects.filter(user=request.user).order_by('-created_at').first()

            if not dataset or not dataset.file:
                return Response({"error": "No dataset file available."}, status=404)

            df = load_dataset(dataset.file.path)
            insights = generate_dataset_insights(df)

            return Response({
                "success": True,
                "dataset_id": dataset.id,
                "dataset_name": dataset.name,
                "insights": insights
            })

        except Dataset.DoesNotExist:
            return Response({"error": "Dataset not found."}, status=404)
        except Exception as e:
            return Response({"error": f"Failed to generate insights: {str(e)}"}, status=400)


class SQLQueryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        dataset_id = request.data.get("dataset_id")
        query = request.data.get("query")
        natural_language = request.data.get("natural_language")

        if not dataset_id:
            dataset = Dataset.objects.filter(user=request.user).order_by('-created_at').first()
        else:
            try:
                dataset = Dataset.objects.get(id=dataset_id, user=request.user)
            except Dataset.DoesNotExist:
                return Response({"error": "Dataset not found."}, status=404)

        if not dataset or not dataset.file:
            return Response({"error": "Dataset file is missing."}, status=400)

        df = load_dataset(dataset.file.path)

        # Natural language translation if provided
        generated_sql = None
        if natural_language:
            try:
                query = generate_sql_from_nl(natural_language, df, dataset.schema_json)
                generated_sql = query
            except Exception as e:
                return Response({"error": f"AI SQL generation error: {str(e)}"}, status=400)

        if not query:
            return Response({"error": "SQL query or question required."}, status=400)

        try:
            results = execute_sql_query(df, query)

            # Record in history
            AnalysisHistory.objects.create(
                user=request.user,
                dataset=dataset,
                dataset_name=dataset.name,
                dataset_type="CSV" if dataset.source_type == "csv" else "Excel",
                analysis_type="SQL Query",
                query_text=query,
                result_summary=f"Returned {results['count']} rows in {results['execution_time_ms']} ms"
            )

            return Response({
                "success": True,
                "dataset_id": dataset.id,
                "dataset_name": dataset.name,
                "query": query,
                "generated_sql": generated_sql,
                "results": results
            })
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class AnalysisHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        records = AnalysisHistory.objects.filter(user=request.user).order_by('-created_at')[:20]
        data = []
        for r in records:
            data.append({
                "id": r.id,
                "dataset_name": r.dataset_name,
                "dataset_type": r.dataset_type,
                "analysis_type": r.analysis_type,
                "query_text": r.query_text,
                "result_summary": r.result_summary,
                "date": r.created_at.strftime("%d %b %Y"),
                "created_at": r.created_at.isoformat()
            })
        return Response({"success": True, "history": data})

    def post(self, request):
        dataset_name = request.data.get("dataset_name", "sales_data.csv")
        dataset_type = request.data.get("dataset_type", "CSV")
        analysis_type = request.data.get("analysis_type", "Sales Trend Analysis")
        query_text = request.data.get("query_text", "")
        result_summary = request.data.get("result_summary", "")

        record = AnalysisHistory.objects.create(
            user=request.user,
            dataset_name=dataset_name,
            dataset_type=dataset_type,
            analysis_type=analysis_type,
            query_text=query_text,
            result_summary=result_summary
        )

        return Response({
            "success": True,
            "id": record.id,
            "date": record.created_at.strftime("%d %b %Y")
        }, status=status.HTTP_201_CREATED)
