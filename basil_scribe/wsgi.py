"""WSGI config for the Basil scribe component."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "basil_scribe.settings")

application = get_wsgi_application()

from drafts.tasks import start_pool  # noqa: E402

start_pool()
