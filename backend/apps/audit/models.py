from django.conf import settings
from django.db import models

from apps.common.models import Entity


class AuditLog(Entity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=80)
    entity_type = models.CharField(max_length=80)
    entity_id = models.CharField(max_length=80)
    old_data = models.JSONField(default=dict)
    new_data = models.JSONField(default=dict)
    ip = models.GenericIPAddressField(null=True)
