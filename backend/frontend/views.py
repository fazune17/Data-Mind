import os
from django.shortcuts import render
from django.conf import settings
from django.contrib.auth import get_user_model, login as auth_login
from datasets.models import Dataset
from analytics.models import AnalysisHistory


def ensure_default_dataset(user):
    if Dataset.objects.filter(user=user).exists():
        return
    from datasets.processors import load_dataset, get_dataset_profile, get_dataset_schema
    from django.core.files import File

    benchmark_path = settings.BASE_DIR / 'media' / 'datasets' / 'DataMind_Stage2_Edge_Cases.xlsx'
    if os.path.exists(benchmark_path):
        try:
            df = load_dataset(str(benchmark_path))
            ds = Dataset(
                user=user,
                name="DataMind_Stage2_Edge_Cases.xlsx",
                source_type="excel",
                row_count=len(df),
                column_count=len(df.columns),
                schema_json=get_dataset_schema(df),
                profile_json=get_dataset_profile(df)
            )
            with open(benchmark_path, 'rb') as f:
                ds.file.save("DataMind_Stage2_Edge_Cases.xlsx", File(f), save=True)

            AnalysisHistory.objects.create(
                user=user,
                dataset=ds,
                dataset_name=ds.name,
                dataset_type="Excel",
                analysis_type="Sales Trend Analysis",
                query_text="Initial upload and auto-profile",
                result_summary=f"Processed {ds.row_count} rows and {ds.column_count} columns."
            )
        except Exception as e:
            print("Auto-seeding default dataset exception:", e)


def get_authenticated_user(request):
    User = get_user_model()
    if request.user.is_authenticated:
        user = request.user
    else:
        user = User.objects.first()
        if not user:
            user = User.objects.create_user(
                username='fazun',
                email='fazun@datamind.ai',
                password='datamind_password_2026'
            )
        auth_login(request, user)

    ensure_default_dataset(user)
    return user


def render_datamind_app(request, active_section="home"):
    user = get_authenticated_user(request)
    datasets = []
    history = []
    active_dataset = None

    if user:
        datasets = Dataset.objects.filter(user=user).order_by('-created_at')
        history = AnalysisHistory.objects.filter(user=user).order_by('-created_at')[:15]
        active_dataset = datasets.first()

    context = {
        "user": user,
        "active_section": active_section,
        "datasets": datasets,
        "history": history,
        "active_dataset": active_dataset,
    }
    return render(request, "frontend/dashboard.html", context)


def dashboard(request):
    return render_datamind_app(request, active_section="home")


def datasets_page(request):
    return render_datamind_app(request, active_section="datasets")


def upload_page(request):
    return render_datamind_app(request, active_section="upload")


def insights_page(request):
    return render_datamind_app(request, active_section="insights")


def ask_ai_page(request):
    return render_datamind_app(request, active_section="ask")


def sql_query_page(request):
    return render_datamind_app(request, active_section="sql")


def history_page(request):
    return render_datamind_app(request, active_section="history")


def mysql_connectors_page(request):
    return render(request, "frontend/mysql_connectors.html")
