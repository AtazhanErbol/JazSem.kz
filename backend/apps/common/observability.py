"""Bounded, non-PII operational counters. Redis failure never fails HTTP work."""

import logging
import os
import time

from celery.signals import heartbeat_sent, task_prerun
from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.db.models import Count, Min
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import AdminReady

BUCKETS = [100, 250, 500, 1000, 2500, 5000]
log = logging.getLogger("operations")


def increment(key):
    cache.add(key, 0, timeout=600)
    cache.incr(key)


def observe_http(status, duration_ms):
    try:
        prefix = f"ops:http:{int(time.time() // 60)}:"
        increment(prefix + "requests")
        if status >= 500:
            increment(prefix + "5xx")
        if status == 429:
            increment(prefix + "429")
        for boundary in BUCKETS:
            if duration_ms <= boundary:
                increment(prefix + str(boundary))
                break
        else:
            increment(prefix + "slow")
    except Exception:
        log.warning("metrics_cache_unavailable")


@heartbeat_sent.connect
def worker_pulse(**kwargs):
    try:
        cache.set("ops:worker:" + os.environ.get("WORKER_ROLE", "all"), time.time(), timeout=180)
    except Exception:
        log.warning("worker_heartbeat_cache_unavailable")


@task_prerun.connect
def task_started(task_id=None, task=None, **kwargs):
    # Arguments are deliberately excluded (mail/document payloads may be private).
    log.info("task_started", extra={"task_id": task_id, "task_name": task.name if task else None})


def worker_freshness():
    roles = settings.REQUIRED_WORKER_ROLES
    pulses = cache.get_many(["ops:worker:" + role for role in roles])
    return {
        role: max(0, time.time() - pulses["ops:worker:" + role])
        if "ops:worker:" + role in pulses
        else None
        for role in roles
    }


def storage_ready():
    if not settings.STORAGE_PROBE_KEY:
        return None
    value = cache.get("ops:storage")
    if value is None:
        try:
            value = default_storage.exists(settings.STORAGE_PROBE_KEY)
        except Exception:
            value = False
        cache.set("ops:storage", value, timeout=15)
    return value


def queue(model, statuses):
    pending = model.objects.filter(status__in=statuses)
    oldest = pending.aggregate(oldest=Min("created_at"))["oldest"]
    return {
        "counts": dict(
            model.objects.values("status")
            .annotate(total=Count("pk"))
            .values_list("status", "total")
        ),
        "oldest_pending_seconds": max(0, (timezone.now() - oldest).total_seconds())
        if oldest
        else 0,
    }


class QueueOutput(serializers.Serializer):
    counts = serializers.DictField(child=serializers.IntegerField())
    oldest_pending_seconds = serializers.FloatField()


class OperationsOutput(serializers.Serializer):
    window_seconds = serializers.IntegerField()
    http = serializers.DictField(child=serializers.IntegerField())
    latency_buckets_ms = serializers.ListField(child=serializers.IntegerField())
    workers = serializers.DictField(child=serializers.FloatField(allow_null=True))
    storage_ready = serializers.BooleanField(allow_null=True)
    mail = QueueOutput()
    background = QueueOutput()


class OperationsView(APIView):
    permission_classes = [AdminReady]
    serializer_class = OperationsOutput

    def get(self, request):
        from apps.ai.models import TaskDelivery
        from apps.notifications.models import MailOutbox

        names = ["requests", "5xx", "429", *map(str, BUCKETS), "slow"]
        minute = int(time.time() // 60)
        counters = cache.get_many(
            [f"ops:http:{slot}:{name}" for slot in range(minute - 4, minute + 1) for name in names]
        )
        return Response(
            {
                "window_seconds": 300,
                "http": {
                    name: sum(
                        counters.get(f"ops:http:{slot}:{name}", 0)
                        for slot in range(minute - 4, minute + 1)
                    )
                    for name in names
                },
                "latency_buckets_ms": BUCKETS,
                "workers": worker_freshness(),
                "storage_ready": storage_ready(),
                "mail": queue(MailOutbox, ["PENDING", "RETRY", "SENDING"]),
                "background": queue(TaskDelivery, ["PENDING", "DISPATCHING", "SENT", "RUNNING"]),
            }
        )
