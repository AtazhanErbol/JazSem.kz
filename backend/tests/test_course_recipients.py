import pytest

from apps.enrollments.services import assign_group


def test_recipients_persist_and_report_selected(world, client_for):
    assign_group(world["teacher"], world["group"], world["course"])
    url = f"/api/v1/courses/{world['course'].pk}/recipients/"
    for role in ["admin", "teacher"]:
        api = client_for(world[role])
        students = api.get(url, {"kind": "students", "selected": str(world["student"].pk)})
        assert students.status_code == 200
        assert students.data["count"] == 1
        assert students.data["selected_assigned"] is True
        assert students.data["results"][0]["recipient_id"] == str(world["student"].pk)
        groups = api.get(url, {"kind": "groups", "selected": str(world["group"].pk)})
        assert groups.data["selected_assigned"] is True
        assert groups.data["results"][0]["name"] == world["group"].name
    assert (
        client_for(world["teacher"])
        .get(url, {"kind": "students", "selected": str(world["outsider"].pk)})
        .data["selected_assigned"]
        is False
    )


@pytest.mark.parametrize("role", ["student", "other", "outsider"])
def test_recipients_not_visible_to_other_users(world, client_for, role):
    response = client_for(world[role]).get(f"/api/v1/courses/{world['course'].pk}/recipients/")
    assert response.status_code in [403, 404]


def test_archived_group_assignment_can_be_assigned_again(world, client_for):
    assignment = assign_group(world["teacher"], world["group"], world["course"])
    assignment.status = "ARCHIVED"
    assignment.save()
    response = client_for(world["teacher"]).get(
        f"/api/v1/courses/{world['course'].pk}/recipients/",
        {"kind": "groups", "selected": str(world["group"].pk)},
    )
    assert response.data["count"] == 0
    assert response.data["selected_assigned"] is False
