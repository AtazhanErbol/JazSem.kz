import pytest

from apps.assignments.services import submit
from apps.enrollments.services import add_member, assign_group, enroll
from apps.testing.services import start


def test_close_restore_preserves_work_and_blocks_links(world, client_for):
    w = world
    submission = submit(w["assignment"], w["student"], "Answer", [])
    attempt = start(w["test"], w["student"])
    teacher = client_for(w["teacher"])
    student = client_for(w["student"])
    base = f"/api/v1/enrollments/{w['enrollment'].pk}/"
    for _ in range(2):
        assert teacher.post(base + "close-access/", {}, format="json").status_code == 200
    for resource, obj in [
        ("courses", w["course"]),
        ("materials", w["material"]),
        ("assignments", w["assignment"]),
        ("tests", w["test"]),
        ("enrollments", w["enrollment"]),
        ("submissions", submission),
        ("attempts", attempt),
    ]:
        assert student.get(f"/api/v1/{resource}/{obj.pk}/").status_code == 404
    assert (
        student.post(f"/api/v1/attempts/{attempt.pk}/finish/", {}, format="json").status_code == 404
    )
    add_member(w["teacher"], w["group"], w["student"])
    assign_group(w["teacher"], w["group"], w["course"])
    enroll(w["teacher"], w["student"], w["course"])
    w["enrollment"].refresh_from_db()
    assert w["enrollment"].access_revoked
    assert teacher.post(base + "restore-access/", {}, format="json").status_code == 200
    w["enrollment"].refresh_from_db()
    assert not w["enrollment"].access_revoked
    assert w["enrollment"].course_version_id == w["version"].pk
    submission.refresh_from_db()
    assert submission.text_answer == "Answer"
    assert student.get(f"/api/v1/courses/{w['course'].pk}/").status_code == 200
    assert student.get(f"/api/v1/attempts/{attempt.pk}/").status_code == 200


@pytest.mark.parametrize("role", ["student", "other", "outsider"])
@pytest.mark.parametrize("action", ["close-access", "restore-access"])
def test_access_requires_owner_or_admin(world, client_for, role, action):
    response = client_for(world[role]).post(
        f"/api/v1/enrollments/{world['enrollment'].pk}/{action}/", {}, format="json"
    )
    assert response.status_code in [403, 404]
    world["enrollment"].refresh_from_db()
    assert not world["enrollment"].access_revoked


def test_admin_can_close_access(world, client_for):
    assert (
        client_for(world["admin"])
        .post(f"/api/v1/enrollments/{world['enrollment'].pk}/close-access/", {}, format="json")
        .status_code
        == 200
    )
