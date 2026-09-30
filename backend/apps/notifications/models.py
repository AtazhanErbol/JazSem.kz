from django.conf import settings
from django.db import models

from apps.common.models import Entity


class Notification(Entity):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    type = models.CharField(max_length=60)
    title = models.CharField(max_length=240)
    message = models.TextField(blank=True)
    link = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)
    dedupe_key = models.CharField(max_length=200, unique=True, null=True)


class MailOutbox(Entity):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        SENDING = "SENDING"
        RETRY = "RETRY"
        SENT = "SENT"
        FAILED = "FAILED"

    recipient = models.EmailField()
    encrypted_payload = models.TextField()
    sent_at = models.DateTimeField(null=True)
    attempts = models.PositiveIntegerField(default=0)
    cycle_attempts = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)
    next_retry_at = models.DateTimeField(null=True)
    lease_token = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    error_code = models.CharField(max_length=40, blank=True)

    class Meta(Entity.Meta):
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["PENDING", "SENDING", "RETRY", "SENT", "FAILED"]),
                name="mail_valid_status",
            ),
        ]
