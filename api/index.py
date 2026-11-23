import os
import sys
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application
app = get_wsgi_application()

# Auto-migrate SQLite on /tmp if on Vercel
if os.getenv("VERCEL") == "1":
    try:
        from django.core.management import call_command
        call_command("migrate", interactive=False)
    except Exception as e:
        print("Vercel startup migration exception:", e)
