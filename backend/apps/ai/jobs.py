import hashlib

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, Throttled, ValidationError

from apps.accounts.models import User
from apps.courses.models import Course

from .models import AIJob, DocumentChunk, SourceDocument, TaskDelivery


class ActiveGeneration(APIException):
    status_code = 409
    default_detail = "Генерация уже запущена."
    default_code = "generation_active"


def snapshot(course, source_ids, page_from=None, page_to=None):
    selected = set(source_ids)
    sources = SourceDocument.objects.filter(
        course=course, pk__in=selected, excluded=False, processing_status="COMPLETED"
    )
    if sources.count() != len(selected):
        raise ValidationError({"sources": "Выберите обработанные источники этого курса."})
    chunks = DocumentChunk.objects.filter(document__in=sources)
    if page_from is not None:
        if sources.count() != 1 or not sources.first().filename.lower().endswith(".pdf"):
            raise ValidationError(
                "Диапазон страниц поддерживается для одного PDF-файла. Для Word или текста укажите раздел в инструкции."
            )
        chunks = chunks.filter(page_number__gte=page_from, page_number__lte=page_to)
        if not chunks.exists():
            raise ValidationError(
                "На выбранных страницах нет распознанного текста. Проверьте номера страниц PDF и обработку файла."
            )
    result, chars = [], 0
    for chunk in chunks.order_by("document_id", "chunk_index").iterator():
        chars += len(chunk.content)
        if chars > settings.AI_MAX_SOURCE_CHARS:
            raise ValidationError(
                {"sources": "Источники превышают лимит контекста. Выберите меньше файлов."}
            )
        result.append(
            {
                "id": str(chunk.pk),
                "document": str(chunk.document_id),
                "page": chunk.page_number,
                "text": chunk.content,
                "sha256": hashlib.sha256(chunk.content.encode()).hexdigest(),
            }
        )
    if not result:
        raise ValidationError({"sources": "В источниках нет текста."})
    return result


@transaction.atomic
def create_job(
    actor, course, params, request_id, *, sources=None, source_snapshot=None, kind="COURSE"
):
    Course.objects.select_for_update().get(pk=course.pk)
    User.objects.select_for_update().get(pk=actor.pk)
    if AIJob.objects.filter(course=course, status__in=["QUEUED", "PROCESSING"]).exists():
        raise ActiveGeneration()
    if (
        AIJob.objects.filter(user=actor, created_at__date=timezone.now().date()).count()
        >= settings.AI_MAX_DAILY_JOBS
    ):
        raise Throttled(detail="Дневной лимит генерации исчерпан.")
    chunks = (
        source_snapshot
        if source_snapshot is not None
        else snapshot(course, sources, params.get("page_from"), params.get("page_to"))
    )
    if not chunks:
        raise ValidationError(
            "Для этого черновика нет снимка источников. Создайте новую генерацию."
        )
    job = AIJob.objects.create(
        user=actor,
        course=course,
        parameters=params,
        source_snapshot=chunks,
        type=kind,
        request_id=request_id,
    )
    TaskDelivery.objects.create(job=job, request_id=job.request_id)
    return job
