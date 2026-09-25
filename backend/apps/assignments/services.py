from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import record
from apps.common.scope import require_visible
from apps.enrollments.models import Enrollment
from apps.notifications.services import notify

from .models import Submission, SubmissionFile


@transaction.atomic
def submit(assignment, student, text, files):
    require_visible(assignment, student)
    if student.role != "STUDENT":
        raise PermissionDenied()
    enrollment = Enrollment.objects.select_for_update().get(
        student=student, course_version=assignment.topic.week.course_version
    )
    if (
        enrollment.status not in ["ASSIGNED", "IN_PROGRESS", "COMPLETED"]
        or assignment.status != "PUBLISHED"
    ):
        raise ValidationError("Задание закрыто.")
    current = (
        Submission.objects.filter(assignment=assignment, student=student)
        .order_by("-attempt_number")
        .first()
    )
    if current and current.status != "REVISION_REQUESTED":
        return current
    if (
        assignment.deadline
        and timezone.now() > assignment.deadline
        and not assignment.allow_late_submission
    ):
        raise ValidationError("Срок сдачи истёк.")
    if not text.strip() and not files:
        raise ValidationError("Добавьте ответ или файл.")
    from apps.materials.validation import validate_upload

    if len(files) > 5:
        raise ValidationError("Не более пяти файлов на одну работу.")

    for file in files:
        validate_upload(file)
    submission = Submission.objects.create(
        assignment=assignment,
        student=student,
        attempt_number=current.attempt_number + 1 if current else 1,
        text_answer=text,
        status="RESUBMITTED" if current else "SUBMITTED",
    )
    for file in files:
        SubmissionFile.objects.create(
            submission=submission,
            file=file,
            original_filename=file.name,
            mime_type=file.content_type,
            size=file.size,
        )
    from apps.progress.services import summary

    summary(enrollment, persist=True)
    return submission


@transaction.atomic
def review(submission, actor, action, score=None, comment=""):
    require_visible(submission, actor)
    if actor.role not in ["ADMIN", "TEACHER"] and not actor.is_superuser:
        raise PermissionDenied()
    submission = Submission.objects.select_for_update().get(pk=submission.pk)
    if submission.status not in ["SUBMITTED", "RESUBMITTED", "UNDER_REVIEW", "GRADED"]:
        raise ValidationError("Работа недоступна для проверки.")
    old = {"score": str(submission.score), "status": submission.status}
    if action == "review":
        if submission.status == "GRADED":
            raise ValidationError("Работа уже оценена.")
        submission.status = "UNDER_REVIEW"
    elif action == "revision":
        if not comment.strip():
            raise ValidationError("Укажите причину доработки.")
        submission.status = "REVISION_REQUESTED"
        submission.score = None
    else:
        try:
            value = Decimal(str(score))
            if not value.is_finite() or not 0 <= value <= submission.assignment.max_score:
                raise ValueError()
        except Exception:
            raise ValidationError("Оценка вне допустимого диапазона.")
        submission.score = (value * 100 / submission.assignment.max_score).quantize(Decimal(".01"))
        submission.status = "GRADED"
        submission.graded_at = timezone.now()
        submission.graded_by = actor
    submission.teacher_comment = comment
    submission.save()
    record(
        actor,
        "submission." + action,
        submission,
        old,
        {"score": str(submission.score), "status": submission.status},
    )
    if action != "review":
        title = (
            "Жұмыс тексерілді"
            if submission.student.preferred_language == "kk"
            else "Работа проверена"
        )
        notify(submission.student, submission.status, title, comment, "/app/grades", email=True)
    return submission
