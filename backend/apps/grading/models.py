from django.db import models

from apps.common.models import Entity


class GradingScheme(Entity):
    course_version = models.OneToOneField(
        "courses.CourseVersion", on_delete=models.CASCADE, related_name="grading_scheme"
    )
    title = models.CharField(max_length=200, default="Основная схема")


class GradingComponent(Entity):
    scheme = models.ForeignKey(GradingScheme, on_delete=models.CASCADE, related_name="components")
    kind = models.CharField(
        max_length=20,
        choices=[("ASSIGNMENTS", "Assignments"), ("TESTS", "Tests"), ("FINAL", "Final")],
    )
    weight = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["scheme", "kind"], name="grading_component_kind"),
            models.CheckConstraint(
                condition=models.Q(weight__gt=0, weight__lte=100), name="valid_component_weight"
            ),
        ]
