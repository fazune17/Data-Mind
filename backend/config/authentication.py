from rest_framework.authentication import BaseAuthentication, SessionAuthentication
from django.contrib.auth import get_user_model


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return  # CSRF handled at application level


class DemoAutoAuthentication(BaseAuthentication):
    def authenticate(self, request):
        User = get_user_model()
        user = User.objects.first()
        if not user:
            try:
                user = User.objects.create_user(
                    username='fazun',
                    email='fazun@datamind.ai',
                    password='datamind_password_2026'
                )
            except Exception:
                user = User.objects.first()
        if user:
            return (user, None)
        return None
