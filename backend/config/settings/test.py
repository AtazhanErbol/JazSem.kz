import base64

from .base import *  # noqa: F403

DATABASES = {"default": dj_database_url.config(default="sqlite:///:memory:")}  # noqa: F405
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
MAIL_ENCRYPTION_KEY = base64.urlsafe_b64encode(b"0" * 32).decode()
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
