import pytest

from config.vercel_proxy import VercelProxy


def test_vercel_adapter_cannot_start_outside_vercel(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    with pytest.raises(RuntimeError, match="Vercel runtime"):
        VercelProxy(lambda environ, start_response: [])


def test_adapter_preserves_https_and_real_client_in_django(monkeypatch, settings):
    import json

    from django.core.handlers.wsgi import WSGIRequest
    from django.http import JsonResponse
    from django.test import RequestFactory

    from apps.common.proxy import TrustedProxyMiddleware

    monkeypatch.setenv("VERCEL", "1")
    settings.TRUSTED_PROXY_CIDRS = ["127.0.0.1/32"]
    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    def application(environ, start_response):
        response = TrustedProxyMiddleware(
            lambda request: JsonResponse(
                {"secure": request.is_secure(), "ip": request.META["REMOTE_ADDR"]}
            )
        )(WSGIRequest(environ))
        start_response("200 OK", [])
        return [response.content]

    request = RequestFactory().get(
        "/health/",
        HTTP_X_FORWARDED_FOR="198.51.100.7",
        HTTP_X_FORWARDED_PROTO="https",
        HTTP_X_VERIFIED_CLIENT_IP="203.0.113.99",
    )
    response = VercelProxy(application)(request.environ, lambda status, headers: None)
    assert json.loads(b"".join(response)) == {"secure": True, "ip": "198.51.100.7"}


@pytest.mark.parametrize("client_ip", ["198.51.100.7", "2001:db8::7"])
def test_edge_address_replaces_forged_private_proxy_headers(monkeypatch, client_ip):
    monkeypatch.setenv("VERCEL", "1")
    captured = {}

    def application(environ, start_response):
        captured.update(environ)
        start_response("200 OK", [])
        return [b"ok"]

    environ = {
        "REMOTE_ADDR": "192.0.2.99",
        "HTTP_HOST": "jazsem.example.test",
        "HTTP_X_FORWARDED_FOR": client_ip,
        "HTTP_X_FORWARDED_PROTO": "https",
        "HTTP_X_VERIFIED_CLIENT_IP": "203.0.113.99",
        "HTTP_X_REAL_IP": "203.0.113.99",
        "HTTP_X_FORWARDED_HOST": "attacker.example.test",
        "HTTP_FORWARDED": "for=203.0.113.99;proto=http",
    }
    assert VercelProxy(application)(environ, lambda status, headers: None) == [b"ok"]
    assert captured["REMOTE_ADDR"] == "127.0.0.1"
    assert captured["HTTP_X_VERIFIED_CLIENT_IP"] == client_ip
    assert captured["HTTP_X_FORWARDED_PROTO"] == "https"
    assert captured["HTTP_HOST"] == "jazsem.example.test"
    assert not any(
        name in captured
        for name in (
            "HTTP_X_FORWARDED_FOR",
            "HTTP_X_REAL_IP",
            "HTTP_X_FORWARDED_HOST",
            "HTTP_FORWARDED",
        )
    )


@pytest.mark.parametrize(
    "address,protocol",
    [
        ("", "https"),
        ("invalid", "https"),
        ("198.51.100.1, 203.0.113.1", "https"),
        ("198.51.100.1", ""),
        ("198.51.100.1", "https,http"),
    ],
)
def test_invalid_edge_headers_fail_before_django(monkeypatch, address, protocol):
    monkeypatch.setenv("VERCEL", "1")
    calls = []

    def application(environ, start_response):
        pytest.fail("Invalid edge requests must not reach Django")

    result = VercelProxy(application)(
        {"HTTP_X_FORWARDED_FOR": address, "HTTP_X_FORWARDED_PROTO": protocol},
        lambda status, headers: calls.append((status, headers)),
    )
    assert calls[0][0] == "400 Bad Request"
    assert b"invalid_proxy" in b"".join(result)
