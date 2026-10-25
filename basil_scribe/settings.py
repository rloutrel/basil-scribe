"""
Django settings for the Basil scribe component.

Configuration is strictly environment-based (12-factor).
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

if os.environ.get("DJANGO_ENV_FILE"):
    try:
        from dotenv import load_dotenv

        load_dotenv(os.environ["DJANGO_ENV_FILE"])
    except ImportError:
        pass

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-development-key-change-me",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if h.strip()
]

if os.environ.get("DATABASE_URL"):
    import dj_database_url

    DATABASES = {"default": dj_database_url.parse(os.environ["DATABASE_URL"])}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "basil_scribe"),
            "USER": os.environ.get("POSTGRES_USER", "basil"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "basil"),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "profiles",
    "precedents",
    "drafts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "profiles.middleware.ActiveProfileMiddleware",
]

ROOT_URLCONF = "basil_scribe.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "profiles.context_processors.active",
            ],
        },
    },
]

WSGI_APPLICATION = "basil_scribe.wsgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation.MinimumLengthValidator"
        )
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-gb"

LANGUAGES = [
    ("de", "Deutsch"),
    ("en", "English"),
    ("fr", "Français"),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "UTC")

USE_I18N = True

USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

LOGIN_URL = "admin:login"
LOGIN_REDIRECT_URL = "drafts:home"
LOGOUT_REDIRECT_URL = "drafts:home"

PROFILES_DIR = os.environ.get("PROFILES_DIR", BASE_DIR / "profiles")

MAIL_EXPORT_ROOT = os.environ.get("MAIL_EXPORT_ROOT", "/data/mail-exports")

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "")

EMBED_DEVICE = os.environ.get("EMBED_DEVICE", "cpu")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "BAAI/bge-m3")

DEFAULT_LLM_TEMPERATURE = float(
    os.environ.get("DEFAULT_LLM_TEMPERATURE", "0.7")
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[%(asctime)s] %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "core": {
            "handlers": ["console"],
            "level": os.environ.get("BASIL_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "profiles": {
            "handlers": ["console"],
            "level": os.environ.get("BASIL_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "precedents": {
            "handlers": ["console"],
            "level": os.environ.get("BASIL_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "drafts": {
            "handlers": ["console"],
            "level": os.environ.get("BASIL_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
