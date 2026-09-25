from apps.common.request_context import request_context

from .models import AuditLog


def record(user, action, obj, old=None, new=None):
    # Only explicitly selected business fields are accepted at call sites.
    AuditLog.objects.create(
        user=user,
        action=action,
        entity_type=obj._meta.label,
        entity_id=str(obj.pk),
        old_data=old or {},
        ip=request_context.get().get("ip"),
        new_data=new or {},
    )
