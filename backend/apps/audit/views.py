from apps.audit.models import AuditLog
from apps.common.api import ReadOnlyScoped
from apps.common.serializers import serializer_for


class AuditViewSet(ReadOnlyScoped):
    queryset = AuditLog.objects.all()
    serializer_class = serializer_for(AuditLog)
