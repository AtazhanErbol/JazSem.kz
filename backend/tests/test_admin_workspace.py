from apps.courses.services import duplicate, new_version
from apps.grading.models import GradingComponent, GradingScheme
from apps.testing.models import Test as CourseTest


def test_grading_preset_uses_existing_activities_and_keeps_manual_weights(world, client_for):
    version = duplicate(world["version"], world["teacher"])
    GradingScheme.objects.filter(course_version=version).delete()
    topic = version.weeks.first().topics.first()
    CourseTest.objects.create(topic=topic, title="Final", is_final=True)
    client = client_for(world["admin"])
    url = f"/api/v1/courses/{world['course'].pk}/grading-preset/"
    response = client.post(url, {"version": str(version.pk)})
    assert response.status_code == 200
    assert {c["kind"] for c in response.data} == {"ASSIGNMENTS", "TESTS", "FINAL"}
    assert sum(c["weight"] for c in response.data) == 100
    component = GradingComponent.objects.get(scheme__course_version=version, kind="TESTS")
    component.weight = 20
    component.save()
    assert client.post(url, {"version": str(version.pk)}).status_code == 200
    component.refresh_from_db()
    assert component.weight == 20


def test_grading_preset_requires_access_editable_version_and_activities(world, client_for):
    course = world["course"]
    url = f"/api/v1/courses/{course.pk}/grading-preset/"
    published_payload = {"version": str(world["version"].pk)}
    assert client_for(world["admin"]).post(url, published_payload).status_code == 400
    assert client_for(world["student"]).post(url, published_payload).status_code == 403
    draft = new_version(course, world["teacher"])
    payload = {"version": str(draft.pk)}
    assert client_for(world["other"]).post(url, payload).status_code == 404
    assert client_for(world["teacher"]).post(url, payload).status_code == 400
    assert not GradingScheme.objects.filter(course_version=draft).exists()


def test_activity_editor_links_identify_correct_course_version(world, client_for):
    client = client_for(world["admin"])
    for resource, item in [("assignments", world["assignment"]), ("tests", world["test"])]:
        response = client.get(f"/api/v1/{resource}/{item.pk}/")
        assert response.status_code == 200
        assert response.data["course_id"] == str(world["course"].pk)
        assert response.data["course_version_id"] == str(world["version"].pk)
        assert client_for(world["other"]).get(f"/api/v1/{resource}/{item.pk}/").status_code == 404
