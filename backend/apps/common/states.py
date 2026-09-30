"""Persisted states; transition policies live in the owning service."""

from django.db import models


class CourseState(models.TextChoices):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class VersionState(models.TextChoices):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"  # Existing editable legacy state; import now creates DRAFT.
    PUBLISHED = "PUBLISHED"


class EnrollmentState(models.TextChoices):
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"  # Historical states remain readable; no new write action.
    FAILED = "FAILED"


class SubmissionState(models.TextChoices):
    SUBMITTED = "SUBMITTED"
    RESUBMITTED = "RESUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    GRADED = "GRADED"


class AttemptState(models.TextChoices):
    IN_PROGRESS = "IN_PROGRESS"
    GRADED = "GRADED"
    EXPIRED = "EXPIRED"


class SourceState(models.TextChoices):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobState(models.TextChoices):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
