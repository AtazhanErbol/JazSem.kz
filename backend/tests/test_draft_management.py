import pytest

from apps.courses.models import Course, CourseVersion
from apps.courses.services import new_version


def test_edit_published_reuses_draft_without_changing_student_version(world, client_for):
    api = client_for(world["teacher"])
    url = f"/api/v1/courses/{world['course'].pk}/edit-draft/"
    body = {"version": str(world["version"].pk)}
    first = api.post(url, body, format="json")
    assert first.status_code == 200
    assert first.data["status"] == "DRAFT"
    assert api.post(url, body, format="json").data["id"] == first.data["id"]
    world["course"].refresh_from_db()
    world["enrollment"].refresh_from_db()
    assert world["course"].current_version_id == world["version"].pk
    assert world["enrollment"].course_version_id == world["version"].pk
    draft = CourseVersion.objects.get(pk=first.data["id"])
    assert draft.weeks.count() == world["version"].weeks.count()
    assert draft.weeks.first().topics.first().tests.count() == 1


def test_delete_only_confirmed_draft_keeps_published(world, client_for):
    course = world["course"]
    draft = new_version(course, world["teacher"])
    another = new_version(course, world["teacher"])
    api = client_for(world["teacher"])
    url = f"/api/v1/courses/{course.pk}/delete-draft/"
    body = {"version": str(draft.pk), "confirmation": "wrong"}
    assert api.post(url, body, format="json").status_code == 400
    assert CourseVersion.objects.filter(pk=draft.pk).exists()
    body["confirmation"] = f"{course.title} · v{draft.version_number}"
    response = api.post(url, body, format="json")
    assert response.status_code == 200
    assert not response.data["course_deleted"]
    assert not CourseVersion.objects.filter(pk=draft.pk).exists()
    assert CourseVersion.objects.filter(pk=another.pk).exists()
    assert CourseVersion.objects.filter(pk=world["version"].pk).exists()
    body = {"version": str(world["version"].pk), "confirmation": f"{course.title} · v1"}
    assert api.post(url, body, format="json").status_code == 400


def test_last_unused_draft_deletes_empty_course(world, client_for):
    course = Course.objects.create(
        title="Unused", teacher=world["teacher"], discipline=world["discipline"]
    )
    draft = new_version(course, world["teacher"])
    response = client_for(world["admin"]).post(
        f"/api/v1/courses/{course.pk}/delete-draft/",
        {"version": str(draft.pk), "confirmation": "Unused · v1"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["course_deleted"]
    assert not Course.objects.filter(pk=course.pk).exists()


@pytest.mark.parametrize("role", ["student", "other"])
@pytest.mark.parametrize("action", ["edit-draft", "delete-draft"])
def test_other_users_cannot_change_drafts(world, client_for, role, action):
    draft = new_version(world["course"], world["teacher"])
    body = (
        {"version": str(world["version"].pk)}
        if action == "edit-draft"
        else {
            "version": str(draft.pk),
            "confirmation": f"{world['course'].title} · v{draft.version_number}",
        }
    )
    response = client_for(world[role]).post(
        f"/api/v1/courses/{world['course'].pk}/{action}/", body, format="json"
    )
    assert response.status_code in [403, 404]
    assert CourseVersion.objects.filter(pk=draft.pk).exists()


def test_protected_reference_prevents_delete(world, client_for):
    draft = new_version(world["course"], world["teacher"])
    enrollment = world["enrollment"]
    enrollment.course_version = draft
    enrollment.save()
    response = client_for(world["admin"]).post(
        f"/api/v1/courses/{world['course'].pk}/delete-draft/",
        {
            "version": str(draft.pk),
            "confirmation": f"{world['course'].title} · v{draft.version_number}",
        },
        format="json",
    )
    assert response.status_code == 400
    assert CourseVersion.objects.filter(pk=draft.pk).exists()
