import os
from django.core.asgi import get_asgi_application
from django.conf import settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'apimovil.settings')

application = get_asgi_application()

if settings.DEBUG:
    application = ASGIStaticFilesHandler(application)
