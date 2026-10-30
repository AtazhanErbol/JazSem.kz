from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.audit.services import record, selected_fields
from apps.common.api import ScopedViewSet, lookup, private_response
from apps.common.permissions import is_teacher
from apps.common.scope import editable
from apps.common.serializers import ScopedSerializer
from apps.common.upload_parser import UPLOAD_PARSERS

from .models import LearningAttachment
from .remote_uploads import promote_attachment
from .validation import MIMES, VIDEO_MIMES, validate_upload
from .youtube import embed_url, normalize_youtube

PARENTS = ("topic", "assignment", "test", "question")


def attachment_parent(data, user):
    from apps.assignments.models import Assignment
    from apps.courses.models import Topic
    from apps.testing.models import Question, Test

    if not is_teacher(user):
        raise PermissionDenied()
    models = dict(zip(PARENTS, (Topic, Assignment, Test, Question), strict=True))
    selected = [field for field in PARENTS if data.get(field)]
    if len(selected) != 1:
        raise ValidationError("Укажите ровно одну лекцию, задание, тест или вопрос.")
    field = selected[0]
    pk = serializers.UUIDField().run_validation(data[field])
    parent = lookup(models[field], pk, user)
    editable(parent, user)
    return parent


class AttachmentSerializer(ScopedSerializer):
    external_url = serializers.CharField(max_length=2048, required=False, allow_blank=True)
    upload_ticket = serializers.UUIDField(required=False, write_only=True)
    embed_url = serializers.SerializerMethodField()

    class Meta:
        model = LearningAttachment
        fields = [
            "id",
            *PARENTS,
            "title",
            "description",
            "kind",
            "file",
            "external_url",
            "original_filename",
            "mime_type",
            "size",
            "order",
            "created_at",
            "uploaded_at",
            "updated_at",
            "upload_ticket",
            "embed_url",
        ]
        read_only_fields = [
            "uploaded_at",
            "id",
            "original_filename",
            "mime_type",
            "size",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {"description": {"max_length": 4000}, "file": {"required": False}}

    def get_embed_url(self, obj) -> str:
        return embed_url(obj.external_url) if obj.kind == "YOUTUBE" else ""

    def validate(self, attrs):
        parents = {name: attrs.get(name, getattr(self.instance, name, None)) for name in PARENTS}
        if sum(value is not None for value in parents.values()) != 1:
            raise serializers.ValidationError(
                "Вложение должно относиться ровно к одному материалу."
            )
        if self.instance and any(
            name in attrs and attrs[name] != getattr(self.instance, name) for name in PARENTS
        ):
            raise serializers.ValidationError("Вложение нельзя перемещать в другой материал.")
        kind = attrs.get("kind", getattr(self.instance, "kind", "FILE"))
        file = attrs.get("file")
        ticket = attrs.get("upload_ticket")
        if file and ticket:
            raise serializers.ValidationError("Укажите файл или разрешение загрузки, а не оба.")
        if kind == "YOUTUBE":
            if file or ticket:
                raise serializers.ValidationError({"file": "Для YouTube укажите ссылку."})
            attrs["external_url"] = normalize_youtube(
                attrs.get("external_url", getattr(self.instance, "external_url", ""))
            )
            attrs.update(file="", original_filename="", mime_type="", size=None)
        else:
            if attrs.get("external_url"):
                raise serializers.ValidationError(
                    {"external_url": "Ссылка доступна только для YouTube."}
                )
            attrs["external_url"] = ""
            if not (file or ticket or (self.instance and self.instance.file)):
                raise serializers.ValidationError({"file": "Выберите файл."})
            if file:
                validate_upload(file, allow_video=True)
            mime = file.content_type if file else getattr(self.instance, "mime_type", "")
            if not ticket and (mime in VIDEO_MIMES.values()) != (kind == "VIDEO"):
                raise serializers.ValidationError(
                    {"kind": "Выберите видео для MP4/WebM, файл — для учебного документа."}
                )
        return attrs


class AttachmentConfigOutput(serializers.Serializer):
    max_document_bytes = serializers.IntegerField()
    max_video_bytes = serializers.IntegerField()
    document_types = serializers.DictField(child=serializers.CharField())
    video_types = serializers.DictField(child=serializers.CharField())
    direct_uploads = serializers.BooleanField()


class ReorderInput(serializers.Serializer):
    first = serializers.UUIDField()
    second = serializers.UUIDField(required=False)
    direction = serializers.ChoiceField(choices=["UP", "DOWN"], required=False)

    def validate(self, attrs):
        if ("second" in attrs) == ("direction" in attrs):
            raise serializers.ValidationError("Укажите соседнее вложение или направление.")
        return attrs


class AttachmentViewSet(ScopedViewSet):
    queryset = LearningAttachment.objects.select_related("topic", "assignment", "test", "question")
    serializer_class = AttachmentSerializer
    parser_classes = UPLOAD_PARSERS
    filterset_fields = {**{name: ["exact"] for name in PARENTS}, "kind": ["exact", "in"]}
    ordering_fields = ["order", "created_at"]
    throttle_scope = "upload"

    def get_throttles(self):
        return super().get_throttles() if self.action in {"create", "partial_update"} else []

    @extend_schema(request=ReorderInput, responses={204: None})
    @action(detail=False, methods=["post"])
    @transaction.atomic
    def reorder(self, request):
        from apps.common.inputs import validated

        if not is_teacher(request.user):
            raise PermissionDenied()
        data = validated(request, ReorderInput)
        first = get_object_or_404(self.get_queryset(), pk=data["first"])
        editable(first, request.user)
        parent_name = next(name for name in PARENTS if getattr(first, name + "_id"))
        parent_id = getattr(first, parent_name + "_id")
        rows = list(
            LearningAttachment.objects.filter(**{parent_name + "_id": parent_id}).order_by(
                "order", "created_at", "pk"
            )
        )
        indices = {row.pk: i for i, row in enumerate(rows)}
        if "second" in data:
            second = get_object_or_404(self.get_queryset(), pk=data["second"])
            if getattr(second, parent_name + "_id") != parent_id:
                raise ValidationError("Материалы должны принадлежать одному объекту.")
        else:
            group = [row for row in rows if (row.kind == "FILE") == (first.kind == "FILE")]
            current = next(i for i, row in enumerate(group) if row.pk == first.pk)
            neighbour = current + (-1 if data["direction"] == "UP" else 1)
            if neighbour < 0 or neighbour >= len(group):
                return Response(status=204)
            second = group[neighbour]
        a, b = indices[first.pk], indices[second.pk]
        rows[a], rows[b] = rows[b], rows[a]
        for position, row in enumerate(rows):
            row.order = position
        LearningAttachment.objects.bulk_update(rows, ["order"])
        record(request.user, "attachment.reorder", first)
        return Response(status=204)

    def save_attachment(self, serializer):
        if not is_teacher(self.request.user):
            raise PermissionDenied()
        values = serializer.validated_data
        parent = (
            serializer.instance.parent
            if serializer.instance
            else next(values[p] for p in PARENTS if values.get(p))
        )
        editable(parent, self.request.user)
        ticket = values.pop("upload_ticket", None)
        file = values.get("file")
        if file and settings.DIRECT_UPLOADS_ENABLED:
            raise ValidationError({"file": "Используйте прямую загрузку во внешнее хранилище."})
        metadata = {}
        if ticket:
            metadata = promote_attachment(
                ticket,
                self.request,
                kind=values.get("kind", getattr(serializer.instance, "kind", "FILE")),
            )
        elif file:
            metadata = {
                "original_filename": file.name,
                "mime_type": file.content_type,
                "size": file.size,
            }
        if (
            ticket
            or file
            or (
                values.get("kind") == "YOUTUBE"
                and values.get("external_url") != getattr(serializer.instance, "external_url", "")
            )
        ):
            metadata["uploaded_at"] = timezone.now()
        old = selected_fields(serializer.instance) if serializer.instance else {}
        saved = serializer.save(**metadata)
        record(self.request.user, "attachment.saved", saved, old=old, new=selected_fields(saved))

    @transaction.atomic
    def perform_create(self, serializer):
        self.save_attachment(serializer)

    @transaction.atomic
    def perform_update(self, serializer):
        self.save_attachment(serializer)

    @extend_schema(responses=AttachmentConfigOutput)
    @action(detail=False, methods=["get"])
    def config(self, request):
        if not is_teacher(request.user):
            raise PermissionDenied()
        return Response(
            {
                "max_document_bytes": settings.MAX_UPLOAD_BYTES,
                "max_video_bytes": settings.MAX_VIDEO_UPLOAD_BYTES,
                "document_types": MIMES,
                "video_types": VIDEO_MIMES,
                "direct_uploads": settings.DIRECT_UPLOADS_ENABLED,
            }
        )

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        attachment = self.get_object()
        if not attachment.file:
            raise ValidationError("Файл отсутствует.")
        return private_response(attachment.file, attachment.original_filename)

    @action(detail=True, methods=["get"])
    def preview(self, request, pk=None):
        attachment = self.get_object()
        if not attachment.file or attachment.mime_type not in {
            "application/pdf",
            "image/png",
            "image/jpeg",
            "image/webp",
            "image/gif",
            *VIDEO_MIMES.values(),
        }:
            raise ValidationError("Для этого формата доступно скачивание.")
        response = private_response(
            attachment.file,
            attachment.original_filename,
            as_attachment=False,
            content_type=attachment.mime_type,
            expires=settings.PRIVATE_MEDIA_URL_SECONDS,
        )
        response["Content-Security-Policy"] = "sandbox; default-src 'none'"
        return response
