from django.db import transaction
from django.db.models import Max
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.assignments.models import Assignment
from apps.audit.services import record
from apps.common.permissions import is_teacher
from apps.common.scope import require_visible
from apps.courses.models import Course, CourseVersion, Topic, Week
from apps.courses.services import duplicate, new_version
from apps.grading.models import GradingComponent, GradingScheme
from apps.materials.models import Material
from apps.testing.models import AnswerOption, Question, Test

from .models import AICourseDraft, DocumentChunk
from .schema import CourseDraft, validate_citations


def validated_draft(data, course, allowed_ids=None):
    try:
        draft = CourseDraft.model_validate(data)
        validate_citations(
            draft,
            allowed_ids
            if allowed_ids is not None
            else {
                str(pk)
                for pk in DocumentChunk.objects.filter(document__course=course).values_list(
                    "pk", flat=True
                )
            },
        )
        return draft
    except ValueError as exc:
        raise ValidationError(str(exc))


def append_context(course, version_id, actor):
    if not is_teacher(actor):
        raise PermissionDenied()
    require_visible(course, actor)
    version = CourseVersion.objects.filter(course=course, pk=version_id).first()
    if (
        not version
        or version.status not in ["DRAFT", "REVIEW", "PUBLISHED"]
        or course.status == "ARCHIVED"
    ):
        raise ValidationError(
            "Версия недоступна для дополнения. Выберите действующий курс и версию."
        )
    weeks = list(version.weeks.order_by("number").values("id", "number", "title"))
    return {
        "base_version": str(version.pk),
        "version_number": version.version_number,
        "base_status": version.status,
        "start_week": max((week["number"] for week in weeks), default=0) + 1,
        "existing_weeks": [{**week, "id": str(week["id"])} for week in weeks],
    }


@transaction.atomic
def import_draft(draft, actor):
    require_visible(draft, actor)
    Course.objects.select_for_update().get(pk=draft.job.course_id)
    draft = AICourseDraft.objects.select_for_update().get(pk=draft.pk)
    if draft.imported_version:
        return draft.imported_version
    allowed = {chunk["id"] for chunk in draft.job.source_snapshot} or None
    data = validated_draft(draft.data, draft.job.course, allowed)
    params = draft.job.parameters
    appending = params.get("mode") == "APPEND"
    start_week = 1
    if appending:
        current = append_context(draft.job.course, params.get("base_version"), actor)
        if current != params.get("append_context"):
            raise ValidationError(
                "Структура или статус выбранной версии изменились. Создайте генерацию заново для актуальной версии."
            )
        source = CourseVersion.objects.select_for_update().get(pk=current["base_version"])
        version = duplicate(source, actor) if source.status == "PUBLISHED" else source
        start_week = current["start_week"]
    else:
        version = new_version(draft.job.course, actor)
    course = version.course
    if not appending:
        course.title, course.description = data.title, data.description
        course.save(update_fields=["title", "description", "updated_at"])
    has_assignments = has_tests = False
    first_order = (version.weeks.aggregate(n=Max("order"))["n"] or 0) + 1
    for offset, week_data in enumerate(data.weeks):
        week = Week.objects.create(
            course_version=version,
            number=start_week + offset,
            order=first_order + offset,
            title=week_data.title,
        )
        for order, topic_data in enumerate(week_data.topics):
            topic = Topic.objects.create(
                week=week,
                title=topic_data.title,
                order=order,
                source_chunks=topic_data.source_chunks,
            )
            Material.objects.create(
                topic=topic, title=topic.title, content=topic_data.content, type="TEXT"
            )
            for assignment in topic_data.assignments:
                Assignment.objects.create(
                    topic=topic,
                    title=assignment.title,
                    instructions=assignment.instructions,
                    source_chunks=assignment.source_chunks,
                )
                has_assignments = True
            if topic_data.questions:
                has_tests = True
                test = Test.objects.create(topic=topic, title=topic.title)
                for position, question_data in enumerate(topic_data.questions):
                    question = Question.objects.create(
                        test=test,
                        text=question_data.text,
                        type=question_data.type,
                        explanation=question_data.explanation,
                        source_chunks=question_data.source_chunks,
                        order=position,
                    )
                    for order, option in enumerate(question_data.options):
                        AnswerOption.objects.create(
                            question=question, order=order, **option.model_dump()
                        )
    scheme, created = GradingScheme.objects.get_or_create(course_version=version)
    if created and has_assignments:
        GradingComponent.objects.create(
            scheme=scheme, kind="ASSIGNMENTS", weight=50 if has_tests else 100
        )
    if created and has_tests:
        GradingComponent.objects.create(
            scheme=scheme, kind="TESTS", weight=50 if has_assignments else 100
        )
    draft.imported_version = version
    draft.save()
    record(actor, "ai.imported", draft, new={"version": str(version.pk)})
    return version
