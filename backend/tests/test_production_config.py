import base64

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.production_checks import validate_production


def valid_env():
    return {
        "DJANGO_SECRET_KEY": "SyntheticTestOnly-" * 4,
        "MAIL_ENCRYPTION_KEY": base64.urlsafe_b64encode(b"2" * 32).decode(),
        "DATABASE_URL": "postgresql://qa:test@database/qa?sslmode=require",
        "REDIS_URL": "rediss://:test@cache:6379/0",
        "DJANGO_ALLOWED_HOSTS": "rc.example.test",
        "FRONTEND_URL": "https://rc.example.test",
        "CSRF_TRUSTED_ORIGINS": "https://rc.example.test",
        "S3_BUCKET": "qa-private",
        "EMAIL_HOST": "smtp.example.test",
        "DEFAULT_FROM_EMAIL": "qa@example.test",
        "TRUSTED_PROXY_CIDRS": "172.30.0.20/32",
    }


def test_production_requires_explicit_complete_configuration():
    env = valid_env()
    validate_production(env)
    for key in env:
        missing = {name: value for name, value in env.items() if name != key}
        with pytest.raises(ImproperlyConfigured):
            validate_production(missing)


@pytest.mark.parametrize(
    "key,value",
    [
        ("FRONTEND_URL", "http://rc.example.test"),
        ("DJANGO_ALLOWED_HOSTS", "*"),
        ("DATABASE_URL", "sqlite:///database"),
        ("REDIS_URL", "redis://:SECRET@cache/0"),
        ("CSRF_TRUSTED_ORIGINS", "https://*.example.test"),
        ("EMAIL_USE_TLS", "false"),
        ("MAIL_ENCRYPTION_KEY", "SECRET-invalid-key"),
        ("TRUSTED_PROXY_CIDRS", "0.0.0.0/0"),
    ],
)
def test_invalid_production_settings_do_not_echo_values(key, value):
    env = {**valid_env(), key: value}
    with pytest.raises(ImproperlyConfigured) as error:
        validate_production(env)
    assert "SECRET" not in str(error.value)


def test_liveness_accepts_explicit_domain_without_loopback_in_allowed_hosts(client, settings):
    settings.ALLOWED_HOSTS = ["rc.example.test"]
    assert client.get("/health/", HTTP_HOST="rc.example.test").status_code == 200
    assert client.get("/health/", HTTP_HOST="127.0.0.1").status_code == 400
