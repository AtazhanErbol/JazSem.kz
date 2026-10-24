import os

from config.production_checks import validate_production
from config.vercel_environment import configure_runtime

if os.environ.get("VERCEL") == "1":
    # Vercel also imports settings directly while detecting the Django app.
    configure_runtime(os.environ)

from .base import *  # noqa: E402, F403

validate_production(os.environ)
SESSION_COOKIE_SECURE = True
SECURE_REDIRECT_EXEMPT = [r"^(health|ready)/$"]
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
REQUIRED_WORKER_ROLES = ["short", "heavy"]
STORAGE_PROBE_KEY = "private/health/readiness.txt"
