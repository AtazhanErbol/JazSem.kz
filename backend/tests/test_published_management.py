import pytest

from apps.courses.models import Course, CourseVersion
from apps.courses.services import duplicate, publish
from apps.enrollments.models import GroupCourseAssignment


def unused_version(w):
    return publish(duplicate(w["version"], w["teacher"]), w["teacher"])


def delete(api, w, version, confirmation=None):
    return api.post(
        f"/api/v1/courses/{w['course'].pk}/delete-published/",
        {
            "version": str(version.pk),
            "confirmation": confirmation or f"{w['course'].title} · v{version.version_number}",
        },
        format="json",
    )


def test_unused_published_can_be_edited_in_place(world, client_for):
    v = unused_version(world)
    response = client_for(world["teacher"]).post(
        f"/api/v1/courses/{world['course'].pk}/edit-draft/", {"version": str(v.pk)}, format="json"
    )
    assert response.status_code == 200
    assert str(response.data["id"]) == str(v.pk)
    v.refresh_from_db()
    world["course"].refresh_from_db()
    assert v.status == "DRAFT"
    assert world["course"].current_version_id == world["version"].pk
    assert world["course"].status == "PUBLISHED"
    assert v.weeks.exists()


def test_delete_published_requires_confirmation_and_keeps_student_version(world, client_for):
    v = unused_version(world)
    api = client_for(world["teacher"])
    assert delete(api, world, v, "wrong").status_code == 400
    assert delete(api, world, v).status_code == 200
    assert not CourseVersion.objects.filter(pk=v.pk).exists()
    world["course"].refresh_from_db()
    assert world["course"].current_version_id == world["version"].pk
    world["enrollment"].refresh_from_db()
    assert world["enrollment"].course_version_id == world["version"].pk


def test_assigned_version_cannot_be_deleted_even_when_access_revoked(world, client_for):
    e = world["enrollment"]
    e.access_revoked = True
    e.save()
    assert delete(client_for(world["admin"]), world, world["version"]).status_code == 400
    assert CourseVersion.objects.filter(pk=world["version"].pk).exists()


def test_empty_group_assignment_protects_version(world, client_for):
    v = unused_version(world)
    GroupCourseAssignment.objects.create(
        group=world["group"], course=world["course"], course_version=v, assigned_by=world["teacher"]
    )
    assert delete(client_for(world["teacher"]), world, v).status_code == 400
    response = client_for(world["teacher"]).post(
        f"/api/v1/courses/{world['course'].pk}/edit-draft/", {"version": str(v.pk)}, format="json"
    )
    assert response.status_code == 200
    assert str(response.data["id"]) != str(v.pk)


@pytest.mark.parametrize("role", ["student", "other", "outsider"])
def test_other_users_cannot_delete_published(world, client_for, role):
    v = unused_version(world)
    assert delete(client_for(world[role]), world, v).status_code in [403, 404]
    assert CourseVersion.objects.filter(pk=v.pk).exists()


def test_last_unassigned_published_version_deletes_course(world, client_for):
    course = Course.objects.create(
        title="Unused", teacher=world["teacher"], discipline=world["discipline"], status="PUBLISHED"
    )
    version = CourseVersion.objects.create(
        course=course, version_number=1, status="PUBLISHED", created_by=world["teacher"]
    )
    course.current_version = version
    course.save()
    response = delete(client_for(world["admin"]), {"course": course}, version)
    assert response.status_code == 200
    assert response.data["course_deleted"]
    assert not Course.objects.filter(pk=course.pk).exists()
