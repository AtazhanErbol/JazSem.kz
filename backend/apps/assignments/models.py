from django.conf import settings
from django.db import models

from apps.common.models import Entity
from apps.materials.models import private_name


class Assignment(Entity):
    topic = models.ForeignKey("courses.Topic", on_delete=models.CASCADE, related_name="assignments")
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    max_score = models.PositiveIntegerField(default=100)
    deadline = models.DateTimeField(null=True, blank=True)
    allow_late_submission = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default="DRAFT")
    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)
    source_chunks = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_score__gt=0), name="assignment_max_positive"
            )
        ]


class Submission(Entity):
    assignment = models.ForeignKey(Assignment, on_delete=models.PROTECT, related_name="submissions")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    attempt_number = models.PositiveIntegerField()
    text_answer = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, default="SUBMITTED", db_index=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    teacher_comment = models.TextField(blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+"
    )
    graded_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "student", "attempt_number"], name="submission_attempt_number"
            ),
            models.CheckConstraint(
                condition=models.Q(score__isnull=True) | models.Q(score__gte=0, score__lte=100),
                name="submission_score_range",
            ),
        ]


class SubmissionFile(Entity):
    submission = models.ForeignKey(Submission, on_delete=models.PROTECT, related_name="files")
    file = models.FileField(upload_to=private_name)
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=150)
    size = models.PositiveIntegerField()
