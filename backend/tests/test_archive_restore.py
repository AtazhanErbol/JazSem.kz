import pytest

from apps.courses.models import Course


@pytest.mark.parametrize(
    "resource,key,status",
    [
        ("disciplines", "discipline", "ACTIVE"),
        ("groups", "group", "ACTIVE"),
        ("courses", "course", "PUBLISHED"),
    ],
)
def test_restore_preserves_records(world, client_for, resource, key, status):
    obj = world[key]
    api = client_for(world["admin"])
    url = f"/api/v1/{resource}/{obj.pk}/"
    assert api.post(url + "archive/", {}, format="json").status_code == 200
    assert api.post(url + "restore/", {}, format="json").status_code == 200
    obj.refresh_from_db()
    assert obj.status == status
    assert api.post(url + "restore/", {}, format="json").status_code == 200
    world["enrollment"].refresh_from_db()
    assert world["enrollment"].course_version_id == world["version"].pk


@pytest.mark.parametrize(
    "resource,key", [("disciplines", "discipline"), ("groups", "group"), ("courses", "course")]
)
def test_restore_permissions(world, client_for, resource, key):
    obj = world[key]
    obj.status = "ARCHIVED"
    obj.save()
    url = f"/api/v1/{resource}/{obj.pk}/restore/"
    for role in ["student", "other"]:
        assert client_for(world[role]).post(url, {}, format="json").status_code in [403, 404]
    obj.refresh_from_db()
    assert obj.status == "ARCHIVED"
    expected = 403 if resource == "disciplines" else 200
    assert client_for(world["teacher"]).post(url, {}, format="json").status_code == expected


def test_restore_draft_and_archived_discipline(world, client_for):
    api = client_for(world["teacher"])
    course = Course.objects.create(
        title="Draft", teacher=world["teacher"], discipline=world["discipline"], status="ARCHIVED"
    )
    url = f"/api/v1/courses/{course.pk}/restore/"
    assert api.post(url, {}, format="json").data["status"] == "DRAFT"
    course.status = "ARCHIVED"
    course.save()
    world["discipline"].status = "ARCHIVED"
    world["discipline"].save()
    assert api.post(url, {}, format="json").status_code == 400
    course.refresh_from_db()
    assert course.status == "ARCHIVED"


def test_group_restore_keeps_assignments_archived(world, client_for):
    from apps.enrollments.services import assign_group

    assignment = assign_group(world["teacher"], world["group"], world["course"])
    api = client_for(world["teacher"])
    url = f"/api/v1/groups/{world['group'].pk}/"
    assert api.post(url + "archive/", {}, format="json").status_code == 200
    assert api.post(url + "restore/", {}, format="json").status_code == 200
    assignment.refresh_from_db()
    assert assignment.status == "ARCHIVED"
