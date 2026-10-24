import uuid

from django.conf import settings
from django.db import models


class Entity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class UploadTicket(Entity):
    """Short-lived, single-use attachment permission, bound to one user/action."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    target = models.CharField(max_length=255)
    method = models.CharField(max_length=5)
    context_digest = models.CharField(max_length=64)
    field = models.CharField(max_length=16)
    filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=150)
    size = models.PositiveIntegerField()
    key = models.CharField(max_length=255, unique=True)
    expires_at = models.DateTimeField(db_index=True)
    consumed = models.BooleanField(default=False)


class RuntimeState(models.Model):
    """Fence timer chains belonging to an older Vercel deployment."""

    name = models.CharField(max_length=40, primary_key=True)
    deployment = models.CharField(max_length=200)
    last_tick = models.DateTimeField(null=True)
