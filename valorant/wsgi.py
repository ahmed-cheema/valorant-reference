"""
WSGI config for valorant project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application
#from whitenoise import WhiteNoise

#from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'valorant.settings')

application = get_wsgi_application()
#application = WhiteNoise(application, root=os.path.join(settings.BASE_DIR, 'staticfiles'))