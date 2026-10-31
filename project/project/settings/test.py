import os

# base.py needs these at import time; give them harmless defaults for tests.
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("SECRET_KEY", "test-only-secret-key")

from .base import *  # noqa: E402,F401,F403
from .base import REST_FRAMEWORK  # noqa: E402

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]

# In-memory SQLite: fast, and the tests need no MySQL.
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

# Cheap password hasher and a local cache keep the tests quick.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Generous rates so only the dedicated throttle test hits a limit.
# "anon" and "user" must exist too: TokenRefreshView uses the default throttle classes.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        "anon": "10000/hour",
        "user": "10000/hour",
        "customer": "10000/hour",
        "login": "10000/hour",
    },
}

# The CORS test needs exactly one allowed origin.
CORS_ALLOWED_ORIGINS = ["http://localhost:3000"]

# Emails are captured in memory so the password-reset test can read them.
EMAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
# Celery tasks run immediately instead of waiting for a worker.
CELERY_TASK_ALWAYS_EAGER = True
