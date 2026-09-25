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
    recipient = models.EmailField()
    encrypted_payload = models.TextField()
    sent_at = models.DateTimeField(null=True)
    attempts = models.PositiveIntegerField(default=0)
