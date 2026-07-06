"""
WSGI config for puntua_backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

# Hotfix for GooglePlusAuth import issue in older python-social-auth / drf-social-oauth2
try:
    import social_core.backends.google as google_backend
    if not hasattr(google_backend, 'GooglePlusAuth'):
        class GooglePlusAuth:
            pass
        google_backend.GooglePlusAuth = GooglePlusAuth
except ImportError:
    pass

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'puntua_backend.settings')

application = get_wsgi_application()
try:
    from puntua_backend.cron import start_scheduler
    start_scheduler()
    print("[Cron] Scheduler initialized")
except (ImportError, Exception) as e:
    print(f"[Cron] Error initializing scheduler: {str(e)}")