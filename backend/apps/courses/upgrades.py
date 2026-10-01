"""Conservative additive upgrades: map unchanged content, preserve result row IDs."""

from collections import defaultdict

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.assignments.models import Submission
from apps.audit.services import record
from apps.common.permissions import is_teacher
from apps.common.scope import require_visible
from apps.courses.models import Course
from apps.enrollments.models import Enrollment, GroupCourseAssignment
from apps.progress.models import StudentProgress, TopicProgress
from apps.progress.services import summary
from apps.testing.models import TestAnswer, TestAttempt

IGNORED = {"id", "created_at", "updated_at", "status", "source_chunks"}


def signature(obj):
    return tuple(
        (f.name, str(getattr(obj, f.attname)))
        for f in obj._meta.fields
        if f.name not in IGNORED and not f.is_relation
    )


def match_rows(old_rows, new_rows, mapping, label, exact=False):
    old_rows, new_rows = list(old_rows), list(new_rows)
    if exact and len(old_rows) != len(new_rows):
        raise ValidationError(
            f"Изменён {label}. Автоматическое обновление поддерживает добавление новых материалов без изменения старых."
        )
    candidates = defaultdict(list)
    for row in new_rows:
        candidates[signature(row)].append(row)
    pairs = []
    for row in old_rows:
        matches = candidates.get(signature(row), [])
        if len(matches) != 1:
            title = getattr(row, "title", getattr(row, "text", label))
            raise ValidationError(
                f"Не удалось однозначно сопоставить {label}: {str(title)[:120]}. Старый элемент изменён, удалён или продублирован. Восстановите его в новой версии."
            )
        target = matches.pop()
        mapping[str(row.pk)] = str(target.pk)
        pairs.append((row, target))
    return pairs


def content_mapping(source, target):
    mapping = {}
    # Use model queries: the scheme reverse accessor is not a public API.
    from apps.grading.models import GradingComponent

    match_rows(
        GradingComponent.objects.filter(scheme__course_version=source),
        GradingComponent.objects.filter(scheme__course_version=target),
        {},
        "схема оценивания",
        exact=True,
    )
    for old_week, new_week in match_rows(source.weeks.all(), target.weeks.all(), mapping, "неделя"):
        for old_topic, new_topic in match_rows(
            old_week.topics.all(), new_week.topics.all(), mapping, "тема"
        ):
            match_rows(old_topic.materials.all(), new_topic.materials.all(), mapping, "материал")
            match_rows(old_topic.assignments.all(), new_topic.assignments.all(), mapping, "задание")
            for old_test, new_test in match_rows(
                old_topic.tests.all(), new_topic.tests.all(), mapping, "тест"
            ):
                for old_q, new_q in match_rows(
                    old_test.questions.all(),
                    new_test.questions.all(),
                    mapping,
                    "вопрос теста",
                    exact=True,
                ):
                    match_rows(
                        old_q.options.all(),
                        new_q.options.all(),
                        mapping,
                        "вариант ответа",
                        exact=True,
                    )
    return mapping


@transaction.atomic
def upgrade_students(actor, course, target_id, apply=False):
    if not is_teacher(actor):
        raise PermissionDenied()
    require_visible(course, actor)
    course = Course.objects.select_for_update().get(pk=course.pk)
    target = course.versions.filter(pk=target_id, status="PUBLISHED").first()
    if course.status != "PUBLISHED" or not target or course.current_version_id != target.pk:
        raise ValidationError("Выберите текущую опубликованную версию курса.")
    # Serialize with submit/start/complete/revoke. Never take Group/User locks here:
    # group assignment takes Group -> Course -> User, and already waits on Course.
    rows = list(
        Enrollment.objects.select_for_update()
        .filter(course=course)
        .exclude(course_version=target)
        .order_by("pk")
    )
    groups = list(
        GroupCourseAssignment.objects.filter(course=course, status="ACTIVE").exclude(
            course_version=target
        )
    )
    versions = {row.course_version_id: row.course_version for row in [*rows, *groups]}
    mappings = {}
    for pk, source in versions.items():
        if source.version_number >= target.version_number:
            raise ValidationError("Обновление на более раннюю версию запрещено.")
        mappings[pk] = content_mapping(source, target)
    if TestAttempt.objects.filter(
        student_id__in=[r.student_id for r in rows],
        test__topic__week__course_version_id__in=versions,
        status="IN_PROGRESS",
    ).exists():
        raise ValidationError(
            "У студентов есть незавершённые тесты. Дождитесь их завершения и повторите обновление."
        )
    result = {
        "students": len(rows),
        "groups": len(groups),
        "version_number": target.version_number,
        "applied": apply,
    }
    if not apply:
        return result
    for enrollment in rows:
        source_id = enrollment.course_version_id
        mapping = mappings[source_id]
        submissions = Submission.objects.select_for_update().filter(
            student=enrollment.student, assignment__topic__week__course_version_id=source_id
        )
        for submission in submissions:
            submission.assignment_id = mapping[str(submission.assignment_id)]
            submission.save(update_fields=["assignment"])
        attempts = TestAttempt.objects.select_for_update().filter(
            student=enrollment.student, test__topic__week__course_version_id=source_id
        )
        for attempt in attempts:
            attempt.test_id = mapping[str(attempt.test_id)]
            attempt.question_order = [mapping[q] for q in attempt.question_order]
            attempt.option_order = {
                mapping[q]: [mapping[o] for o in options]
                for q, options in attempt.option_order.items()
            }
            attempt.save(update_fields=["test", "question_order", "option_order"])
            for answer in TestAnswer.objects.filter(attempt=attempt):
                answer.question_id = mapping[str(answer.question_id)]
                answer.selected_options = [mapping[o] for o in answer.selected_options]
                answer.save(update_fields=["question", "selected_options"])
        for model, field in [(TopicProgress, "topic"), (StudentProgress, "material")]:
            for progress in model.objects.filter(enrollment=enrollment):
                previous = str(getattr(progress, field + "_id"))
                if previous in mapping:
                    setattr(progress, field + "_id", mapping[previous])
                    progress.save(update_fields=[field])
        enrollment.course_version = target
        if enrollment.status == "COMPLETED":
            progress = summary(enrollment)
            if progress["completed"] < progress["total"]:
                enrollment.status = "IN_PROGRESS"
                enrollment.completed_at = None
        enrollment.save(update_fields=["course_version", "status", "completed_at", "updated_at"])
        record(
            actor,
            "enrollment.version_updated",
            enrollment,
            old={"version": str(source_id)},
            new={"version": str(target.pk)},
        )
    GroupCourseAssignment.objects.filter(pk__in=[g.pk for g in groups]).update(
        course_version=target
    )
    record(actor, "course.students_updated", course, new={**result, "version": str(target.pk)})
    return result
