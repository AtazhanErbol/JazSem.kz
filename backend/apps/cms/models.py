from django.db import models

from apps.common.models import Entity


class ContentBlock(Entity):
    key = models.CharField(max_length=80)
    language = models.CharField(max_length=2, choices=[("ru", "RU"), ("kk", "KZ")])
    title = models.CharField(max_length=240)
    body = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["key", "language"], name="localized_content_key")
        ]
