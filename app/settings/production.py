import os

import dj_database_url

from .base import *

DEBUG = False

# Allowed hosts via env
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if os.environ.get("DJANGO_ALLOWED_HOSTS") else ["*"]

# Secret key
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")

# Database: PostgreSQL via DATABASE_URL or discrete vars
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=os.environ.get("DB_SSL", "0") == "1"),
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "app"),
            "USER": os.environ.get("POSTGRES_USER", "app"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": int(os.environ.get("POSTGRES_PORT", "5432")),
        }
    }

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "1") == "1"
CSRF_COOKIE_SECURE = os.environ.get("CSRF_COOKIE_SECURE", "1") == "1"

try:
    from .local import *
except ImportError:
    pass
