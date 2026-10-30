from datetime import timedelta
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.ai import delivery
from apps.ai.jobs import create_job
from apps.ai.models import AICourseDraft
from apps.ai.provider import OpenAIProvider
from apps.ai.schema import CourseDraft
from apps.ai.tasks import extract_document, generate_course
from tests.test_ai_recovery import configured, source
from tests.test_auth_ai import draft_data


@pytest.mark.parametrize("operation", ["generate_course", "regenerate_topic"])
def test_provider_waits_without_timeout_and_preserves_model(settings, operation):
    settings.OPENAI_API_KEY = "test-only-never-sent"
    settings.OPENAI_MODEL = "gpt-5-nano"
    settings.OPENAI_REASONING_EFFORT = "low"
    result = SimpleNamespace(output_parsed=object(), usage=object())
    with (
        patch("apps.ai.provider.reserve_budget"),
        patch("apps.ai.provider.settle_budget"),
        patch("apps.ai.provider.OpenAI") as client,
    ):
        client.return_value.responses.parse.return_value = result
        provider = OpenAIProvider()
        if operation == "generate_course":
            provider.generate_course([], {})
        else:
            provider.regenerate_topic([], {}, "Revise")
    assert client.call_args.kwargs == {
        "api_key": "test-only-never-sent",
        "timeout": None,
        "max_retries": 0,
    }
    request = client.return_value.responses.parse.call_args.kwargs
    assert request["model"] == "gpt-5-nano"
    assert request["reasoning"] == {"effort": "low"}


def test_worker_pool_and_ai_tasks_have_no_duration_limit(settings):
    from config.celery import app

    app.autodiscover_tasks(force=True)
    app.finalize()
    assert settings.CELERY_TASK_TIME_LIMIT is None
    assert settings.CELERY_TASK_SOFT_TIME_LIMIT is None
    for task in (extract_document, generate_course):
        assert task.time_limit == 0
        assert task.soft_time_limit == 0
    for name in settings.CELERY_TASK_ANNOTATIONS:
        task = app.tasks[name]
        assert task.time_limit == 600
        assert task.soft_time_limit == 540


@pytest.mark.parametrize("lost_ownership", [False, True])
def test_keep_alive_renews_during_blocking_work_and_stops(monkeypatch, lost_ownership):
    monkeypatch.setattr(delivery, "HEARTBEAT_SECONDS", 0.01)
    renewed = Event()

    def renew(row):
        renewed.set()
        return not lost_ownership

    with (
        patch.object(delivery, "heartbeat", side_effect=renew) as heartbeat,
        patch.object(delivery, "close_old_connections"),
        patch.object(delivery, "connection") as connection,
    ):
        row = SimpleNamespace(pk="unit-test")
        with delivery.keep_alive(row):
            assert renewed.wait(2), "Blocking work did not receive a heartbeat"
        count = heartbeat.call_count
        assert count >= 1
        if lost_ownership:
            assert count == 1
        connection.close.assert_called_once()


def test_long_generation_survives_reconciliation_without_duplicate_call(world, settings):
    configured(settings)
    document = source(world)
    chunk = document.chunks.get()
    job = create_job(
        world["teacher"],
        world["course"],
        {"weeks": 1, "assignments": True, "tests": False},
        "duration-test",
        sources=[document.pk],
    )
    later = timezone.now() + timedelta(hours=2)

    def long_response(*args):
        with patch("apps.ai.delivery.timezone.now", return_value=later):
            # Simulate a heartbeat after hours of provider processing, then run
            # the real reconciler against the renewed lease.
            job.delivery.refresh_from_db()
            assert delivery.heartbeat(job.delivery) == 1
            delivery.reconcile()
        job.refresh_from_db()
        assert job.status == "PROCESSING"
        return CourseDraft.model_validate(draft_data(chunk)), SimpleNamespace(
            input_tokens=10, output_tokens=20
        )

    with patch("apps.ai.tasks.OpenAIProvider.generate_course", side_effect=long_response) as call:
        generate_course(str(job.pk))
        generate_course(str(job.pk))
    job.refresh_from_db()
    assert job.status == "COMPLETED"
    assert call.call_count == 1
    assert AICourseDraft.objects.filter(job=job).count() == 1


@pytest.mark.parametrize("operation", ["generation", "extraction"])
def test_tasks_keep_lease_alive_while_provider_or_extraction_blocks(world, settings, operation):
    configured(settings)
    document = source(world, "QUEUED" if operation == "extraction" else "COMPLETED")
    entered = []

    from contextlib import contextmanager

    @contextmanager
    def keep_alive(row):
        entered.append(row.pk)
        try:
            yield
        finally:
            entered.pop()

    if operation == "extraction":

        def pages(*args):
            assert entered == [document.delivery.pk]
            yield 1, "Extracted lesson text."

        with (
            patch.object(delivery, "keep_alive", side_effect=keep_alive),
            patch("apps.ai.tasks.extract_pages", side_effect=pages),
        ):
            extract_document(str(document.pk))
        document.refresh_from_db()
        assert document.processing_status == "COMPLETED"
    else:
        chunk = document.chunks.get()
        job = create_job(
            world["teacher"],
            world["course"],
            {"weeks": 1, "assignments": True, "tests": False},
            "keep-alive-test",
            sources=[document.pk],
        )

        def response(*args):
            assert entered == [job.delivery.pk]
            return CourseDraft.model_validate(draft_data(chunk)), SimpleNamespace(
                input_tokens=10, output_tokens=20
            )

        with (
            patch.object(delivery, "keep_alive", side_effect=keep_alive),
            patch("apps.ai.tasks.OpenAIProvider.generate_course", side_effect=response),
        ):
            generate_course(str(job.pk))
        job.refresh_from_db()
        assert job.status == "COMPLETED"
    assert not entered


def test_queued_job_is_not_expired_while_heavy_worker_is_busy(world, settings):
    configured(settings)
    document = source(world)
    extracting = source(world, "QUEUED")
    running = delivery.claim(source=extracting)
    job = create_job(
        world["teacher"], world["course"], {"weeks": 1}, "queued", sources=[document.pk]
    )
    now = timezone.now()
    delivery.TaskDelivery.objects.filter(job=job).update(
        status="SENT", attempts=5, lease_until=now - timedelta(seconds=1)
    )
    delivery.reconcile()
    job.refresh_from_db()
    waiting = delivery.TaskDelivery.objects.get(job=job)
    assert job.status == "QUEUED" and waiting.status == "SENT"
    assert waiting.attempts == 5 and waiting.lease_until > now
    # Once ownership is no longer alive, the normal loss recovery still runs.
    delivery.TaskDelivery.objects.filter(pk=running.pk).update(status="DONE")
    delivery.TaskDelivery.objects.filter(job=job).update(lease_until=now - timedelta(seconds=1))
    delivery.reconcile()
    job.refresh_from_db()
    assert job.status == "FAILED"


@pytest.mark.django_db(transaction=True)
def test_background_thread_renews_real_lease_during_provider_call(world, settings, monkeypatch):
    configured(settings)
    monkeypatch.setattr(delivery, "HEARTBEAT_SECONDS", 0.01)
    document = source(world)
    chunk = document.chunks.get()
    job = create_job(
        world["teacher"],
        world["course"],
        {"weeks": 1, "assignments": True, "tests": False},
        "thread-test",
        sources=[document.pk],
    )
    renewed = Event()
    real_heartbeat = delivery.heartbeat

    def heartbeat(row):
        result = real_heartbeat(row)
        if result:
            renewed.set()
        return result

    def response(*args):
        assert renewed.wait(2), "Provider waited without a DB heartbeat"
        row = delivery.TaskDelivery.objects.get(job=job)
        job.refresh_from_db()
        assert row.heartbeat_at > job.started_at
        return CourseDraft.model_validate(draft_data(chunk)), SimpleNamespace(
            input_tokens=10, output_tokens=20
        )

    with (
        patch.object(delivery, "heartbeat", side_effect=heartbeat),
        patch("apps.ai.tasks.OpenAIProvider.generate_course", side_effect=response),
    ):
        generate_course(str(job.pk))
    job.refresh_from_db()
    assert job.status == "COMPLETED"
