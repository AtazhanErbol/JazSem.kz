from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.api import ReadOnlyScoped, representation
from apps.common.serializers import serializer_for
from apps.notifications.models import Notification


class NotificationViewSet(ReadOnlyScoped):
    queryset = Notification.objects.all()
    serializer_class = serializer_for(Notification)

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        note = self.get_object()
        note.is_read = True
        note.save()
        return Response(representation(note, request))
