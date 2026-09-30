"""DB outbox for extraction/generation. All business transitions lock Course first."""

import uuid
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.courses.models import Course

from .models import AIJob, SourceDocument, TaskDelivery

TERMINAL = ["DONE", "FAILED", "CANCELLED"]
LEASE_SECONDS = 600  # exceeds the Celery hard limit of 540s


def lock_course(delivery):
    course_id = (
        (AIJob.objects if delivery.job_id else SourceDocument.objects)
        .values_list("course_id", flat=True)
        .get(pk=delivery.job_id or delivery.source_id)
    )
    Course.objects.select_for_update().get(pk=course_id)


def finish_target(delivery, status, error=""):
    if delivery.job_id:
        AIJob.objects.filter(pk=delivery.job_id, status__in=["QUEUED", "PROCESSING"]).update(
            status=status,
            error=error,
            current_step=status,
            finished_at=timezone.now(),
        )
    else:
        SourceDocument.objects.filter(pk=delivery.source_id).exclude(
            processing_status="COMPLETED"
        ).update(processing_status=status, error=error)


def reconcile():
    now = timezone.now()
    ids = TaskDelivery.objects.filter(
        status__in=["DISPATCHING", "SENT", "RUNNING"], lease_until__lte=now
    ).values_list("pk", flat=True)
    for pk in list(ids[:100]):
        with transaction.atomic():
            row = TaskDelivery.objects.get(pk=pk)
            lock_course(row)
            row = TaskDelivery.objects.select_for_update().get(pk=pk)
            if row.status in TERMINAL or not row.lease_until or row.lease_until > now:
                continue
            uncertain = (
                row.job_id
                and AIJob.objects.filter(pk=row.job_id, provider_started_at__isnull=False).exists()
            )
            terminal = uncertain or row.executions >= 3 or row.attempts >= 5
            row.error_code = "PROVIDER_OUTCOME_UNCERTAIN" if uncertain else "WORKER_LEASE_EXPIRED"
            row.status = "FAILED" if terminal else "PENDING"
            row.lease_token = row.lease_until = None
            row.next_retry_at = now
            row.save()
            if terminal:
                finish_target(row, "FAILED", row.error_code)
            elif row.job_id:
                AIJob.objects.filter(pk=row.job_id, status="PROCESSING").update(
                    status="QUEUED", current_step="RECOVERING"
                )
            else:
                SourceDocument.objects.filter(
                    pk=row.source_id, processing_status="PROCESSING"
                ).update(processing_status="QUEUED")


def dispatch():
    from .tasks import extract_document, generate_course

    reconcile()
    due = TaskDelivery.objects.filter(status="PENDING").filter(
        Q(next_retry_at=None) | Q(next_retry_at__lte=timezone.now())
    )
    for pk in list(due.order_by("created_at", "pk").values_list("pk", flat=True)[:100]):
        with transaction.atomic():
            row = TaskDelivery.objects.select_for_update().get(pk=pk)
            if row.status != "PENDING" or (
                row.next_retry_at and row.next_retry_at > timezone.now()
            ):
                continue
            row.status = "DISPATCHING"
            row.attempts += 1
            row.lease_token = uuid.uuid4()
            row.lease_until = timezone.now() + timedelta(seconds=30)
            row.save()
        owned = TaskDelivery.objects.filter(
            pk=pk, status="DISPATCHING", lease_token=row.lease_token
        )
        try:
            task = generate_course if row.job_id else extract_document
            task.apply_async(
                args=[str(row.job_id or row.source_id)], task_id=str(row.pk), retry=False
            )
        except Exception:
            # No exception text: broker URLs may contain credentials.
            with transaction.atomic():
                lock_course(row)
                terminal = row.attempts >= 5
                changed = owned.update(
                    status="FAILED" if terminal else "PENDING",
                    error_code="BROKER_UNAVAILABLE",
                    lease_token=None,
                    lease_until=None,
                    next_retry_at=timezone.now()
                    + timedelta(seconds=min(300, 5 * 2 ** (row.attempts - 1))),
                )
                if changed and terminal:
                    finish_target(row, "FAILED", "BROKER_UNAVAILABLE")
        else:
            # The consumer may have already claimed/completed this row.
            owned.update(
                status="SENT",
                lease_token=None,
                lease_until=timezone.now() + timedelta(seconds=LEASE_SECONDS),
                error_code="",
            )


@transaction.atomic
def claim(*, job=None, source=None):
    obj = job or source
    Course.objects.select_for_update().get(pk=obj.course_id)
    obj.refresh_from_db()
    state = obj.status if job else obj.processing_status
    if state != "QUEUED":
        return None
    row, _ = TaskDelivery.objects.get_or_create(job=job, source=source)
    row = TaskDelivery.objects.select_for_update().get(pk=row.pk)
    if row.status in [*TERMINAL, "RUNNING"]:
        return None
    row.status = "RUNNING"
    row.executions += 1
    row.lease_token = uuid.uuid4()
    row.heartbeat_at = timezone.now()
    row.lease_until = timezone.now() + timedelta(seconds=LEASE_SECONDS)
    row.save()
    if job:
        AIJob.objects.filter(pk=job.pk).update(
            status="PROCESSING",
            started_at=timezone.now(),
            progress=10,
            current_step="VALIDATING_SOURCES",
        )
    else:
        SourceDocument.objects.filter(pk=source.pk).update(processing_status="PROCESSING", error="")
    return row


def heartbeat(row):
    return TaskDelivery.objects.filter(
        pk=row.pk, status="RUNNING", lease_token=row.lease_token
    ).update(
        heartbeat_at=timezone.now(), lease_until=timezone.now() + timedelta(seconds=LEASE_SECONDS)
    )


def owned(row):
    return (
        TaskDelivery.objects.select_for_update()
        .filter(pk=row.pk, status="RUNNING", lease_token=row.lease_token)
        .first()
    )


def complete(row):
    row.status = "DONE"
    row.lease_token = row.lease_until = None
    row.error_code = ""
    row.save()


@transaction.atomic
def failed(row, code):
    lock_course(row)
    row = owned(row)
    if row is None:
        return
    row.status = "FAILED"
    row.error_code = code
    row.lease_token = row.lease_until = None
    row.save()
    finish_target(row, "FAILED", code)
