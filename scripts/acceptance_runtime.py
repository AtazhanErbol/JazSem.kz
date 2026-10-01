"""Production-settings smoke in disposable compose.acceptance.yml only.

Run via the isolated mail (development tooling) container; output is counts only.
"""

import argparse
import json
import os
import socket
import ssl
import time

import django

django.setup()

import redis
import requests
from apps.accounts.models import User
from apps.notifications.models import MailOutbox
from apps.notifications.services import queue_mail
from celery import Celery
from config.celery import app
from config.redis_tls import redis_tls_options
from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from kombu.exceptions import OperationalError

assert settings.DATABASES["default"]["NAME"] == "jazsem_rc_runtime"
assert (
    settings.STORAGES["default"]["OPTIONS"]["bucket_name"]
    == "jazsem-acceptance-private"
)
assert not settings.DEBUG and not settings.AI_ENABLED and not settings.OPENAI_API_KEY
base = "https://rc.example.test:8443"
password = "Synthetic-runtime-login-7482!"


def wait_for(check, seconds=90):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(1)
    raise AssertionError("Acceptance dependency did not reach expected state")


def initialize():
    storage = default_storage
    client = storage.connection.meta.client
    buckets = client.list_buckets()["Buckets"]
    if not any(bucket["Name"] == storage.bucket_name for bucket in buckets):
        client.create_bucket(Bucket=storage.bucket_name)
    if not storage.exists(settings.STORAGE_PROBE_KEY):
        assert (
            storage.save(
                settings.STORAGE_PROBE_KEY, ContentFile(b"synthetic readiness")
            )
            == settings.STORAGE_PROBE_KEY
        )
    for role in ("ADMIN", "TEACHER", "STUDENT"):
        email = f"runtime-{role.lower()}@example.test"
        user, created = User.objects.get_or_create(
            username=email,
            defaults={
                "email": email,
                "role": role,
                "must_change_password": False,
            },
        )
        if created:
            user.set_password(password)
            user.save()
    print(json.dumps({"initialized": True, "synthetic_users": 3}))


def tls_clients():
    assert settings.CELERY_BROKER_USE_SSL["ssl_cert_reqs"] == ssl.CERT_REQUIRED
    assert settings.CELERY_REDIS_BACKEND_USE_SSL["ssl_check_hostname"] is True
    with app.connection_for_write() as connection:
        connection.ensure_connection(max_retries=0)
        assert connection.channel().client.ping()
    app.backend.set("acceptance:result", b"verified")
    assert app.backend.get("acceptance:result") == b"verified"
    app.backend.delete("acceptance:result")
    cache.set("acceptance:cache", "verified", timeout=15)
    assert cache.get("acceptance:cache") == "verified"
    cache.delete("acceptance:cache")
    # System trust roots do not trust this disposable CA. Both actual Celery
    # clients must reject it, not merely have a reassuring config dictionary.
    rejected = 0
    bad = Celery(
        "untrusted-acceptance", broker=settings.REDIS_URL, backend=settings.REDIS_URL
    )
    bad.conf.update(
        broker_use_ssl=redis_tls_options(settings.REDIS_URL),
        redis_backend_use_ssl=redis_tls_options(settings.REDIS_URL),
        broker_connection_timeout=2,
        redis_socket_connect_timeout=2,
        redis_socket_timeout=2,
        broker_transport_options={"max_retries": 0},
    )
    # SSL_CERT_FILE otherwise makes the synthetic CA a process-wide trust root.
    previous = os.environ.pop("SSL_CERT_FILE", None)
    try:
        try:
            with bad.connection_for_write() as connection:
                connection.ensure_connection(max_retries=0)
        except (OperationalError, redis.exceptions.ConnectionError) as error:
            assert "CERTIFICATE_VERIFY_FAILED" in str(error)
            rejected += 1
        try:
            bad.backend.client.ping()
        except redis.exceptions.ConnectionError as error:
            assert "CERTIFICATE_VERIFY_FAILED" in str(error)
            rejected += 1
    finally:
        if previous:
            os.environ["SSL_CERT_FILE"] = previous
        bad.close()
    assert rejected == 2
    wrong_host_url = settings.REDIS_URL.replace(
        "@redis:", "@" + socket.gethostbyname("redis") + ":"
    )
    wrong_host = redis.Redis.from_url(wrong_host_url, **settings.REDIS_TLS_OPTIONS)
    try:
        wrong_host.ping()
    except redis.exceptions.ConnectionError as error:
        assert "CERTIFICATE_VERIFY_FAILED" in str(error)
    else:
        raise AssertionError("TLS hostname mismatch was accepted")
    print(
        json.dumps(
            {
                "redis_tls_verified_clients": 3,
                "untrusted_ca_rejections": rejected,
                "hostname_mismatch_rejected": True,
            }
        )
    )


def probe():
    session = requests.Session()
    session.trust_env = False
    session.verify = "/certs/ca.pem"
    live = session.get(base + "/health/", timeout=12)
    readiness = session.get(base + "/ready/", timeout=12)
    assert live.status_code == 200
    print(
        json.dumps(
            {
                "health": live.status_code,
                "ready": readiness.status_code,
                "status": readiness.json()["status"],
            }
        )
    )


def http_smoke():
    session = requests.Session()
    session.trust_env = False
    session.verify = "/certs/ca.pem"

    def get(path, **kwargs):
        return session.get(base + path, timeout=8, **kwargs)

    wait_for(lambda: get("/ready/").status_code == 200)
    assert get("/health/").status_code == 200
    for path in ("/", "/login", "/app/courses"):
        response = get(path)
        assert response.status_code == 200 and '<div id="root">' in response.text
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert (
        get("/health/", headers={"Host": "unexpected.example.test"}).status_code == 400
    )
    csrf = get("/api/v1/auth/login/").json()["csrfToken"]
    assert session.cookies.get_dict().get("csrftoken")
    assert all(cookie.secure for cookie in session.cookies)
    body = {"email": "runtime-admin@example.test", "password": password}
    assert (
        session.post(base + "/api/v1/auth/login/", json=body, timeout=8).status_code
        == 403
    )
    session.headers.update({"X-CSRFToken": csrf, "Origin": base})
    assert (
        session.post(base + "/api/v1/auth/login/", json=body, timeout=8).status_code
        == 200
    )
    assert all(cookie.secure for cookie in session.cookies)
    assert get("/api/v1/auth/me/").json()["role"] == "ADMIN"
    assert get("/api/v1/operations/").status_code == 200
    assert get("/api/v1/mail-outbox/").status_code == 200
    # Anonymous direct S3 read must fail despite a real sentinel object.
    response = requests.get(
        "http://minio:9000/jazsem-acceptance-private/" + settings.STORAGE_PROBE_KEY,
        timeout=8,
    )
    assert response.status_code == 403
    user = User.objects.get(email="runtime-admin@example.test")
    queue_mail(user, "Synthetic TLS acceptance", "Synthetic notification")
    row = MailOutbox.objects.filter(recipient=user.email).latest("created_at")
    wait_for(lambda: MailOutbox.objects.filter(pk=row.pk, status="SENT").exists())
    row.refresh_from_db()
    assert row.encrypted_payload == ""
    print(json.dumps({"production_https_csrf_cookies_private_storage_smtp": "passed"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["init", "tls", "http", "probe"])
    stage = parser.parse_args().stage
    {"init": initialize, "tls": tls_clients, "http": http_smoke, "probe": probe}[
        stage
    ]()
