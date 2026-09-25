from .base import *  # noqa: F403

DEBUG = True
if not os.environ.get("CSRF_TRUSTED_ORIGINS"):  # noqa: F405
    CSRF_TRUSTED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
if not os.environ.get("REDIS_URL"):  # noqa: F405
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
if not MAIL_ENCRYPTION_KEY:  # noqa: F405
    import base64
    import hashlib

    MAIL_ENCRYPTION_KEY = base64.urlsafe_b64encode(
        hashlib.sha256(SECRET_KEY.encode()).digest()  # noqa: F405
    ).decode()  # noqa: F405
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")  # noqa: F405
