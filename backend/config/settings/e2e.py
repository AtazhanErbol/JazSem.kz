"""Explicitly isolated browser acceptance profile; not a deployment profile."""

import base64
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

if os.environ.get("E2E_ISOLATED") != "1":
    raise ImproperlyConfigured("E2E_ISOLATED=1 is required for synthetic browser acceptance")
os.environ["AI_ENABLED"] = "false"
os.environ["OPENAI_API_KEY"] = ""
os.environ.pop("SENTRY_DSN", None)
os.environ["MAIL_ENCRYPTION_KEY"] = base64.urlsafe_b64encode(b"e" * 32).decode()
os.environ["DEFAULT_FROM_EMAIL"] = "acceptance@example.test"

from .local import *  # noqa: E402,F403

_database = DATABASES["default"]  # noqa: F405
# runserver creates request threads rather than a bounded production worker
# pool. Close their connections at request end to avoid exhausting PostgreSQL.
_database["CONN_MAX_AGE"] = 0
if not (
    _database["ENGINE"] == "django.db.backends.sqlite3"
    and str(_database["NAME"]).replace("\\", "/").endswith("/qa.sqlite3")
    or _database["ENGINE"] == "django.db.backends.postgresql"
    and str(_database["NAME"]).startswith("jazsem_rc_")
    and _database["HOST"] in {"127.0.0.1", "localhost"}
):
    raise ImproperlyConfigured("Browser acceptance requires a separate synthetic database")
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "127.0.0.1"
EMAIL_PORT = int(os.environ.get("E2E_SMTP_PORT", "1025"))
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
EMAIL_USE_TLS = False  # Loopback sink only; production settings remain strict.
EMAIL_USE_SSL = False
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {**REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], "auth": "200/min"},  # noqa: F405
}

MEDIA_ROOT = Path(os.environ["JAZSEM_RUNTIME_DIR"]) / "private-media"
MAIL_PREVIOUS_ENCRYPTION_KEYS = []
CELERY_BEAT_SCHEDULE = {
    **CELERY_BEAT_SCHEDULE,  # noqa: F405
    "deliver-mail": {"task": "apps.notifications.tasks.flush_mail", "schedule": 2.0},
}  # noqa: F405
if os.environ.get("E2E_REDIS_URL"):
    from urllib.parse import urlsplit

    _redis = os.environ["E2E_REDIS_URL"]
    if urlsplit(_redis).hostname not in {"127.0.0.1", "localhost"}:
        raise ImproperlyConfigured("Browser acceptance requires loopback Redis")
    CELERY_BROKER_URL = _redis
    REDIS_URL = _redis
    CELERY_BROKER_TRANSPORT_OPTIONS = {"socket_connect_timeout": 1, "socket_timeout": 1}
    CELERY_RESULT_BACKEND = _redis
    # Several disposable DBs may share one local Redis. Their workers must
    # never consume task IDs belonging to another acceptance database.
    CELERY_TASK_DEFAULT_QUEUE = "acceptance-" + str(_database["NAME"])
    CELERY_TASK_DEFAULT_EXCHANGE = CELERY_TASK_DEFAULT_QUEUE
    CELERY_TASK_DEFAULT_ROUTING_KEY = CELERY_TASK_DEFAULT_QUEUE
    CELERY_CONTROL_EXCHANGE = CELERY_TASK_DEFAULT_QUEUE + "-control"
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _redis,
            "KEY_PREFIX": "e2e:" + str(_database["NAME"]),
        }
    }

if os.environ.get("E2E_FAKE_PROVIDER") == "1":
    ACCEPTANCE_SYNTHETIC = True
    ACCEPTANCE_CONTROL_DIR = str(Path(os.environ["JAZSEM_RUNTIME_DIR"]) / "provider-control")
    INSTALLED_APPS = [*INSTALLED_APPS, "tests.acceptance_provider.SyntheticProviderConfig"]  # noqa: F405
    AI_ENABLED = True
    OPENAI_API_KEY = "synthetic-acceptance-not-a-provider-key"
    OPENAI_MODEL = "synthetic-no-network"
    AI_INPUT_PRICE = "0.01"
    AI_OUTPUT_PRICE = "0.02"
