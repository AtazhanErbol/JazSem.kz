from django.conf import settings
from django.db import models

from apps.common.models import Entity


class Enrollment(Entity):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="enrollments"
    )
    course = models.ForeignKey(
        "courses.Course", on_delete=models.PROTECT, related_name="enrollments"
    )
    course_version = models.ForeignKey(
        "courses.CourseVersion", on_delete=models.PROTECT, related_name="enrollments"
    )
    source_type = models.CharField(max_length=20)
    assigned_group = models.ForeignKey("academics.StudyGroup", null=True, on_delete=models.PROTECT)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    status = models.CharField(max_length=20, default="ASSIGNED", db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["student", "course"], name="one_learning_per_course")
        ]


class GroupCourseAssignment(Entity):
    group = models.ForeignKey(
        "academics.StudyGroup", on_delete=models.PROTECT, related_name="course_assignments"
    )
    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT)
    course_version = models.ForeignKey("courses.CourseVersion", on_delete=models.PROTECT)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    assigned_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default="ACTIVE")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["group", "course"], name="group_course")]


class EnrollmentSource(Entity):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT, related_name="sources")
    source_key = models.CharField(max_length=80)
    group_assignment = models.ForeignKey(GroupCourseAssignment, null=True, on_delete=models.PROTECT)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["enrollment", "source_key"], name="enrollment_source")
        ]
