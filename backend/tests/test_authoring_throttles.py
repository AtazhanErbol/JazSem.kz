from types import SimpleNamespace

import pytest
from django.core.cache import cache
from rest_framework.test import APIRequestFactory

from apps.common.throttles import AuthoringScopedRateThrottle


@pytest.fixture(autouse=True)
def isolated_throttle_cache(monkeypatch):
    cache.clear()
    monkeypatch.setattr(
        AuthoringScopedRateThrottle,
        "THROTTLE_RATES",
        {
            "upload": "30/hour",
            "upload_grant": "30/hour",
            "staff_upload": "120/hour",
            "staff_upload_grant": "240/hour",
            "auth": "10/min",
            "reset": "5/hour",
            "ai": "6/hour",
        },
    )
    yield
    cache.clear()


def allowed(user, scope):
    request = APIRequestFactory().post("/api/v1/attachments/", {})
    request.user = user
    return AuthoringScopedRateThrottle().allow_request(
        request, SimpleNamespace(throttle_scope=scope)
    )


@pytest.mark.parametrize("role", ["ADMIN", "TEACHER"])
@pytest.mark.parametrize("scope,limit", [("upload", 120), ("upload_grant", 240)])
def test_course_authors_can_upload_a_semester_but_remain_rate_limited(role, scope, limit):
    user = SimpleNamespace(pk=1, role=role, is_authenticated=True)
    assert all(allowed(user, scope) for _ in range(limit))
    assert not allowed(user, scope)


@pytest.mark.parametrize("role", ["STUDENT", "UNKNOWN", "TEACHER"])
@pytest.mark.parametrize("scope", ["upload", "upload_grant"])
def test_students_and_unauthenticated_roles_keep_the_original_budget(role, scope):
    user = SimpleNamespace(pk=2, role=role, is_authenticated=role != "TEACHER", is_staff=True)
    assert all(allowed(user, scope) for _ in range(30))
    assert not allowed(user, scope)


@pytest.mark.parametrize("role", ["ADMIN", "TEACHER", "STUDENT"])
@pytest.mark.parametrize("scope,limit", [("auth", 10), ("reset", 5), ("ai", 6)])
def test_other_security_and_ai_budgets_do_not_change(role, scope, limit):
    user = SimpleNamespace(pk=3, role=role, is_authenticated=True)
    assert all(allowed(user, scope) for _ in range(limit))
    assert not allowed(user, scope)


def test_anonymous_requests_cannot_claim_the_staff_budget():
    assert all(allowed(None, "upload") for _ in range(30))
    assert not allowed(None, "upload")
