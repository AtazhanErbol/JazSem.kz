import time
from unittest.mock import patch

from django.core.cache import cache

from apps.common.observability import observe_http, worker_pulse


def test_operations_are_private_aggregates(world, client_for, settings):
    cache.clear()
    settings.REQUIRED_WORKER_ROLES = ["short", "heavy"]
    observe_http(500, 800)
    observe_http(429, 30)
    with patch.dict("os.environ", {"WORKER_ROLE": "short"}):
        worker_pulse()
    for role in ["student", "teacher"]:
        assert client_for(world[role]).get("/api/v1/operations/").status_code == 403
    data = client_for(world["admin"]).get("/api/v1/operations/").json()
    assert data["http"]["5xx"] == 1 and data["http"]["429"] == 1
    assert data["workers"]["short"] < 2 and data["workers"]["heavy"] is None
    assert set(data["mail"]) == {"counts", "oldest_pending_seconds"}
    assert "recipient" not in str(data) and "password" not in str(data)


def test_readiness_separates_worker_and_storage_failures(world, client_for, settings):
    settings.REQUIRED_WORKER_ROLES = ["heavy"]
    client = client_for(world["admin"])
    cache.delete("ops:worker:heavy")
    with (
        patch("redis.Redis.ping", return_value=True),
        patch("config.urls.storage_ready", return_value=True),
    ):
        assert client.get("/ready/").status_code == 503
        cache.set("ops:worker:heavy", time.time())
        assert client.get("/ready/").status_code == 200
    with (
        patch("redis.Redis.ping", return_value=True),
        patch("config.urls.storage_ready", return_value=False),
    ):
        assert client.get("/ready/").json()["status"] == "storage_unavailable"
    assert client.get("/health/").status_code == 200


def test_metrics_cache_failure_does_not_break_http(world, client_for):
    with patch("apps.common.observability.cache.add", side_effect=ConnectionError()):
        assert client_for(world["student"]).get("/api/v1/auth/me/").status_code == 200
