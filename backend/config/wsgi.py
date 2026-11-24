"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import os
import shutil
from pathlib import Path

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Ensure SQLite DB and media directories are properly seeded on Vercel cold starts
if os.getenv('VERCEL') == '1':
    tmp_db = Path('/tmp/db.sqlite3')
    seed_db = Path(__file__).resolve().parent.parent / 'default_db.sqlite3'
    if (not tmp_db.exists() or tmp_db.stat().st_size == 0) and seed_db.exists():
        try:
            shutil.copyfile(seed_db, tmp_db)
        except Exception:
            pass

    try:
        os.makedirs('/tmp/media/datasets', exist_ok=True)
    except Exception:
        pass

application = get_wsgi_application()
