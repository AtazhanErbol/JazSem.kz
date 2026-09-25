from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

if not os.environ.get("DJANGO_SECRET_KEY") or not os.environ.get("MAIL_ENCRYPTION_KEY"):  # noqa: F405
    raise ImproperlyConfigured("Production requires DJANGO_SECRET_KEY and MAIL_ENCRYPTION_KEY")
if not os.environ.get("DATABASE_URL", "").startswith("postgres"):  # noqa: F405
    raise ImproperlyConfigured("Production requires PostgreSQL")
SESSION_COOKIE_SECURE = True
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("replace"):  # noqa: F405
    raise ImproperlyConfigured(
        "Use a cryptographically random production secret of at least 50 characters"
    )
Fernet(MAIL_ENCRYPTION_KEY.encode())  # noqa: F405
if not os.environ.get("S3_BUCKET"):  # noqa: F405
    raise ImproperlyConfigured("Production requires a private S3 bucket")
if EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend":  # noqa: F405
    raise ImproperlyConfigured("Production requires SMTP email backend")
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
