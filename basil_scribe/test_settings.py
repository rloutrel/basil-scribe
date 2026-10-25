"""
Test-only settings: same as production settings except that the database is
an in-memory SQLite file, so the test suite runs without a PostgreSQL server.
Production never uses this module; the shipped configuration is
PostgreSQL-only.
"""

from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# The manifest storage expects the collectstatic output to exist; the
# test suite never serves hashed static URLs, so use the plain
# compressed storage instead.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
