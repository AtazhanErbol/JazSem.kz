from django.db import models

from apps.common.models import Entity


class TopicProgress(Entity):
    enrollment = models.ForeignKey("enrollments.Enrollment", on_delete=models.PROTECT)
    topic = models.ForeignKey("courses.Topic", on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["enrollment", "topic"], name="topic_completion")
        ]


class StudentProgress(Entity):
    enrollment = models.ForeignKey(
        "enrollments.Enrollment", on_delete=models.PROTECT, related_name="material_progress"
    )
    material = models.ForeignKey("materials.Material", on_delete=models.PROTECT)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["enrollment", "material"], name="material_completion")
        ]
