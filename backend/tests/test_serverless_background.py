from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.common.models import RuntimeState
from apps.common.serverless import publish, schedule_next
from apps.common.tasks import expire_one, maintenance_tick
from apps.notifications.models import MailOutbox
from apps.notifications.services import queue_mail
from apps.notifications.tasks import flush_mail
from apps.testing.services import start


def test_native_queue_delay_does_not_use_celery_eta_or_countdown():
    task = Mock()
    connection = Mock()
    with patch("config.celery.app.connection_for_write") as connect:
        connect.return_value.__enter__.return_value = connection
        publish(task, ["synthetic"], delay=3600, key="timer-id", queue="heavy")
    assert connect.call_args.kwargs["transport_options"]["delay"] == 3600
    assert connect.call_args.kwargs["transport_options"]["use_task_id_as_idempotency_key"]
    assert task.apply_async.call_args.kwargs == {
        "args": ["synthetic"],
        "task_id": "timer-id",
        "queue": "heavy",
        "connection": connection,
        "retry": False,
    }


def test_immediate_batches_do_not_deduplicate_away_remaining_work(settings):
    settings.BACKGROUND_MODE = "vercel"
    with patch("apps.common.serverless.publish") as sent:
        schedule_next(Mock(), timezone.now(), prefix="mail")
    assert sent.call_args.kwargs["key"] is None


def test_long_timers_checkpoint_within_retention_and_use_distinct_keys(settings):
    settings.BACKGROUND_MODE = "vercel"
    due = timezone.now() + timedelta(days=3)
    with patch("apps.common.serverless.publish") as sent:
        schedule_next(Mock(), due, prefix="exam")
    assert sent.call_args.kwargs["delay"] == 23 * 3600


@pytest.mark.django_db
def test_serverless_mail_drains_more_than_one_bounded_batch(world, settings, mailoutbox):
    for n in range(12):
        queue_mail(world["student"], f"Test {n}", "Synthetic mail")
    settings.BACKGROUND_MODE = "vercel"
    with patch("apps.common.serverless.publish") as sent:
        flush_mail()
        assert MailOutbox.objects.filter(status="SENT").count() == 5
        assert sent.call_args.kwargs["key"] is None
        flush_mail()
        flush_mail()
    assert sum(message.subject.startswith("Test ") for message in mailoutbox) == 12
    assert not MailOutbox.objects.exclude(status="SENT").exists()


@pytest.mark.django_db
def test_stale_deployment_cannot_keep_a_timer_chain_alive():
    RuntimeState.objects.create(name="scheduler", deployment="current", last_tick=timezone.now())
    with patch("apps.common.serverless.publish") as sent:
        maintenance_tick(1, "old")
    sent.assert_not_called()


@pytest.mark.django_db
def test_maintenance_queues_successor_before_current_work(world, settings):
    settings.DIRECT_UPLOADS_ENABLED = False
    RuntimeState.objects.create(name="scheduler", deployment="current")
    order = []
    with (
        patch(
            "apps.common.serverless.publish", side_effect=lambda *a, **k: order.append("successor")
        ),
        patch(
            "apps.notifications.tasks.deadline_reminders",
            side_effect=lambda: order.append("deadlines"),
        ),
    ):
        maintenance_tick(1, "current")
    assert order[:2] == ["successor", "deadlines"]
    assert RuntimeState.objects.get(name="scheduler").last_tick is not None


@pytest.mark.django_db
def test_event_driven_exam_expiry_preserves_idempotent_grading(world):
    attempt = start(world["test"], world["student"])
    attempt.expires_at = timezone.now() - timedelta(seconds=1)
    attempt.save()
    expire_one(str(attempt.pk))
    expire_one(str(attempt.pk))
    attempt.refresh_from_db()
    assert attempt.status == "EXPIRED"
    assert attempt.score == 0


def test_queue_health_failure_is_not_reported_as_available(settings):
    from django.core.cache import cache

    from apps.common.background import worker_available

    settings.BACKGROUND_MODE = "vercel"
    settings.CELERY_TASK_ALWAYS_EAGER = False
    cache.delete("ops:vercel-workers-ready")
    with patch("apps.common.serverless.publish", side_effect=OSError("synthetic")):
        assert worker_available() is False


def test_timer_activation_failure_keeps_completed_business_response(settings):
    from django.http import JsonResponse
    from django.test import RequestFactory

    from apps.common.middleware import RequestIDMiddleware

    settings.BACKGROUND_MODE = "vercel"
    request = RequestFactory().post("/api/v1/materials/")
    with patch("apps.common.serverless.ensure_runtime", side_effect=OSError("synthetic")):
        response = RequestIDMiddleware(lambda _: JsonResponse({"saved": True}, status=201))(request)
    assert response.status_code == 201


@pytest.mark.django_db
def test_noncanonical_deployment_cannot_activate_old_timers(settings, monkeypatch):
    from django.core.cache import cache
    from django.test import RequestFactory

    from apps.common.serverless import ensure_runtime

    settings.BACKGROUND_MODE = "vercel"
    settings.FRONTEND_URL = "https://canonical.example.test"
    settings.ALLOWED_HOSTS = ["old.example.test"]
    monkeypatch.setenv("VERCEL_DEPLOYMENT_ID", "old-deployment")
    cache.delete("ops:runtime-active:old-deployment")
    RuntimeState.objects.create(name="scheduler", deployment="current", last_tick=timezone.now())
    request = RequestFactory().get("/ready/", HTTP_HOST="old.example.test")
    with pytest.raises(RuntimeError):
        ensure_runtime(request)
    assert RuntimeState.objects.get(name="scheduler").deployment == "current"
