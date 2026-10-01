"""Single-machine development: persistent Celery file queue, no Docker required."""

import os
from pathlib import Path

_root = Path(__file__).resolve().parents[3]
_allowed = ("AI_", "OPENAI_", "EMAIL_", "DEFAULT_FROM_EMAIL", "MAIL_ENCRYPTION_KEY")
_explicit = set(os.environ)
# Read only service settings, never execute shell code or inherit Docker DB/S3 URLs.
for _name in (
    ()
    if os.environ.get("DJANGO_SETTINGS_MODULE") == "config.settings.e2e"
    else (".env", ".env.local")
):
    _path = _root / _name
    if _path.exists():
        for _line in _path.read_text(encoding="utf-8-sig").splitlines():
            if "=" not in _line or _line.lstrip().startswith("#"):
                continue
            _key, _value = _line.split("=", 1)
            _key = _key.strip()
            if _key.startswith(_allowed):
                # Explicit process environment wins; .env.local overrides .env.
                if _key not in _explicit:
                    os.environ[_key] = _value.strip().strip('"').strip("'")

from .development import *  # noqa: E402,F403

_runtime = Path(os.environ.get("JAZSEM_RUNTIME_DIR", str(_root / ".runtime")))
for _folder in ("queue", "control", "emails", "cache"):
    (_runtime / _folder).mkdir(parents=True, exist_ok=True)
CELERY_BROKER_URL = "filesystem://"
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "data_folder_in": str(_runtime / "queue"),
    "data_folder_out": str(_runtime / "queue"),
    "control_folder": str(_runtime / "control"),
    "store_processed": False,
}
CELERY_RESULT_BACKEND = "cache+memory://"
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ROUTES = {}  # One local solo worker; production isolates heavy work.
CELERY_BEAT_SCHEDULE_FILENAME = str(_runtime / "celerybeat-schedule")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": str(_runtime / "cache"),
    }
}
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://127.0.0.1:5173")
if not (EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend" and EMAIL_HOST_PASSWORD):  # noqa: F405
    EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
    EMAIL_FILE_PATH = str(_runtime / "emails")
