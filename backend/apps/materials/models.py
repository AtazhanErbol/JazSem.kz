import uuid
from pathlib import Path

from django.db import models

from apps.common.models import Entity


def private_name(instance, filename):
    return f"private/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class Material(Entity):
    topic = models.ForeignKey("courses.Topic", on_delete=models.CASCADE, related_name="materials")
    title = models.CharField(max_length=240)
    type = models.CharField(max_length=20, default="TEXT")
    file = models.FileField(upload_to=private_name, blank=True)
    content = models.TextField(blank=True)
    external_url = models.URLField(blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "created_at"]
