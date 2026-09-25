import pytest

from apps.courses.services import duplicate


@pytest.mark.parametrize(
    "resource,key",
    [
        ("courses", "course"),
        ("materials", "material"),
        ("assignments", "assignment"),
        ("tests", "test"),
        ("groups", "group"),
    ],
)
def test_teacher_cannot_read_or_write_foreign_objects(world, client_for, resource, key):
    client = client_for(world["other"])
    url = f"/api/v1/{resource}/{world[key].pk}/"
    assert client.get(url).status_code == 404
    assert client.patch(url, {"title": "Hijacked"}, format="json").status_code == 404


def test_student_isolation(world, client_for):
    client = client_for(world["student"])
    assert client.get(f"/api/v1/users/{world['outsider'].pk}/").status_code == 404
    assert (
        client.post(
            "/api/v1/groups/", {"name": "bad", "teacher": str(world["teacher"].pk)}, format="json"
        ).status_code
        == 403
    )
    assert client.get("/api/v1/ai-jobs/").data["count"] == 0
    assert (
        client_for(world["outsider"]).get(f"/api/v1/courses/{world['course'].pk}/").status_code
        == 404
    )


def test_student_never_sees_answer_keys(world, client_for):
    client = client_for(world["student"])
    response = client.get("/api/v1/options/")
    assert response.status_code == 200
    assert all("is_correct" not in o for o in response.data["results"])
    assert "explanation" not in client.get("/api/v1/questions/").data["results"][0]


def test_private_download_scope(world, client_for):
    from rest_framework.test import APIClient

    url = f"/api/v1/materials/{world['material'].pk}/download/"
    assert APIClient().get(url).status_code == 403
    assert client_for(world["outsider"]).get(url).status_code == 404
    response = client_for(world["student"]).get(url)
    assert response.status_code == 200
    assert response["Cache-Control"] == "private, no-store"
    response.close()


def test_draft_hidden_and_published_version_frozen(world, client_for):
    draft = duplicate(world["version"], world["teacher"])
    student = client_for(world["student"])
    teacher = client_for(world["teacher"])
    assert student.get(f"/api/v1/weeks/?course_version={draft.pk}").data["count"] == 0
    assert (
        teacher.patch(
            f"/api/v1/topics/{world['topic'].pk}/", {"title": "mutate"}, format="json"
        ).status_code
        == 400
    )
    assert (
        teacher.post(
            "/api/v1/materials/",
            {"topic": str(world["topic"].pk), "title": "late mutation"},
            format="json",
        ).status_code
        == 400
    )


def test_foreign_parent_injection(world, client_for):
    client = client_for(world["other"])
    assert (
        client.post(
            "/api/v1/topics/", {"week": str(world["week"].pk), "title": "Injected"}, format="json"
        ).status_code
        == 403
    )
