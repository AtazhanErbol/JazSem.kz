from django.db import transaction
from django.db.models import Count, Min
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.audit.services import record
from apps.common.api import ReadOnlyScoped, representation
from apps.common.inputs import EmptyInput, validated
from apps.common.permissions import AdminReady
from apps.common.serializers import serializer_for
from apps.notifications.models import MailOutbox, Notification


class NotificationViewSet(ReadOnlyScoped):
    queryset = Notification.objects.all()
    serializer_class = serializer_for(Notification)
    search_fields = ["title", "message"]
    filterset_fields = ["is_read"]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        validated(request, EmptyInput)
        note = self.get_object()
        note.is_read = True
        note.save()
        return Response(representation(note, request))


class MailDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = MailOutbox
        fields = [
            "id",
            "recipient",
            "created_at",
            "updated_at",
            "status",
            "attempts",
            "cycle_attempts",
            "next_retry_at",
            "sent_at",
            "error_code",
        ]
        read_only_fields = fields


class MailOutboxViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AdminReady]
    serializer_class = MailDeliverySerializer
    queryset = MailOutbox.objects.all().order_by("-created_at", "pk")
    filterset_fields = ["status"]
    search_fields = ["recipient"]
    ordering_fields = ["created_at", "next_retry_at"]

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def retry(self, request, pk=None):
        validated(request, EmptyInput)
        mail = MailOutbox.objects.select_for_update().get(pk=self.get_object().pk)
        if mail.status == "SENDING" or mail.sent_at or not mail.encrypted_payload:
            raise ValidationError("Доставка уже выполняется или завершена.")
        previous = mail.status
        mail.status = "PENDING"
        mail.cycle_attempts = 0
        mail.next_retry_at = timezone.now()
        mail.error_code = ""
        mail.save()
        record(request.user, "mail.retry", mail, {"status": previous}, {"status": mail.status})
        return Response(self.get_serializer(mail).data)

    @action(detail=False, methods=["get"])
    def metrics(self, request):
        pending = MailOutbox.objects.exclude(status="SENT")
        oldest = pending.aggregate(oldest=Min("created_at"))["oldest"]
        return Response(
            {
                "counts": dict(
                    MailOutbox.objects.values("status")
                    .annotate(total=Count("id"))
                    .values_list("status", "total")
                ),
                "oldest_unsent_seconds": max(0, (timezone.now() - oldest).total_seconds())
                if oldest
                else 0,
            }
        )
