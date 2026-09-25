from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.assignments.services import review, submit
from apps.courses.services import duplicate, publish
from apps.enrollments.models import Enrollment
from apps.enrollments.services import add_member, assign_group, enroll
from apps.grading.services import grades
from apps.progress.models import StudentProgress
from apps.progress.services import summary
from apps.testing.models import TestAttempt as AttemptRecord
from apps.testing.services import finalize, save_answer, start


def test_group_and_individual_enrollment_deduplicate_and_inherit(world):
    w = world
    add_member(w["teacher"], w["group"], w["student"])
    assign_group(w["teacher"], w["group"], w["course"])
    enrollment = enroll(w["teacher"], w["student"], w["course"])
    assert Enrollment.objects.filter(student=w["student"], course=w["course"]).count() == 1
    assert enrollment.sources.count() == 2
    newcomer = User.objects.create_user(
        username="new", email="new@example.test", role="STUDENT", created_by=w["teacher"]
    )
    add_member(w["teacher"], w["group"], newcomer)
    assert Enrollment.objects.filter(student=newcomer, course=w["course"]).count() == 1


def test_revision_history_and_normalized_grade(world):
    w = world
    first = submit(w["assignment"], w["student"], "First answer", [])
    assert submit(w["assignment"], w["student"], "Duplicate", []).pk == first.pk
    review(first, w["teacher"], "revision", comment="Show your reasoning")
    second = submit(w["assignment"], w["student"], "Revised answer", [])
    assert second.attempt_number == 2
    review(second, w["teacher"], "grade", score=73, comment="Good")
    first.refresh_from_db()
    assert first.status == "REVISION_REQUESTED"
    assert grades(w["enrollment"])["score"] == 36.5


def test_teacher_cannot_grade_foreign_student(world, client_for):
    submission = submit(world["assignment"], world["student"], "Answer", [])
    assert (
        client_for(world["other"])
        .post(f"/api/v1/submissions/{submission.pk}/grade/", {"score": 100}, format="json")
        .status_code
        == 404
    )
    assert (
        client_for(world["student"])
        .post(f"/api/v1/submissions/{submission.pk}/grade/", {"score": 100}, format="json")
        .status_code
        == 403
    )


def test_timer_shuffle_autosave_and_exact_score(world):
    w = world
    attempt = start(w["test"], w["student"])
    assert start(w["test"], w["student"]).question_order == attempt.question_order
    save_answer(attempt, w["student"], str(w["question"].pk), [str(w["correct"].pk)])
    result = finalize(attempt, w["student"])
    assert result.score == Decimal(100)
    assert finalize(result, w["student"]).pk == result.pk
    attempt = start(w["test"], w["student"])
    AttemptRecord.objects.filter(pk=attempt.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    with pytest.raises(ValidationError):
        save_answer(attempt, w["student"], str(w["question"].pk), [str(w["correct"].pk)])
    assert finalize(attempt, w["student"]).status == "EXPIRED"
    with pytest.raises(ValidationError):
        start(w["test"], w["student"])


def test_progress_independent_of_grade(world):
    w = world
    StudentProgress.objects.create(enrollment=w["enrollment"], material=w["material"])
    submit(w["assignment"], w["student"], "Wrong answer", [])
    finalize(start(w["test"], w["student"]), w["student"])
    assert summary(w["enrollment"])["percent"] == 100
    assert grades(w["enrollment"])["score"] == 0


def test_publication_pins_old_enrollment(world):
    w = world
    draft = duplicate(w["version"], w["teacher"])
    publish(draft, w["teacher"])
    w["enrollment"].refresh_from_db()
    assert w["enrollment"].course_version_id == w["version"].pk
    draft = duplicate(w["version"], w["teacher"])
    draft.grading_scheme.components.all().delete()
    with pytest.raises(ValidationError):
        publish(draft, w["teacher"])


def test_multiple_choice_rejects_partial_and_foreign_options(world):
    w = world
    w["question"].type = "MULTIPLE_CHOICE"
    w["question"].save()
    w["wrong"].is_correct = True
    w["wrong"].save()
    attempt = start(w["test"], w["student"])
    with pytest.raises(ValidationError):
        save_answer(
            attempt, w["student"], str(w["question"].pk), ["00000000-0000-0000-0000-000000000000"]
        )
    save_answer(attempt, w["student"], str(w["question"].pk), [str(w["correct"].pk)])
    assert finalize(attempt, w["student"]).score == 0
