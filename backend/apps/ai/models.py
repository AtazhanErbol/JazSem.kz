from django.conf import settings
from django.db import models

from apps.common.models import Entity
from apps.materials.models import private_name


class SourceDocument(Entity):
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT, related_name="sources")
    file = models.FileField(upload_to=private_name)
    filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=150)
    size = models.PositiveIntegerField()
    processing_status = models.CharField(max_length=20, default="QUEUED")
    extracted_text = models.TextField(blank=True)
    error = models.CharField(max_length=250, blank=True)
    excluded = models.BooleanField(default=False)


class DocumentChunk(Entity):
    document = models.ForeignKey(SourceDocument, on_delete=models.CASCADE, related_name="chunks")
    page_number = models.PositiveIntegerField()
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()
    metadata = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["document", "chunk_index"], name="document_chunk_index")
        ]


class AIJob(Entity):
    type = models.CharField(max_length=40, default="COURSE")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default="QUEUED", db_index=True)
    progress = models.PositiveIntegerField(default=0)
    current_step = models.CharField(max_length=100, default="QUEUED")
    error = models.CharField(max_length=250, blank=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    parameters = models.JSONField(default=dict)
    request_id = models.CharField(max_length=36, blank=True)
    source_snapshot = models.JSONField(default=list)
    provider_started_at = models.DateTimeField(null=True)

    class Meta(Entity.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["course"],
                condition=models.Q(status__in=["QUEUED", "PROCESSING"]),
                name="one_active_generation_per_course",
            )
        ]


class TaskDelivery(Entity):
    """Durable at-least-once delivery; the lease token fences late workers."""

    source = models.OneToOneField(
        SourceDocument, null=True, on_delete=models.PROTECT, related_name="delivery"
    )
    job = models.OneToOneField(AIJob, null=True, on_delete=models.PROTECT, related_name="delivery")
    status = models.CharField(max_length=15, default="PENDING")
    attempts = models.PositiveIntegerField(default=0)
    executions = models.PositiveIntegerField(default=0)
    lease_token = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    heartbeat_at = models.DateTimeField(null=True)
    next_retry_at = models.DateTimeField(null=True)
    error_code = models.CharField(max_length=50, blank=True)

    class Meta(Entity.Meta):
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(source__isnull=False, job__isnull=True)
                    | models.Q(source__isnull=True, job__isnull=False)
                ),
                name="delivery_exactly_one_target",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "PENDING",
                        "DISPATCHING",
                        "SENT",
                        "RUNNING",
                        "DONE",
                        "FAILED",
                        "CANCELLED",
                    ]
                ),
                name="delivery_valid_status",
            ),
        ]


class AICourseDraft(Entity):
    job = models.OneToOneField(AIJob, on_delete=models.PROTECT, related_name="draft")
    data = models.JSONField()
    imported_version = models.OneToOneField(
        "courses.CourseVersion", null=True, on_delete=models.PROTECT
    )


class AIUsageLog(Entity):
    job = models.OneToOneField(AIJob, null=True, on_delete=models.PROTECT, related_name="usage")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    operation = models.CharField(max_length=80)
    model = models.CharField(max_length=100)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=6, null=True)
    duration = models.FloatField(default=0)
    status = models.CharField(max_length=30)


class AIBudgetDay(models.Model):
    day = models.DateField(primary_key=True)
    reserved_usd = models.DecimalField(max_digits=12, decimal_places=6, default=0)
