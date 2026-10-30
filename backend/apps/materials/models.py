import uuid
from pathlib import Path

from django.db import models
from django.utils import timezone

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
    mime_type = models.CharField(max_length=150, blank=True)
    size = models.PositiveIntegerField(null=True)
    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "created_at"]


class LearningAttachment(Entity):
    """Version-owned resources; storage objects remain immutable across clones."""

    class Kind(models.TextChoices):
        FILE = "FILE", "Document"
        VIDEO = "VIDEO", "Uploaded video"
        YOUTUBE = "YOUTUBE", "YouTube"

    topic = models.ForeignKey(
        "courses.Topic", null=True, blank=True, on_delete=models.CASCADE, related_name="attachments"
    )
    assignment = models.ForeignKey(
        "assignments.Assignment",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    test = models.ForeignKey(
        "testing.Test", null=True, blank=True, on_delete=models.CASCADE, related_name="attachments"
    )
    question = models.ForeignKey(
        "testing.Question",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.FILE)
    uploaded_at = models.DateTimeField(default=timezone.now)
    file = models.FileField(upload_to=private_name, blank=True)
    external_url = models.URLField(max_length=2048, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    mime_type = models.CharField(max_length=150, blank=True)
    size = models.PositiveBigIntegerField(null=True)
    order = models.PositiveIntegerField(default=0)

    @property
    def parent(self):
        return next(
            getattr(self, field)
            for field in ("topic", "assignment", "test", "question")
            if getattr(self, field + "_id")
        )

    class Meta:
        ordering = ["order", "created_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        topic__isnull=False,
                        assignment__isnull=True,
                        test__isnull=True,
                        question__isnull=True,
                    )
                    | models.Q(
                        topic__isnull=True,
                        assignment__isnull=False,
                        test__isnull=True,
                        question__isnull=True,
                    )
                    | models.Q(
                        topic__isnull=True,
                        assignment__isnull=True,
                        test__isnull=False,
                        question__isnull=True,
                    )
                    | models.Q(
                        topic__isnull=True,
                        assignment__isnull=True,
                        test__isnull=True,
                        question__isnull=False,
                    )
                ),
                name="attachment_exactly_one_parent",
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=["FILE", "VIDEO", "YOUTUBE"]),
                name="attachment_valid_kind",
            ),
        ]
