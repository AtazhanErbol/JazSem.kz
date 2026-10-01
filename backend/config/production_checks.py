from ipaddress import ip_network
from urllib.parse import parse_qs, urlsplit

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

from config.redis_tls import redis_tls_options


def validate_production(env):
    """Fail closed on configuration errors, without including secret values."""
    required = [
        "DJANGO_SECRET_KEY",
        "MAIL_ENCRYPTION_KEY",
        "DATABASE_URL",
        "REDIS_URL",
        "DJANGO_ALLOWED_HOSTS",
        "FRONTEND_URL",
        "CSRF_TRUSTED_ORIGINS",
        "S3_BUCKET",
        "EMAIL_HOST",
        "DEFAULT_FROM_EMAIL",
        "TRUSTED_PROXY_CIDRS",
    ]
    missing = [name for name in required if not env.get(name)]
    if missing:
        raise ImproperlyConfigured("Missing production settings: " + ", ".join(missing))

    def require(condition, field):
        if not condition:
            raise ImproperlyConfigured("Invalid production setting: " + field)

    require(
        len(env["DJANGO_SECRET_KEY"]) >= 50 and not env["DJANGO_SECRET_KEY"].startswith("replace"),
        "DJANGO_SECRET_KEY",
    )
    for key in [
        env["MAIL_ENCRYPTION_KEY"],
        *filter(None, env.get("MAIL_PREVIOUS_ENCRYPTION_KEYS", "").split(",")),
    ]:
        try:
            Fernet(key.encode())
        except (ValueError, TypeError):
            raise ImproperlyConfigured("Invalid production setting: MAIL_ENCRYPTION_KEY") from None
    hosts = env["DJANGO_ALLOWED_HOSTS"].split(",")
    require(
        all(
            host and host == host.strip() and not host.startswith(("*", ".")) and "/" not in host
            for host in hosts
        ),
        "DJANGO_ALLOWED_HOSTS",
    )
    frontend = urlsplit(env["FRONTEND_URL"])
    require(
        frontend.scheme == "https"
        and frontend.hostname in hosts
        and not frontend.username
        and not frontend.query
        and not frontend.fragment
        and frontend.path in ["", "/"],
        "FRONTEND_URL",
    )
    origins = env["CSRF_TRUSTED_ORIGINS"].split(",")
    require(
        env["FRONTEND_URL"].rstrip("/") in origins
        and all(
            urlsplit(origin).scheme == "https"
            and urlsplit(origin).hostname in hosts
            and "*" not in origin
            for origin in origins
        ),
        "CSRF_TRUSTED_ORIGINS",
    )
    private = env.get("TRUSTED_SERVICE_NETWORK") == "true"
    database = urlsplit(env["DATABASE_URL"])
    require(
        database.scheme in ["postgres", "postgresql"]
        and database.hostname
        and database.username
        and database.password
        and database.path not in ["", "/"],
        "DATABASE_URL",
    )
    require(
        private
        or parse_qs(database.query).get("sslmode", [""])[0]
        in ["require", "verify-ca", "verify-full"],
        "DATABASE_URL sslmode",
    )
    redis = urlsplit(env["REDIS_URL"])
    redis_tls_options(env["REDIS_URL"], env.get("REDIS_SSL_CA_CERTS", ""))
    require(
        redis.hostname
        and redis.password
        and (redis.scheme == "rediss" or (private and redis.scheme == "redis")),
        "REDIS_URL transport/authentication",
    )
    endpoint = urlsplit(env.get("S3_ENDPOINT_URL", "https://s3.amazonaws.com"))
    require(
        endpoint.hostname
        and (endpoint.scheme == "https" or (private and endpoint.scheme == "http")),
        "S3_ENDPOINT_URL",
    )
    require(
        env.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
        == "django.core.mail.backends.smtp.EmailBackend",
        "EMAIL_BACKEND",
    )
    tls, ssl = (
        env.get("EMAIL_USE_TLS", "true") == "true",
        env.get("EMAIL_USE_SSL", "false") == "true",
    )
    require(tls != ssl, "EMAIL_USE_TLS/EMAIL_USE_SSL")
    require(
        "@" in env["DEFAULT_FROM_EMAIL"] and not env["DEFAULT_FROM_EMAIL"].endswith("@localhost"),
        "DEFAULT_FROM_EMAIL",
    )
    if env.get("EMAIL_HOST_USER"):
        require(bool(env.get("EMAIL_HOST_PASSWORD")), "EMAIL_HOST_PASSWORD")
    try:
        networks = [ip_network(value) for value in env["TRUSTED_PROXY_CIDRS"].split(",")]
        require(
            all(net.prefixlen == net.max_prefixlen for net in networks),
            "TRUSTED_PROXY_CIDRS (exact private peers required)",
        )
    except ValueError:
        raise ImproperlyConfigured("Invalid production setting: TRUSTED_PROXY_CIDRS") from None
