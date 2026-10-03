import runpy

import pytest
from django.core.cache import cache
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.common.errors import exception_handler
from config.settings import base


@pytest.mark.parametrize(
    "configured",
    [[], ["http://localhost:5173"], ["https://campus.example.test", "http://127.0.0.1:5173"]],
)
def test_development_keeps_both_loopback_origins_without_changing_base(monkeypatch, configured):
    monkeypatch.setattr(base, "CSRF_TRUSTED_ORIGINS", configured)
    result = runpy.run_module("config.settings.development")
    assert set(result["CSRF_TRUSTED_ORIGINS"]) == {
        *configured,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }
    assert len(result["CSRF_TRUSTED_ORIGINS"]) == len(set(result["CSRF_TRUSTED_ORIGINS"]))
    assert base.CSRF_TRUSTED_ORIGINS == configured


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_login_and_profile_update_accept_both_local_frontend_names(world, settings, origin):
    cache.clear()
    settings.CSRF_TRUSTED_ORIGINS = runpy.run_module("config.settings.development")[
        "CSRF_TRUSTED_ORIGINS"
    ]
    client = APIClient(enforce_csrf_checks=True)
    token = client.get("/api/v1/auth/login/").json()["csrfToken"]
    response = client.post(
        "/api/v1/auth/login/",
        {"email": world["admin"].email, "password": "Example-pass-583!"},
        HTTP_ORIGIN=origin,
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 200
    response = client.patch(
        "/api/v1/auth/me/",
        {"first_name": "Updated name"},
        HTTP_ORIGIN=origin,
        HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
    )
    assert response.status_code == 200


def test_login_does_not_accept_an_untrusted_origin(world, settings):
    cache.clear()
    settings.CSRF_TRUSTED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
    client = APIClient(enforce_csrf_checks=True)
    token = client.get("/api/v1/auth/login/").json()["csrfToken"]
    response = client.post(
        "/api/v1/auth/login/",
        {"email": world["admin"].email, "password": "Example-pass-583!"},
        HTTP_ORIGIN="https://untrusted.example.test",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"
    assert "sessionid" not in client.cookies


def test_stale_csrf_rejects_profile_action_before_execution_and_refresh_recovers(world):
    cache.clear()
    client = APIClient(enforce_csrf_checks=True)
    old_token = client.get("/api/v1/auth/login/").json()["csrfToken"]
    assert (
        client.post(
            "/api/v1/auth/login/",
            {"email": world["admin"].email, "password": "Example-pass-583!"},
            HTTP_X_CSRFTOKEN=old_token,
        ).status_code
        == 200
    )
    original = world["admin"].first_name
    response = client.patch(
        "/api/v1/auth/me/", {"first_name": "Must not be saved"}, HTTP_X_CSRFTOKEN=old_token
    )
    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"
    assert "CSRF Failed:" not in response.json()["message"]
    world["admin"].refresh_from_db()
    assert world["admin"].first_name == original
    fresh = client.get("/api/v1/auth/login/").json()["csrfToken"]
    assert (
        client.patch(
            "/api/v1/auth/me/", {"first_name": "Saved once"}, HTTP_X_CSRFTOKEN=fresh
        ).status_code
        == 200
    )
    world["admin"].refresh_from_db()
    assert world["admin"].first_name == "Saved once"


def test_permission_errors_are_not_reported_as_csrf_errors():
    response = exception_handler(PermissionDenied("Course is private"), {})
    assert response.status_code == 403
    assert response.data["code"] == "permission_denied"
