"""Event-driven outbox dispatch and delayed timers; no sleeping worker processes."""

import logging
import math
import os
import time
import uuid
from urllib.parse import urlsplit

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

log = logging.getLogger("background")


def enabled():
    return settings.BACKGROUND_MODE == "vercel"


def publish(task, args=(), *, delay=0, key=None, queue=None):
    from config.celery import app

    # The broker's native delay schedules delivery without holding a Function
    # open, unlike Celery's ETA/countdown implementation on Vercel.
    options = {
        **app.conf.broker_transport_options,
        "delay": max(0, min(23 * 3600, math.ceil(delay))),
        "retention": 24 * 3600,
        "use_task_id_as_idempotency_key": key is not None,
    }
    with app.connection_for_write(transport_options=options) as connection:
        return task.apply_async(
            args=list(args),
            task_id=key or str(uuid.uuid4()),
            queue=queue,
            connection=connection,
            retry=False,
        )


def kick(kind):
    if not enabled():
        return

    def send():
        from apps.ai.tasks import dispatch_pending
        from apps.notifications.tasks import flush_mail

        marker = f"ops:kick:{kind}"
        try:
            if not cache.add(marker, 1, timeout=2):
                return
            publish(flush_mail if kind == "mail" else dispatch_pending)
        except Exception:
            # The database outbox is authoritative; maintenance recovers it.
            try:
                cache.delete(marker)
            except Exception:
                pass
            log.warning("outbox_kick_failed", extra={"kind": kind})

    transaction.on_commit(send)


def schedule_next(task, when, *, prefix, args=()):
    if enabled() and when is not None:
        delay = max(0, (when - timezone.now()).total_seconds())
        delay = min(23 * 3600, delay)
        slot = math.ceil((time.time() + delay) / 5)
        # Immediate batch continuations must remain distinct: reusing the same
        # key after processing a batch would drop the rest of the outbox.
        key = f"{prefix}-{slot}" if delay > 1 else None
        publish(task, args, delay=delay, key=key)


def schedule_expiry(attempt):
    if not enabled():
        return
    pk, expires_at = str(attempt.pk), attempt.expires_at

    def send():
        from apps.common.tasks import expire_one

        try:
            schedule_next(expire_one, expires_at, prefix=f"expire-{pk}", args=[pk])
        except Exception:
            log.warning("test_expiry_schedule_failed")

    transaction.on_commit(send)


def ensure_runtime(request):
    """Canonical alias activation prevents old previews restarting old timers."""
    if not enabled():
        return
    from apps.common.models import RuntimeState
    from apps.common.tasks import maintenance_tick

    deployment = os.environ.get("VERCEL_DEPLOYMENT_ID")
    if not deployment:
        raise RuntimeError("Missing Vercel deployment identity")
    active_marker = "ops:runtime-active:" + deployment
    if cache.get(active_marker):
        return
    state = RuntimeState.objects.filter(name="scheduler").first()
    if (
        state
        and state.deployment == deployment
        and state.last_tick
        and (timezone.now() - state.last_tick).total_seconds() < 75 * 60
    ):
        cache.set(active_marker, True, timeout=60)
        return
    if request.get_host() != urlsplit(settings.FRONTEND_URL).netloc:
        raise RuntimeError("Activate the runtime through its canonical alias")
    marker = "ops:runtime-start:" + deployment
    if cache.add(marker, 1, timeout=60):
        try:
            RuntimeState.objects.update_or_create(
                name="scheduler", defaults={"deployment": deployment, "last_tick": None}
            )
            publish(maintenance_tick, [int(time.time() // 3600), deployment])
        except Exception:
            cache.delete(marker)
            raise


def maybe_activate_runtime(request):
    if enabled():
        try:
            ensure_runtime(request)
        except Exception:
            # Readiness reports startup failures; do not turn an already
            # completed business action into an ambiguous failed HTTP result.
            log.warning("runtime_activation_pending")
