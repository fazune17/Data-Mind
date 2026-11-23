
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from datasets.models import Dataset
from datasets.processors import load_dataset

from .analysis_agent import analyze_dataset
import logging

logger = logging.getLogger(__name__)


class AIAnalysisView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        dataset_id = request.data.get("dataset_id")
        question = request.data.get("question")

        if not dataset_id or not question:
            return Response({
                "error": "dataset_id and question are required."
            }, status=400)

        if not isinstance(question, str) or len(question) > 1000:
            return Response({
                "error": "Question must be a string of at most 1000 characters."
            }, status=400)

        question = question.strip()

        if not question:
            return Response({
                "error": "Question cannot be empty."
            }, status=400)

        try:
            dataset = Dataset.objects.get(
                id=dataset_id,
                user=request.user
            )

            if not dataset.file:
                return Response({
                    "error": "Uploaded dataset file not available."
                }, status=400)

            df = load_dataset(dataset.file.path)

            result = analyze_dataset(
                question=question,
                df=df,
                schema=dataset.schema_json,
                profile=dataset.profile_json
            )

            try:
                from analytics.models import AnalysisHistory
                AnalysisHistory.objects.create(
                    user=request.user,
                    dataset=dataset,
                    dataset_name=dataset.name,
                    dataset_type="CSV" if dataset.source_type == "csv" else "Excel",
                    analysis_type="Ask with AI",
                    query_text=question,
                    result_summary=result.get("insights", "")[:250]
                )
            except Exception:
                pass

            return Response({
                "success": True,
                "dataset": dataset.name,
                "analysis": result
            })

        except Dataset.DoesNotExist:
            return Response({
                "error": "Dataset not found."
            }, status=404)

        except ValueError as error:
            return Response({
                "success": False,
                "error": str(error)
            }, status=400)

        except Exception as error:

            logger.exception("DataMind AI Analysis Error")

            return Response({
                "success": False,
                "error": str(error)
            }, status=502)
