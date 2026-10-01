from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record
from apps.common.api import ReadOnlyScoped, lookup, private_response, representation
from apps.common.background import require_worker, worker_available
from apps.common.inputs import EmptyInput, validated
from apps.common.permissions import is_teacher
from apps.courses.models import Course
from apps.materials.validation import validate_upload

from .contracts import (
    ChunkOutput,
    DraftInput,
    DraftOutput,
    GenerationInput,
    JobOutput,
    RegenerateInput,
    SourceInput,
    SourceOutput,
    UsageOutput,
)
from .jobs import create_job
from .models import AICourseDraft, AIJob, AIUsageLog, DocumentChunk, SourceDocument, TaskDelivery
from .services import append_context, import_draft, validated_draft


def require_generation():
    if not settings.AI_ENABLED:
        raise ValidationError("Генерация AI отключена администратором.")
    if not all(
        [
            settings.OPENAI_API_KEY,
            settings.OPENAI_MODEL,
            settings.AI_INPUT_PRICE,
            settings.AI_OUTPUT_PRICE,
        ]
    ):
        raise ValidationError("Не настроены ключ, модель или лимиты стоимости AI.")
    require_worker()


class AIStatusView(APIView):
    class AIStatusOutput(serializers.Serializer):
        enabled = serializers.BooleanField()
        configured = serializers.BooleanField()
        worker_available = serializers.BooleanField()
        daily_budget = serializers.CharField()
        model = serializers.CharField()

    serializer_class = AIStatusOutput

    def get(self, request):
        if not is_teacher(request.user):
            raise PermissionDenied()
        return Response(
            {
                "enabled": settings.AI_ENABLED,
                "configured": bool(
                    settings.OPENAI_API_KEY
                    and settings.OPENAI_MODEL
                    and settings.AI_INPUT_PRICE
                    and settings.AI_OUTPUT_PRICE
                ),
                "worker_available": worker_available(),
                "daily_budget": str(settings.AI_DAILY_BUDGET_USD),
                "model": settings.OPENAI_MODEL,
            }
        )


class SourceViewSet(ReadOnlyScoped):
    queryset = SourceDocument.objects.all()
    serializer_class = SourceOutput
    throttle_scope = "upload"
    filterset_fields = ["course"]

    def get_throttles(self):
        return super().get_throttles() if self.action == "create" else []

    def create(self, request):
        if not is_teacher(request.user):
            raise PermissionDenied()
        data = validated(request, SourceInput)
        course = lookup(Course, data["course"], request.user)
        file = data["file"]
        validate_upload(file)
        require_worker()
        with transaction.atomic():
            source = SourceDocument.objects.create(
                course=course,
                uploaded_by=request.user,
                file=file,
                filename=file.name,
                mime_type=file.content_type,
                size=file.size,
            )
            TaskDelivery.objects.create(source=source, request_id=request.request_id)
        return Response(self.get_serializer(source).data, status=201)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def retry(self, request, pk=None):
        validated(request, EmptyInput)
        source = self.get_object()
        Course.objects.select_for_update().get(pk=source.course_id)
        source.refresh_from_db()
        if source.processing_status != "FAILED" or source.chunks.exists():
            raise ValidationError(
                "Повтор доступен только для сбойного источника без готовых цитат."
            )
        source.processing_status, source.error = "QUEUED", ""
        source.save()
        TaskDelivery.objects.update_or_create(
            source=source,
            defaults={
                "status": "PENDING",
                "attempts": 0,
                "executions": 0,
                "lease_token": None,
                "lease_until": None,
                "next_retry_at": None,
                "error_code": "",
            },
        )
        record(request.user, "source.retry", source)
        return Response(self.get_serializer(source).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def exclude(self, request, pk=None):
        validated(request, EmptyInput)
        source = self.get_object()
        Course.objects.select_for_update().get(pk=source.course_id)
        source.excluded = True
        source.save(update_fields=["excluded", "updated_at"])
        record(request.user, "source.exclude", source)
        return Response(self.get_serializer(source).data)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        source = self.get_object()
        return private_response(source.file, source.filename)

    @action(detail=True, methods=["get"])
    def chunks(self, request, pk=None):
        qs = self.get_object().chunks.order_by("chunk_index")
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(ChunkOutput(page, many=True).data)


class JobViewSet(ReadOnlyScoped):
    queryset = AIJob.objects.select_related("usage")
    serializer_class = JobOutput
    throttle_scope = "ai"
    filterset_fields = ["course", "status"]

    @action(detail=False, methods=["get"], url_path="append-context")
    def append_info(self, request):
        if not is_teacher(request.user):
            raise PermissionDenied()
        from rest_framework.serializers import UUIDField

        course_id = UUIDField().run_validation(request.query_params.get("course"))
        version_id = UUIDField().run_validation(request.query_params.get("version"))
        course = lookup(Course, course_id, request.user)
        return Response(append_context(course, version_id, request.user))

    def get_throttles(self):
        return super().get_throttles() if self.action == "create" else []

    @transaction.atomic
    def create(self, request):
        if not is_teacher(request.user):
            raise PermissionDenied()
        require_generation()
        params = validated(request, GenerationInput)
        course = lookup(Course, params.pop("course"), request.user)
        if params.get("mode") == "APPEND":
            Course.objects.select_for_update().get(pk=course.pk)
            params["base_version"] = str(params["base_version"])
            params["append_context"] = append_context(course, params["base_version"], request.user)
        sources = params.pop("sources")
        job = create_job(request.user, course, params, request.request_id, sources=sources)
        return Response(self.get_serializer(job).data, status=202)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def cancel(self, request, pk=None):
        validated(request, EmptyInput)
        job = self.get_object()
        Course.objects.select_for_update().get(pk=job.course_id)
        TaskDelivery.objects.filter(job=job).exclude(
            status__in=["DONE", "FAILED", "CANCELLED"]
        ).update(status="CANCELLED", lease_token=None, lease_until=None)
        AIJob.objects.filter(pk=job.pk, status__in=["QUEUED", "PROCESSING"]).update(
            status="CANCELLED", current_step="CANCELLED", finished_at=timezone.now()
        )
        job.refresh_from_db()
        record(request.user, "ai.cancel", job, new={"status": job.status})
        return Response(self.get_serializer(job).data)

    @action(detail=True, methods=["get"])
    def draft(self, request, pk=None):
        job = self.get_object()
        draft = AICourseDraft.objects.filter(job=job).first()
        if not draft:
            raise ValidationError("Черновик ещё не готов.")
        return Response(DraftOutput(draft).data)


class DraftViewSet(ReadOnlyScoped):
    queryset = AICourseDraft.objects.all()
    serializer_class = DraftOutput
    throttle_scope = "ai"

    def get_throttles(self):
        return super().get_throttles() if self.action == "regenerate" else []

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def regenerate(self, request, pk=None):
        require_generation()
        draft = self.get_object()
        Course.objects.select_for_update().get(pk=draft.job.course_id)
        draft = AICourseDraft.objects.select_for_update().get(pk=draft.pk)
        if draft.imported_version:
            raise ValidationError("Черновик уже импортирован.")

        params = validated(request, RegenerateInput)
        try:
            draft.data["weeks"][params["week_index"]]["topics"][params["topic_index"]]
        except (IndexError, KeyError, TypeError):
            raise ValidationError("Тема не найдена.")
        params.update(
            {
                "draft_data": draft.data,
                "weeks": len(draft.data["weeks"]),
                "assignments": True,
                "tests": True,
            }
        )
        for key in ["mode", "base_version", "append_context"]:
            if key in draft.job.parameters:
                params[key] = draft.job.parameters[key]
        job = create_job(
            request.user,
            draft.job.course,
            params,
            request.request_id,
            source_snapshot=draft.job.source_snapshot,
            kind="REGENERATE_TOPIC",
        )
        return Response(JobOutput(job).data, status=202)

    @transaction.atomic
    def partial_update(self, request, pk=None):
        draft = self.get_object()
        Course.objects.select_for_update().get(pk=draft.job.course_id)
        draft = AICourseDraft.objects.select_for_update().get(pk=draft.pk)
        if draft.imported_version:
            raise ValidationError("Черновик уже импортирован. Редактируйте версию курса.")
        allowed = {chunk["id"] for chunk in draft.job.source_snapshot} or None
        data = validated_draft(validated(request, DraftInput)["data"], draft.job.course, allowed)
        draft.data = data.model_dump()
        draft.save()
        return Response(DraftOutput(draft).data)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        validated(request, EmptyInput)
        return Response(representation(import_draft(self.get_object(), request.user), request))


class UsageViewSet(ReadOnlyScoped):
    queryset = AIUsageLog.objects.all()
    serializer_class = UsageOutput


class ChunkViewSet(ReadOnlyScoped):
    queryset = DocumentChunk.objects.all()
    serializer_class = ChunkOutput
