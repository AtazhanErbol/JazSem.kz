from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.ai.models import AIJob, DocumentChunk, SourceDocument


def source(world, status="COMPLETED"):
    result = SourceDocument.objects.create(
        course=world["course"],
        uploaded_by=world["teacher"],
        filename="lesson.txt",
        mime_type="text/plain",
        size=12,
        file=SimpleUploadedFile("lesson.txt", b"Lesson text."),
        processing_status=status,
    )
    if status == "COMPLETED":
        DocumentChunk.objects.create(
            document=result, page_number=1, chunk_index=0, content="Lesson text."
        )
    return result


def configured(settings):
    cache.clear()
    settings.AI_ENABLED = True
    settings.OPENAI_API_KEY = "fake-never-called"
    settings.OPENAI_MODEL = "fake"
    settings.AI_INPUT_PRICE = settings.AI_OUTPUT_PRICE = "1"


@pytest.mark.django_db(transaction=True)
def test_broker_loss_after_commit_does_not_turn_accepted_job_into_500(world, client_for, settings):
    configured(settings)
    document = source(world)
    with (
        patch("apps.ai.views.require_worker"),
        patch("apps.ai.tasks.generate_course.delay", side_effect=OSError("offline")),
    ):
        response = client_for(world["teacher"]).post(
            "/api/v1/ai-jobs/",
            {
                "course": str(world["course"].pk),
                "weeks": 1,
                "language": "ru",
                "sources": [str(document.pk)],
            },
            format="json",
        )
    assert response.status_code == 202
    job = AIJob.objects.get()
    assert job.status == "QUEUED"
    assert job.delivery.status == "PENDING"


def test_failed_source_does_not_block_explicit_completed_selection(world, client_for, settings):
    configured(settings)
    good = source(world)
    source(world, "FAILED")
    with patch("apps.ai.views.require_worker"):
        response = client_for(world["teacher"]).post(
            "/api/v1/ai-jobs/",
            {
                "course": str(world["course"].pk),
                "weeks": 1,
                "language": "kk",
                "sources": [str(good.pk)],
            },
            format="json",
        )
    assert response.status_code == 202
    job = AIJob.objects.get()
    assert job.source_snapshot[0]["text"] == "Lesson text."


def test_source_can_be_excluded_without_deleting_citations(world, client_for):
    document = source(world)
    response = client_for(world["teacher"]).post(f"/api/v1/sources/{document.pk}/exclude/")
    assert response.status_code == 200
    document.refresh_from_db()
    assert document.excluded and document.chunks.count() == 1


def test_dispatch_failure_is_durable_and_retry_keeps_identity(world, client_for, settings):
    from django.utils import timezone

    from apps.ai.delivery import dispatch
    from apps.ai.jobs import create_job

    configured(settings)
    document = source(world)
    job = create_job(
        world["teacher"], world["course"], {"weeks": 1}, "request", sources=[document.pk]
    )
    identity = job.delivery.pk
    with patch(
        "apps.ai.tasks.generate_course.apply_async", side_effect=OSError("secret broker URL")
    ):
        dispatch()
    job.delivery.refresh_from_db()
    assert job.delivery.status == "PENDING" and job.delivery.error_code == "BROKER_UNAVAILABLE"
    assert job.delivery.next_retry_at > timezone.now()
    job.delivery.next_retry_at = timezone.now()
    job.delivery.save()
    with patch("apps.ai.tasks.generate_course.apply_async") as send:
        dispatch()
    assert send.call_args.kwargs["task_id"] == str(identity)
    job.delivery.refresh_from_db()
    assert job.delivery.status == "SENT"


def test_paid_call_crash_is_not_replayed_and_reservation_is_retained(world, settings):
    from datetime import timedelta

    from django.utils import timezone

    from apps.ai.budget import reserve_budget
    from apps.ai.delivery import reconcile
    from apps.ai.jobs import create_job
    from apps.ai.models import AIBudgetDay, TaskDelivery
    from apps.ai.tasks import generate_course

    configured(settings)
    settings.AI_DAILY_BUDGET_USD = "1"
    document = source(world)
    job = create_job(
        world["teacher"],
        world["course"],
        {"weeks": 1, "assignments": True, "tests": False},
        "request",
        sources=[document.pk],
    )

    def killed(*args):
        reserve_budget({}, {}, 100)
        raise SystemExit("simulated hard kill")

    with patch("apps.ai.tasks.OpenAIProvider.generate_course", side_effect=killed) as provider:
        with pytest.raises(SystemExit):
            generate_course(str(job.pk))
        reserved = AIBudgetDay.objects.get().reserved_usd
        assert reserved > 0
        TaskDelivery.objects.filter(job=job).update(
            lease_until=timezone.now() - timedelta(seconds=1)
        )
        reconcile()
        generate_course(str(job.pk))
    assert provider.call_count == 1
    job.refresh_from_db()
    assert job.status == "FAILED" and job.error == "PROVIDER_OUTCOME_UNCERTAIN"
    assert AIBudgetDay.objects.get().reserved_usd == reserved
    from apps.ai.models import AIUsageLog

    assert AIUsageLog.objects.get(job=job).status == "UNCERTAIN"


def test_cancellation_wins_over_late_provider_and_cost_is_recorded(world, client_for, settings):
    from types import SimpleNamespace

    from apps.ai.jobs import create_job
    from apps.ai.models import AICourseDraft, AIUsageLog
    from apps.ai.schema import CourseDraft
    from apps.ai.tasks import generate_course
    from tests.test_auth_ai import draft_data

    configured(settings)
    document = source(world)
    chunk = document.chunks.get()
    job = create_job(
        world["teacher"],
        world["course"],
        {"weeks": 1, "assignments": True, "tests": False},
        "request",
        sources=[document.pk],
    )

    def response(*args):
        assert (
            client_for(world["teacher"]).post(f"/api/v1/ai-jobs/{job.pk}/cancel/").status_code
            == 200
        )
        return CourseDraft.model_validate(draft_data(chunk)), SimpleNamespace(
            input_tokens=10, output_tokens=20
        )

    with patch("apps.ai.tasks.OpenAIProvider.generate_course", side_effect=response) as provider:
        generate_course(str(job.pk))
        generate_course(str(job.pk))
    job.refresh_from_db()
    assert job.status == "CANCELLED" and provider.call_count == 1
    assert not AICourseDraft.objects.filter(job=job).exists()
    assert AIUsageLog.objects.get(job=job).input_tokens == 10


def test_snapshot_is_used_and_duplicate_delivery_does_not_generate_twice(world, settings):
    from types import SimpleNamespace

    from apps.ai.jobs import create_job
    from apps.ai.schema import CourseDraft
    from apps.ai.tasks import generate_course
    from tests.test_auth_ai import draft_data

    configured(settings)
    document = source(world)
    chunk = document.chunks.get()
    job = create_job(
        world["teacher"],
        world["course"],
        {"weeks": 1, "assignments": True, "tests": False},
        "request",
        sources=[document.pk],
    )
    document.excluded = True
    document.save()
    document.chunks.update(content="Later database change")
    with patch(
        "apps.ai.tasks.OpenAIProvider.generate_course",
        return_value=(
            CourseDraft.model_validate(draft_data(chunk)),
            SimpleNamespace(input_tokens=10, output_tokens=20),
        ),
    ) as provider:
        generate_course(str(job.pk))
        generate_course(str(job.pk))
    assert provider.call_count == 1
    assert provider.call_args.args[0][0]["text"] == "Lesson text."
    job.refresh_from_db()
    assert job.status == "COMPLETED"


def test_text_limit_stops_consuming_extraction_stream(world, settings):
    from apps.ai.tasks import extract_document

    document = source(world, "QUEUED")
    settings.AI_MAX_SOURCE_CHARS = 10

    visited = []

    def pages(*args):
        visited.append(1)
        yield 1, "x" * 51
        visited.append(2)
        yield 2, "unexpected"

    with patch("apps.ai.tasks.extract_pages", side_effect=pages):
        extract_document(str(document.pk))
    document.refresh_from_db()
    assert document.processing_status == "FAILED" and not document.chunks.exists()
    assert visited == [1]
