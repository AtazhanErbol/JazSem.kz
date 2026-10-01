from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied

from apps.cms.models import ContentBlock
from apps.common.api import ScopedViewSet
from apps.common.permissions import is_admin
from apps.common.serializers import serializer_for

from .landing import PREFIX


class ContentViewSet(ScopedViewSet):
    queryset = ContentBlock.objects.exclude(key__startswith=PREFIX)
    serializer_class = serializer_for(ContentBlock)
    search_fields = ["title", "key"]
    filterset_fields = ["language", "is_published"]

    def validate_write(self, serializer):
        if serializer.validated_data.get("key", "").startswith(PREFIX):
            raise PermissionDenied("Reserved content key.")
        if not is_admin(self.request.user):
            raise PermissionDenied()


class PublicContentViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    queryset = (
        ContentBlock.objects.filter(is_published=True)
        .exclude(key__startswith=PREFIX)
        .order_by("key")
    )
    serializer_class = serializer_for(ContentBlock)
    filterset_fields = ["language", "key"]
