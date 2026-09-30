from config.production_checks import validate_production

from .base import *  # noqa: F403

validate_production(os.environ)  # noqa: F405
SESSION_COOKIE_SECURE = True
SECURE_REDIRECT_EXEMPT = [r"^(health|ready)/$"]
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
