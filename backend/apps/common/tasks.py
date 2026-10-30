import time
from datetime import datetime
from datetime import timezone as dt_timezone

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone


@shared_task
def queue_health(role):
    if role not in {"short", "heavy"}:
        raise ValueError("Invalid worker role")
    if role == "heavy":
        from apps.ai.ocr import embedded_ready

        embedded_ready()
    cache.set("ops:worker:" + role, time.time(), timeout=180)
    return role


@shared_task
def expire_one(pk):
    from apps.common.serverless import schedule_expiry
    from apps.testing.models import TestAttempt
    from apps.testing.services import finalize

    attempt = (
        TestAttempt.objects.select_related("student").filter(pk=pk, status="IN_PROGRESS").first()
    )
    if not attempt:
        return
    if attempt.expires_at <= timezone.now():
        finalize(attempt, attempt.student)
    else:
        # Long exam limits can exceed the queue's retention period.
        schedule_expiry(attempt)


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3}, retry_backoff=True)
def maintenance_tick(slot, deployment):
    from apps.ai.models import TaskDelivery
    from apps.common.direct_uploads import cleanup_uploads
    from apps.common.models import RuntimeState
    from apps.common.serverless import kick, publish
    from apps.notifications.models import MailOutbox
    from apps.notifications.tasks import deadline_reminders
    from apps.testing.tasks import expire_attempts

    state = RuntimeState.objects.filter(name="scheduler", deployment=deployment)
    if not state.exists():
        return
    # Queue the successor before doing work. A crash cannot silently stop the
    # hourly chain; duplicate deliveries deduplicate the same successor ID.
    next_slot = max(slot + 1, int(time.time() // 3600) + 1)
    when = datetime.fromtimestamp(next_slot * 3600, tz=dt_timezone.utc)
    publish(
        maintenance_tick,
        [next_slot, deployment],
        delay=(when - timezone.now()).total_seconds(),
        key=f"maintenance-{deployment}-{next_slot}",
    )
    deadline_reminders()
    expire_attempts()
    cleanup_uploads()
    if TaskDelivery.objects.exclude(status__in=["DONE", "FAILED", "CANCELLED"]).exists():
        kick("ai")
    if MailOutbox.objects.filter(status__in=["PENDING", "RETRY", "SENDING"]).exists():
        kick("mail")
    state.update(last_tick=timezone.now())
