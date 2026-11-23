
import logging

import pandas as pd

from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

try:
    from mysql.connector import Error as MySQLError
except ImportError:
    class MySQLError(Exception):
        pass

from .models import ExternalMySQLConnection

from .serializers import MySQLConnectionSerializer

from .security import encrypt_password

from .mysql_service import (
    connect_mysql,
    get_connection_config,
    get_tables,
    load_table_dataframe,
    dataframe_to_json
)

from analytics.eda import perform_eda

from ai_engine.analysis_agent import analyze_dataset


logger = logging.getLogger(__name__)


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def get_owned_connection(user, connection_id):

    return ExternalMySQLConnection.objects.get(
        id=connection_id,
        user=user
    )


def build_dataset_schema(df):

    schema = []

    for column in df.columns:

        schema.append({
            "column_name": str(column),
            "data_type": str(df[column].dtype),
            "unique_values": int(df[column].nunique()),
            "sample_values": [
                str(value)
                for value in df[column].dropna().head(5).tolist()
            ]
        })

    return schema


def build_dataset_profile(df):

    numerical_columns = df.select_dtypes(
        include="number"
    ).columns.tolist()

    categorical_columns = df.select_dtypes(
        include=["object", "category", "bool"]
    ).columns.tolist()

    return {
        "total_rows": int(len(df)),
        "total_columns": int(len(df.columns)),

        "missing_values": {
            str(column): int(count)
            for column, count in df.isnull().sum().items()
        },

        "duplicate_rows": int(df.duplicated().sum()),

        "numerical_columns": [
            str(column)
            for column in numerical_columns
        ],

        "categorical_columns": [
            str(column)
            for column in categorical_columns
        ]
    }


def get_dataframe(connection, table_name):

    return load_table_dataframe(
        connection,
        table_name
    )


# --------------------------------------------------
# 1. MYSQL CONNECTION LIST AND CREATE
# --------------------------------------------------

class MySQLConnectionListCreateView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        connections = ExternalMySQLConnection.objects.filter(
            user=request.user
        ).order_by("-created_at")

        data = []

        for item in connections:

            data.append({
                "id": item.id,
                "name": item.name,
                "host": item.host,
                "port": item.port,
                "database_name": item.database_name,
                "username": item.username,
                "created_at": item.created_at,
                "last_connected_at": item.last_connected_at
            })

        return Response({
            "success": True,
            "connections": data
        })

    def post(self, request):

        serializer = MySQLConnectionSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        config = {
            "host": data["host"],
            "port": data["port"],
            "database_name": data["database_name"],
            "username": data["username"],
            "password": data["password"]
        }

        connection = None

        try:

            # Test external MySQL connection

            connection = connect_mysql(config)

            tables = get_tables(connection)

            # Encrypt password before storing

            encrypted_password = encrypt_password(
                data["password"]
            )

            # Save connection profile

            saved = ExternalMySQLConnection.objects.create(

                user=request.user,

                name=data["name"],

                host=data["host"],

                port=data["port"],

                database_name=data["database_name"],

                username=data["username"],

                encrypted_password=encrypted_password,

                last_connected_at=timezone.now()
            )

            return Response({

                "success": True,

                "message": "MySQL connected successfully.",

                "connection": {
                    "id": saved.id,
                    "name": saved.name,
                    "database_name": saved.database_name
                },

                "tables": tables

            }, status=201)

        except MySQLError:

            logger.exception("External MySQL connection failed")

            return Response({
                "success": False,
                "error": "MySQL connection failed. Check host, port, username, password and database permissions."
            }, status=400)

        except Exception:

            logger.exception("MySQL connection profile creation failed")

            return Response({
                "success": False,
                "error": "Unable to save MySQL connection."
            }, status=500)

        finally:

            if connection is not None:

                try:
                    if connection.is_connected():
                        connection.close()
                except Exception:
                    logger.exception("Error closing MySQL connection")


# --------------------------------------------------
# 2. MYSQL TABLE DISCOVERY
# --------------------------------------------------

class MySQLTableListView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):

        connection = None

        try:

            saved = get_owned_connection(
                request.user,
                pk
            )

            config = get_connection_config(saved)

            connection = connect_mysql(config)

            tables = get_tables(connection)

            saved.last_connected_at = timezone.now()

            saved.save(
                update_fields=["last_connected_at"]
            )

            return Response({

                "success": True,

                "database": saved.database_name,

                "tables": tables

            })

        except ExternalMySQLConnection.DoesNotExist:

            return Response({
                "error": "MySQL connection not found."
            }, status=404)

        except Exception:

            logger.exception("MySQL table discovery failed")

            return Response({
                "error": "Unable to retrieve database tables."
            }, status=400)

        finally:

            if connection is not None:

                try:
                    connection.close()
                except Exception:
                    logger.exception("Error closing MySQL connection")


# --------------------------------------------------
# 3. MYSQL TABLE PREVIEW
# --------------------------------------------------

class MySQLTablePreviewView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, pk, table_name):

        connection = None

        try:

            saved = get_owned_connection(
                request.user,
                pk
            )

            config = get_connection_config(saved)

            connection = connect_mysql(config)

            df = get_dataframe(
                connection,
                table_name
            )

            preview = dataframe_to_json(
                df,
                limit=10
            )

            return Response({

                "success": True,

                "database": saved.database_name,

                "table": table_name,

                "total_rows_returned": min(len(df), 10),

                "columns": preview["columns"],

                "rows": preview["rows"]

            })

        except ExternalMySQLConnection.DoesNotExist:

            return Response({
                "error": "MySQL connection not found."
            }, status=404)

        except ValueError as error:

            return Response({
                "error": str(error)
            }, status=404)

        except Exception:

            logger.exception("MySQL table preview failed")

            return Response({
                "error": "Unable to preview database table."
            }, status=400)

        finally:

            if connection is not None:

                try:
                    connection.close()
                except Exception:
                    logger.exception("Error closing MySQL connection")


# --------------------------------------------------
# 4. MYSQL TABLE AUTOMATED EDA
# --------------------------------------------------

class MySQLTableEDAView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, pk, table_name):

        connection = None

        try:

            saved = get_owned_connection(
                request.user,
                pk
            )

            config = get_connection_config(saved)

            connection = connect_mysql(config)

            df = get_dataframe(
                connection,
                table_name
            )

            eda_results = perform_eda(df)

            return Response({

                "success": True,

                "database": saved.database_name,

                "table": table_name,

                "eda": eda_results

            })

        except ExternalMySQLConnection.DoesNotExist:

            return Response({
                "error": "MySQL connection not found."
            }, status=404)

        except ValueError as error:

            return Response({
                "error": str(error)
            }, status=404)

        except Exception:

            logger.exception("External MySQL EDA failed")

            return Response({
                "error": "External database EDA processing failed."
            }, status=400)

        finally:

            if connection is not None:

                try:
                    connection.close()
                except Exception:
                    logger.exception("Error closing MySQL connection")


# --------------------------------------------------
# 5. MYSQL TABLE GEMINI AI ANALYSIS
# --------------------------------------------------

class MySQLTableAIAnalysisView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, pk, table_name):

        question = request.data.get("question")

        if not isinstance(question, str):

            return Response({
                "error": "A valid question is required."
            }, status=400)

        question = question.strip()

        if not question:

            return Response({
                "error": "Question cannot be empty."
            }, status=400)

        if len(question) > 1000:

            return Response({
                "error": "Question must not exceed 1000 characters."
            }, status=400)

        connection = None

        try:

            saved = get_owned_connection(
                request.user,
                pk
            )

            config = get_connection_config(saved)

            connection = connect_mysql(config)

            df = get_dataframe(
                connection,
                table_name
            )

            # Build schema and profile

            schema = build_dataset_schema(df)

            profile = build_dataset_profile(df)

            # Run Gemini analysis

            result = analyze_dataset(

                question=question,

                df=df,

                schema=schema,

                profile=profile
            )

            return Response({

                "success": True,

                "database": saved.database_name,

                "table": table_name,

                "analysis": result

            })

        except ExternalMySQLConnection.DoesNotExist:

            return Response({
                "error": "MySQL connection not found."
            }, status=404)

        except ValueError as error:

            return Response({
                "success": False,
                "error": str(error)
            }, status=400)

        except Exception:

            logger.exception("External MySQL AI analysis failed")

            return Response({
                "success": False,
                "error": "External database AI analysis failed. Check server logs."
            }, status=502)

        finally:

            if connection is not None:

                try:
                    connection.close()
                except Exception:
                    logger.exception("Error closing MySQL connection")
