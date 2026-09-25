from django.conf import settings
from django.db import models

from apps.common.models import Entity


class Course(Entity):
    discipline = models.ForeignKey("academics.Discipline", on_delete=models.PROTECT)
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default="DRAFT", db_index=True)
    default_language = models.CharField(
        max_length=2, choices=[("ru", "RU"), ("kk", "KZ")], default="ru"
    )
    current_version = models.ForeignKey(
        "CourseVersion", null=True, on_delete=models.PROTECT, related_name="+"
    )


class CourseVersion(Entity):
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="versions")
    version_number = models.PositiveIntegerField()
    status = models.CharField(max_length=20, default="DRAFT")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    published_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course", "version_number"], name="course_version_number"
            )
        ]


class Week(Entity):
    course_version = models.ForeignKey(
        CourseVersion, on_delete=models.CASCADE, related_name="weeks"
    )
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "number"]
        constraints = [
            models.UniqueConstraint(fields=["course_version", "number"], name="version_week_number")
        ]


class Topic(Entity):
    week = models.ForeignKey(Week, on_delete=models.CASCADE, related_name="topics")
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    content = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)
    source_chunks = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["order", "created_at"]
