import secrets
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.common.scope import require_visible
from apps.enrollments.models import Enrollment
from apps.notifications.services import notify

from .models import TestAnswer, TestAttempt


@transaction.atomic
def start(test, student):
    require_visible(test, student)
    if student.role != "STUDENT":
        raise PermissionDenied()
    Enrollment.objects.select_for_update().get(
        student=student, course_version=test.topic.week.course_version
    )
    now = timezone.now()
    if (
        test.status != "PUBLISHED"
        or (test.available_from and now < test.available_from)
        or (test.available_until and now >= test.available_until)
    ):
        raise ValidationError("Тест сейчас недоступен.")
    attempts = TestAttempt.objects.filter(test=test, student=student)
    active = attempts.filter(status="IN_PROGRESS").first()
    if active and active.expires_at > now:
        return active
    if active:
        finalize(active, student)
    count = attempts.count()
    if count >= test.max_attempts:
        raise ValidationError("Попытки исчерпаны.")
    questions = list(test.questions.prefetch_related("options"))
    if test.shuffle_questions:
        secrets.SystemRandom().shuffle(questions)
    options = {}
    for question in questions:
        ids = [str(o.pk) for o in question.options.all()]
        if test.shuffle_answers:
            secrets.SystemRandom().shuffle(ids)
        options[str(question.pk)] = ids
    expires = now + timedelta(minutes=test.time_limit_minutes)
    if test.available_until:
        expires = min(expires, test.available_until)
    return TestAttempt.objects.create(
        test=test,
        student=student,
        attempt_number=count + 1,
        expires_at=expires,
        question_order=[str(q.pk) for q in questions],
        option_order=options,
    )


@transaction.atomic
def save_answer(attempt, student, question_id, selected):
    attempt = TestAttempt.objects.select_for_update().get(pk=attempt.pk)
    if attempt.student_id != student.pk:
        raise PermissionDenied()
    if attempt.status != "IN_PROGRESS" or timezone.now() >= attempt.expires_at:
        raise ValidationError("Время истекло или попытка завершена.")
    question = attempt.test.questions.filter(pk=question_id).first()
    if (
        not question
        or not isinstance(selected, list)
        or any(not isinstance(x, str) for x in selected)
    ):
        raise ValidationError("Некорректный ответ.")
    allowed = set(attempt.option_order[str(question.pk)])
    if (
        not set(selected) <= allowed
        or len(selected) != len(set(selected))
        or (question.type == "SINGLE_CHOICE" and len(selected) > 1)
    ):
        raise ValidationError("Варианты не принадлежат вопросу.")
    TestAnswer.objects.update_or_create(
        attempt=attempt, question=question, defaults={"selected_options": selected}
    )
    return attempt


@transaction.atomic
def finalize(attempt, student):
    attempt = TestAttempt.objects.select_for_update().get(pk=attempt.pk)
    if attempt.student_id != student.pk:
        raise PermissionDenied()
    if attempt.status != "IN_PROGRESS":
        return attempt
    answers = {str(a.question_id): set(a.selected_options) for a in attempt.answers.all()}
    earned = total = 0
    for question in attempt.test.questions.prefetch_related("options"):
        correct = {str(o.pk) for o in question.options.all() if o.is_correct}
        total += question.score
        if answers.get(str(question.pk), set()) == correct:
            earned += question.score
    attempt.score = (
        (Decimal(earned) * 100 / total).quantize(Decimal(".01")) if total else Decimal(0)
    )
    attempt.status = "EXPIRED" if timezone.now() >= attempt.expires_at else "GRADED"
    attempt.submitted_at = timezone.now()
    attempt.save()
    notify(
        student,
        "TEST_RESULT",
        attempt.test.title,
        str(attempt.score),
        "/app/grades",
        key=f"test:{attempt.pk}",
    )
    from apps.progress.services import summary

    enrollment = Enrollment.objects.get(
        student=student, course_version=attempt.test.topic.week.course_version
    )
    summary(enrollment, persist=True)
    return attempt
