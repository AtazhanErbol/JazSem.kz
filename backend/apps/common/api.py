from django.db import models, transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.common.permissions import is_teacher
from apps.common.scope import editable, require_visible, version_of, visible
from apps.common.serializers import serializer_for
from apps.materials.validation import validate_upload


def representation(obj, request):
    return serializer_for(type(obj))(obj, context={"request": request}).data


def lookup(model, pk, user):
    return get_object_or_404(visible(model.objects.all(), user), pk=pk)


class ScopedViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    search_fields = ["title"]
    ordering_fields = ["created_at"]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def get_queryset(self):
        qs = self.queryset.all()
        if not qs.ordered:
            qs = qs.order_by("created_at", "pk")
        # Load direct foreign keys once for list serialization.
        related = [f.name for f in qs.model._meta.fields if isinstance(f, models.ForeignKey)]
        return visible(qs.select_related(*related), self.request.user)

    def validate_write(self, serializer):
        user = self.request.user
        if not is_teacher(user):
            raise PermissionDenied()
        if serializer.instance:
            editable(serializer.instance, user)
        for field, value in serializer.validated_data.items():
            if isinstance(value, models.Model):
                require_visible(value, user)
                if version_of(value):
                    editable(value, user)
                if (
                    serializer.instance
                    and getattr(serializer.instance, field + "_id", None) != value.pk
                ):
                    raise ValidationError({field: "Перенос между объектами запрещён."})
        if "status" in serializer.validated_data:
            raise ValidationError({"status": "Используйте действие публикации/архивации."})
        if "file" in serializer.validated_data:
            validate_upload(serializer.validated_data["file"])
        if serializer.validated_data.get("external_url") and not serializer.validated_data[
            "external_url"
        ].startswith("https://"):
            raise ValidationError({"external_url": "Разрешены только HTTPS ссылки."})

    @transaction.atomic
    def perform_create(self, serializer):
        self.validate_write(serializer)
        serializer.save()

    @transaction.atomic
    def perform_update(self, serializer):
        self.validate_write(serializer)
        serializer.save()

    @transaction.atomic
    def perform_destroy(self, instance):
        editable(instance, self.request.user)
        if not version_of(instance):
            raise ValidationError("Используйте архивирование.")
        instance.delete()


def private_response(file, filename):
    response = FileResponse(file.open("rb"), as_attachment=True, filename=filename or "download")
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


class ReadOnlyScoped(viewsets.ReadOnlyModelViewSet):
    def get_queryset(self):
        qs = self.queryset.all()
        if not qs.ordered:
            qs = qs.order_by("-created_at", "pk")
        return visible(qs, self.request.user)


def content_view(model):
    return type(
        model.__name__ + "ViewSet",
        (ScopedViewSet,),
        {
            "queryset": model.objects.all(),
            "serializer_class": serializer_for(model),
            "search_fields": [],
            "filterset_fields": [
                f.name for f in model._meta.fields if isinstance(f, models.ForeignKey)
            ],
        },
    )
