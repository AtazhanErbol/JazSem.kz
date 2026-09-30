from django.core.cache import cache
from rest_framework.test import APIClient


def test_untrusted_peer_cannot_forge_https_or_verified_client(settings):
    from django.http import JsonResponse
    from django.test import RequestFactory

    from apps.common.proxy import TrustedProxyMiddleware

    settings.TRUSTED_PROXY_CIDRS = ["192.0.2.10/32"]
    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    request = RequestFactory().get(
        "/",
        REMOTE_ADDR="198.51.100.5",
        HTTP_X_FORWARDED_PROTO="https",
        HTTP_X_VERIFIED_CLIENT_IP="203.0.113.1",
    )
    response = TrustedProxyMiddleware(
        lambda r: JsonResponse({"secure": r.is_secure(), "ip": r.META["REMOTE_ADDR"]})
    )(request)
    assert b'"secure": false' in response.content
    assert b'"ip": "198.51.100.5"' in response.content


def test_forged_forwarded_address_cannot_bypass_login_limit(world):
    cache.clear()
    client = APIClient()
    for i in range(10):
        response = client.post(
            "/api/v1/auth/login/",
            {"email": "unknown@example.test", "password": "wrong"},
            REMOTE_ADDR="198.51.100.5",
            HTTP_X_FORWARDED_FOR=f"203.0.113.{i}",
        )
        assert response.status_code == 400
    response = client.post(
        "/api/v1/auth/login/",
        {"email": "unknown@example.test", "password": "wrong"},
        REMOTE_ADDR="198.51.100.5",
        HTTP_X_FORWARDED_FOR="203.0.113.100",
    )
    assert response.status_code == 429
    cache.clear()


def test_trusted_proxy_clients_do_not_share_one_login_limit(world, settings):
    settings.TRUSTED_PROXY_CIDRS = ["192.0.2.10/32"]
    cache.clear()
    client = APIClient()
    data = {"email": "unknown@example.test", "password": "wrong"}
    for _ in range(10):
        assert (
            client.post(
                "/api/v1/auth/login/",
                data,
                REMOTE_ADDR="192.0.2.10",
                HTTP_X_VERIFIED_CLIENT_IP="198.51.100.1",
            ).status_code
            == 400
        )
    assert (
        client.post(
            "/api/v1/auth/login/",
            data,
            REMOTE_ADDR="192.0.2.10",
            HTTP_X_VERIFIED_CLIENT_IP="198.51.100.2",
        ).status_code
        == 400
    )
    cache.clear()
