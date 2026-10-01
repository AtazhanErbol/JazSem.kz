import pytest
from rest_framework.exceptions import ValidationError

from apps.assignments.services import review, submit
from apps.courses.models import Topic, Week
from apps.courses.services import duplicate, publish
from apps.courses.upgrades import upgrade_students
from apps.enrollments.services import add_member, assign_group
from apps.progress.models import StudentProgress, TopicProgress
from apps.progress.services import summary
from apps.testing.services import finalize, save_answer, start


def next_version(w):
    target = duplicate(w["version"], w["teacher"])
    week = Week.objects.create(course_version=target, number=2, title="Week two")
    Topic.objects.create(week=week, title="New lesson", content="New content")
    return publish(target, w["teacher"])


def test_upgrade_preserves_results_and_adds_week(world, client_for):
    w = world
    submission = submit(w["assignment"], w["student"], "My answer", [])
    review(submission, w["teacher"], "grade", score=80, comment="Good")
    attempt = start(w["test"], w["student"])
    save_answer(attempt, w["student"], w["question"].pk, [str(w["correct"].pk)])
    finalize(attempt, w["student"])
    progress = StudentProgress.objects.create(enrollment=w["enrollment"], material=w["material"])
    read = TopicProgress.objects.create(enrollment=w["enrollment"], topic=w["topic"])
    add_member(w["teacher"], w["group"], w["student"])
    group_assignment = assign_group(w["teacher"], w["group"], w["course"])
    w["enrollment"].refresh_from_db()
    before = summary(w["enrollment"], persist=True)
    target = next_version(w)
    preview = upgrade_students(w["teacher"], w["course"], target.pk)
    assert preview["students"] == preview["groups"] == 1
    w["enrollment"].refresh_from_db()
    assert w["enrollment"].course_version_id == w["version"].pk
    upgrade_students(w["teacher"], w["course"], target.pk, apply=True)
    w["enrollment"].refresh_from_db()
    after = summary(w["enrollment"])
    assert after["completed"] == before["completed"]
    assert after["total"] == before["total"] + 1
    assert w["enrollment"].status == "IN_PROGRESS"
    submission.refresh_from_db()
    attempt.refresh_from_db()
    progress.refresh_from_db()
    read.refresh_from_db()
    group_assignment.refresh_from_db()
    assert submission.score == 80 and submission.text_answer == "My answer"
    assert submission.assignment.topic.week.course_version_id == target.pk
    assert attempt.score == 100
    assert attempt.test.topic.week.course_version_id == target.pk
    assert attempt.answers.first().question_id == attempt.test.questions.first().pk
    assert attempt.question_order == [str(attempt.test.questions.first().pk)]
    assert progress.material.topic.week.course_version_id == target.pk
    assert read.topic.week.course_version_id == target.pk
    assert group_assignment.course_version_id == target.pk
    assert client_for(w["student"]).get(f"/api/v1/attempts/{attempt.pk}/").status_code == 200
    assert upgrade_students(w["teacher"], w["course"], target.pk, apply=True)["students"] == 0


def test_changed_assignment_blocks_atomic_upgrade(world):
    target = duplicate(world["version"], world["teacher"])
    assignment = target.weeks.first().topics.first().assignments.first()
    assignment.instructions = "Changed question"
    assignment.save()
    publish(target, world["teacher"])
    with pytest.raises(ValidationError):
        upgrade_students(world["teacher"], world["course"], target.pk, apply=True)
    world["enrollment"].refresh_from_db()
    assert world["enrollment"].course_version_id == world["version"].pk


def test_active_attempt_blocks_upgrade(world):
    start(world["test"], world["student"])
    target = next_version(world)
    with pytest.raises(ValidationError, match="незавершённые"):
        upgrade_students(world["teacher"], world["course"], target.pk, apply=True)


@pytest.mark.parametrize("role", ["student", "other", "outsider"])
@pytest.mark.parametrize("action", ["update-students", "update-students-preview"])
def test_upgrade_permission(world, client_for, role, action):
    target = next_version(world)
    r = client_for(world[role]).post(
        f"/api/v1/courses/{world['course'].pk}/{action}/",
        {"version": str(target.pk)},
        format="json",
    )
    assert r.status_code in [403, 404]


def test_upgrade_preserves_revocation(world):
    e = world["enrollment"]
    e.access_revoked = True
    e.save()
    target = next_version(world)
    upgrade_students(world["admin"], world["course"], target.pk, apply=True)
    e.refresh_from_db()
    assert e.access_revoked and e.course_version_id == target.pk


def test_old_target_rejected(world):
    next_version(world)
    with pytest.raises(ValidationError):
        upgrade_students(world["teacher"], world["course"], world["version"].pk, apply=True)
