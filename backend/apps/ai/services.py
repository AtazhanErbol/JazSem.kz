from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.assignments.models import Assignment
from apps.audit.services import record
from apps.common.scope import require_visible
from apps.courses.models import Topic, Week
from apps.courses.services import new_version
from apps.grading.models import GradingComponent, GradingScheme
from apps.materials.models import Material
from apps.testing.models import AnswerOption, Question, Test

from .models import AICourseDraft, DocumentChunk
from .schema import CourseDraft, validate_citations


def validated_draft(data, course):
    try:
        draft = CourseDraft.model_validate(data)
        validate_citations(
            draft,
            {
                str(pk)
                for pk in DocumentChunk.objects.filter(document__course=course).values_list(
                    "pk", flat=True
                )
            },
        )
        return draft
    except ValueError as exc:
        raise ValidationError(str(exc))


@transaction.atomic
def import_draft(draft, actor):
    require_visible(draft, actor)
    draft = AICourseDraft.objects.select_for_update().get(pk=draft.pk)
    if draft.imported_version:
        return draft.imported_version
    data = validated_draft(draft.data, draft.job.course)
    version = new_version(draft.job.course, actor)
    has_assignments = has_tests = False
    for index, week_data in enumerate(data.weeks, 1):
        week = Week.objects.create(
            course_version=version, number=index, order=index, title=week_data.title
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
    scheme = GradingScheme.objects.create(course_version=version)
    if has_assignments:
        GradingComponent.objects.create(
            scheme=scheme, kind="ASSIGNMENTS", weight=50 if has_tests else 100
        )
    if has_tests:
        GradingComponent.objects.create(
            scheme=scheme, kind="TESTS", weight=50 if has_assignments else 100
        )
    draft.imported_version = version
    draft.save()
    record(actor, "ai.imported", draft, new={"version": str(version.pk)})
    return version
