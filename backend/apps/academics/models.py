from django.conf import settings
from django.db import models

from apps.common.models import Entity


class Discipline(Entity):
    name = models.CharField(max_length=240)
    code = models.CharField(max_length=40, unique=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="ACTIVE")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    teachers = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="disciplines")


class StudyGroup(Entity):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default="ACTIVE")


class GroupMembership(Entity):
    group = models.ForeignKey(StudyGroup, on_delete=models.PROTECT, related_name="memberships")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True)
    status = models.CharField(max_length=20, default="ACTIVE")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group", "student"],
                condition=models.Q(status="ACTIVE"),
                name="active_membership",
            )
        ]
