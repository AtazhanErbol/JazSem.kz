from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.accounts.models import User
from apps.common.api import ReadOnlyScoped, lookup, private_response, representation
from apps.common.permissions import is_teacher
from apps.common.serializers import serializer_for
from apps.courses.models import Course
from apps.materials.validation import validate_upload

from .models import AICourseDraft, AIJob, AIUsageLog, DocumentChunk, SourceDocument
from .services import import_draft, validated_draft
from .tasks import extract_document, generate_course


class SourceViewSet(ReadOnlyScoped):
    queryset = SourceDocument.objects.all()
    serializer_class = serializer_for(SourceDocument)
    throttle_scope = "upload"
    filterset_fields = ["course"]

    def get_throttles(self):
        return super().get_throttles() if self.action == "create" else []

    def create(self, request):
        if not is_teacher(request.user):
            raise PermissionDenied()
        course = lookup(Course, request.data.get("course"), request.user)
        file = request.FILES.get("file")
        if not file:
            raise ValidationError("Выберите файл.")
        validate_upload(file)
        with transaction.atomic():
            source = SourceDocument.objects.create(
                course=course,
                uploaded_by=request.user,
                file=file,
                filename=file.name,
                mime_type=file.content_type,
                size=file.size,
            )
            transaction.on_commit(lambda: extract_document.delay(str(source.pk)))
        return Response(representation(source, request), status=201)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        source = self.get_object()
        return private_response(source.file, source.filename)

    @action(detail=True, methods=["get"])
    def chunks(self, request, pk=None):
        qs = self.get_object().chunks.order_by("chunk_index")
        page = self.paginate_queryset(qs)
        return self.get_paginated_response([representation(c, request) for c in page])


class GenerationSerializer(serializers.Serializer):
    course = serializers.UUIDField()
    weeks = serializers.IntegerField(min_value=1, max_value=16)
    language = serializers.ChoiceField(choices=["ru", "kk"])
    complexity = serializers.ChoiceField(
        choices=["basic", "intermediate", "advanced"], default="intermediate"
    )
    assignments = serializers.BooleanField(default=True)
    tests = serializers.BooleanField(default=True)


class JobViewSet(ReadOnlyScoped):
    queryset = AIJob.objects.all()
    serializer_class = serializer_for(AIJob)
    throttle_scope = "ai"
    filterset_fields = ["course", "status"]

    def get_throttles(self):
        return super().get_throttles() if self.action == "create" else []

    @transaction.atomic
    def create(self, request):
        if not is_teacher(request.user):
            raise PermissionDenied()
        data = GenerationSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        params = data.validated_data
        course = lookup(Course, params.pop("course"), request.user)
        User.objects.select_for_update().get(pk=request.user.pk)
        if AIJob.objects.filter(course=course, status__in=["QUEUED", "PROCESSING"]).exists():
            raise ValidationError("Генерация уже запущена.")
        if (
            AIJob.objects.filter(user=request.user, created_at__date=timezone.now().date()).count()
            >= settings.AI_MAX_DAILY_JOBS
        ):
            raise ValidationError("Дневной лимит генерации исчерпан.")
        if (
            not course.sources.exists()
            or course.sources.exclude(processing_status="COMPLETED").exists()
        ):
            raise ValidationError("Дождитесь обработки всех источников.")
        job = AIJob.objects.create(
            user=request.user, course=course, parameters=params, request_id=request.request_id
        )
        transaction.on_commit(lambda: generate_course.delay(str(job.pk)))
        return Response(representation(job, request), status=202)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        job = self.get_object()
        AIJob.objects.filter(pk=job.pk, status__in=["QUEUED", "PROCESSING"]).update(
            status="CANCELLED", finished_at=timezone.now()
        )
        job.refresh_from_db()
        return Response(representation(job, request))

    @action(detail=True, methods=["get"])
    def draft(self, request, pk=None):
        job = self.get_object()
        draft = AICourseDraft.objects.filter(job=job).first()
        if not draft:
            raise ValidationError("Черновик ещё не готов.")
        return Response(representation(draft, request))


class DraftViewSet(ReadOnlyScoped):
    queryset = AICourseDraft.objects.all()
    serializer_class = serializer_for(AICourseDraft)
    throttle_scope = "ai"

    def get_throttles(self):
        return super().get_throttles() if self.action == "regenerate" else []

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def regenerate(self, request, pk=None):
        draft = self.get_object()
        if draft.imported_version:
            raise ValidationError("Черновик уже импортирован.")

        class Input(serializers.Serializer):
            week_index = serializers.IntegerField(min_value=0)
            topic_index = serializers.IntegerField(min_value=0)
            instruction = serializers.CharField(max_length=2000)

        data = Input(data=request.data)
        data.is_valid(raise_exception=True)
        params = data.validated_data
        try:
            draft.data["weeks"][params["week_index"]]["topics"][params["topic_index"]]
        except IndexError:
            raise ValidationError("Тема не найдена.")
        User.objects.select_for_update().get(pk=request.user.pk)
        if AIJob.objects.filter(
            course=draft.job.course, status__in=["QUEUED", "PROCESSING"]
        ).exists():
            raise ValidationError("Генерация уже запущена.")
        if (
            AIJob.objects.filter(user=request.user, created_at__date=timezone.now().date()).count()
            >= settings.AI_MAX_DAILY_JOBS
        ):
            raise ValidationError("Дневной лимит генерации исчерпан.")
        params.update(
            {
                "draft_data": draft.data,
                "weeks": len(draft.data["weeks"]),
                "assignments": True,
                "tests": True,
            }
        )
        job = AIJob.objects.create(
            user=request.user,
            course=draft.job.course,
            type="REGENERATE_TOPIC",
            parameters=params,
            request_id=request.request_id,
        )
        transaction.on_commit(lambda: generate_course.delay(str(job.pk)))
        return Response(representation(job, request), status=202)

    @transaction.atomic
    def partial_update(self, request, pk=None):
        draft = self.get_object()
        draft = AICourseDraft.objects.select_for_update().get(pk=draft.pk)
        if draft.imported_version:
            raise ValidationError("Черновик уже импортирован. Редактируйте версию курса.")
        data = validated_draft(request.data.get("data"), draft.job.course)
        draft.data = data.model_dump()
        draft.save()
        return Response(representation(draft, request))

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        return Response(representation(import_draft(self.get_object(), request.user), request))


class UsageViewSet(ReadOnlyScoped):
    queryset = AIUsageLog.objects.all()
    serializer_class = serializer_for(AIUsageLog)


class ChunkViewSet(ReadOnlyScoped):
    queryset = DocumentChunk.objects.all()
    serializer_class = serializer_for(DocumentChunk)
