import pytest

from apps.academics.models import StudyGroup
from apps.enrollments.services import add_member, assign_group


def test_unassign_preserves_learning_and_can_be_reassigned(world, client_for):
    assignment = assign_group(world["teacher"], world["group"], world["course"])
    another = StudyGroup.objects.create(name="Other group", teacher=world["teacher"])
    kept = assign_group(world["teacher"], another, world["course"])
    api = client_for(world["teacher"])
    url = f"/api/v1/groups/{world['group'].pk}/unassign-course/"
    body = {"course": str(world["course"].pk)}
    assert api.post(url, body, format="json").status_code == 204
    assert api.post(url, body, format="json").status_code == 204
    assignment.refresh_from_db()
    kept.refresh_from_db()
    world["enrollment"].refresh_from_db()
    assert assignment.status == "ARCHIVED"
    assert kept.status == "ACTIVE"
    assert world["enrollment"].status == "ASSIGNED"
    assert world["enrollment"].course_version_id == world["version"].pk
    assign_group(world["teacher"], world["group"], world["course"])
    assignment.refresh_from_db()
    assert assignment.status == "ACTIVE"


@pytest.mark.parametrize("role", ["student", "other", "outsider"])
def test_unassign_rejects_other_users(world, client_for, role):
    assignment = assign_group(world["teacher"], world["group"], world["course"])
    response = client_for(world[role]).post(
        f"/api/v1/groups/{world['group'].pk}/unassign-course/",
        {"course": str(world["course"].pk)},
        format="json",
    )
    assert response.status_code in [403, 404]
    assignment.refresh_from_db()
    assert assignment.status == "ACTIVE"


def test_new_members_do_not_inherit_unassigned_course(world, client_for):
    from apps.accounts.models import User

    new_student = User.objects.create_user(
        username="new", email="new@example.test", role="STUDENT", owner_teacher=world["teacher"]
    )
    assign_group(world["teacher"], world["group"], world["course"])
    response = client_for(world["admin"]).post(
        f"/api/v1/groups/{world['group'].pk}/unassign-course/",
        {"course": str(world["course"].pk)},
        format="json",
    )
    assert response.status_code == 204
    add_member(world["teacher"], world["group"], new_student)
    assert not new_student.enrollments.exists()
