from apps.audit.models import AuditLog
from apps.common.api import ReadOnlyScoped
from apps.common.permissions import AdminReady
from apps.common.serializers import serializer_for


class AuditViewSet(ReadOnlyScoped):
    permission_classes = [AdminReady]
    search_fields = ["action", "entity_type"]
    filterset_fields = ["action", "entity_type", "user"]
    queryset = AuditLog.objects.all()
    serializer_class = serializer_for(AuditLog)
