"""
ASGI config for puntua_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
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

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'puntua_backend.settings')

application = get_asgi_application()
