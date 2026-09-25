from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied

from apps.cms.models import ContentBlock
from apps.common.api import ScopedViewSet
from apps.common.permissions import is_admin
from apps.common.serializers import serializer_for


class ContentViewSet(ScopedViewSet):
    queryset = ContentBlock.objects.all()
    serializer_class = serializer_for(ContentBlock)
    search_fields = ["title", "key"]

    def validate_write(self, serializer):
        if not is_admin(self.request.user):
            raise PermissionDenied()


class PublicContentViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    queryset = ContentBlock.objects.filter(is_published=True).order_by("key")
    serializer_class = serializer_for(ContentBlock)
    filterset_fields = ["language", "key"]
