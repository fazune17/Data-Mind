from django.shortcuts import render
from django.conf import settings
from django.contrib.auth import get_user_model, login as auth_login
from datasets.models import Dataset
from analytics.models import AnalysisHistory


def get_authenticated_user(request):
    if request.user.is_authenticated:
        return request.user
    if settings.DEBUG:
        User = get_user_model()
        user = User.objects.first()
        if user:
            auth_login(request, user)
            return user
    return None


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
