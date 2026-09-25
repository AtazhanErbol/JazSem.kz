from celery import shared_task
from django.utils import timezone

from .models import TestAttempt
from .services import finalize


@shared_task
def expire_attempts():
    for attempt in TestAttempt.objects.filter(
        status="IN_PROGRESS", expires_at__lte=timezone.now()
    ).select_related("student")[:500]:
        finalize(attempt, attempt.student)
