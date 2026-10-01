import json
import logging

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.assignments.models import Assignment
from apps.audit.services import record
from apps.common.permissions import is_teacher
from apps.common.scope import require_visible
from apps.courses.models import Course, Topic
from apps.testing.models import Question

from .models import AICourseDraft, AIJob, SourceDocument, TaskDelivery


@transaction.atomic
def delete_source(source, actor, filename):
    if not is_teacher(actor):
        raise PermissionDenied()
    require_visible(source, actor)
    Course.objects.select_for_update().get(pk=source.course_id)
    source = SourceDocument.objects.select_for_update().get(pk=source.pk)
    if filename != source.filename:
        raise ValidationError("Введите точное имя файла для подтверждения удаления.")
    if (
        source.processing_status in ["QUEUED", "PROCESSING"]
        or TaskDelivery.objects.filter(source=source)
        .exclude(status__in=["DONE", "FAILED", "CANCELLED"])
        .exists()
    ):
        raise ValidationError("Файл ещё обрабатывается. Дождитесь завершения обработки.")
    used = any(
        any(str(chunk.get("document")) == str(source.pk) for chunk in snapshot)
        for snapshot in AIJob.objects.filter(course_id=source.course_id).values_list(
            "source_snapshot", flat=True
        )
    )
    ids = {str(pk) for pk in source.chunks.values_list("pk", flat=True)}
    if not used and ids:
        references = [
            Topic.objects.filter(week__course_version__course_id=source.course_id),
            Assignment.objects.filter(topic__week__course_version__course_id=source.course_id),
            Question.objects.filter(test__topic__week__course_version__course_id=source.course_id),
        ]
        used = any(
            ids.intersection(refs)
            for qs in references
            for refs in qs.values_list("source_chunks", flat=True)
        )
        if not used:
            used = any(
                any(identifier in json.dumps(data) for identifier in ids)
                for data in AICourseDraft.objects.filter(
                    job__course_id=source.course_id
                ).values_list("data", flat=True)
            )
    if used:
        raise ValidationError(
            "Файл используется в генерации или материалах курса. Используйте «Исключить», чтобы сохранить ссылки на источник."
        )
    storage, name = source.file.storage, source.file.name
    record(actor, "source.deleted", source)
    TaskDelivery.objects.filter(source=source).delete()
    source.delete()

    def remove_original():
        if name:
            try:
                storage.delete(name)
            except Exception:
                logging.getLogger(__name__).exception("Source file cleanup failed")

    transaction.on_commit(remove_original)
