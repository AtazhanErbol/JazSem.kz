from django.conf import settings
from rest_framework.exceptions import APIException


class BackgroundUnavailable(APIException):
    status_code = 503
    default_detail = "Фоновый обработчик занят или недоступен. Повторите позже."
    default_code = "background_unavailable"


def worker_available():
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        return True
    from config.celery import app

    try:
        with app.connection_for_read(connect_timeout=1) as connection:
            connection.ensure_connection(max_retries=0, timeout=1)
        return bool(app.control.inspect(timeout=3, limit=1).ping())
    except Exception:
        return False


def require_worker():
    if not worker_available():
        raise BackgroundUnavailable()
