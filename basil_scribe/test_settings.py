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
