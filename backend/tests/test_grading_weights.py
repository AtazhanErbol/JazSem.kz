import pytest

from apps.courses.services import duplicate


def test_weights_saved_together_and_invalid_total_rejected(world, client_for):
    draft = duplicate(world["version"], world["teacher"])
    api = client_for(world["teacher"])
    url = f"/api/v1/courses/{world['course'].pk}/grading-weights/"
    assert (
        api.post(
            url,
            {"version": str(draft.pk), "weights": {"ASSIGNMENTS": 60, "TESTS": 100}},
            format="json",
        ).status_code
        == 400
    )
    assert (
        api.post(
            url,
            {"version": str(draft.pk), "weights": {"ASSIGNMENTS": 60, "TESTS": 40, "FINAL": 0}},
            format="json",
        ).status_code
        == 200
    )
    assert dict(draft.grading_scheme.components.values_list("kind", "weight")) == {
        "ASSIGNMENTS": 60,
        "TESTS": 40,
    }


@pytest.mark.parametrize("role", ["student", "other"])
def test_weights_permissions(world, client_for, role):
    draft = duplicate(world["version"], world["teacher"])
    assert client_for(world[role]).post(
        f"/api/v1/courses/{world['course'].pk}/grading-weights/",
        {"version": str(draft.pk), "weights": {"TESTS": 100}},
        format="json",
    ).status_code in [403, 404]


def test_published_weights_immutable(world, client_for):
    assert (
        client_for(world["admin"])
        .post(
            f"/api/v1/courses/{world['course'].pk}/grading-weights/",
            {"version": str(world["version"].pk), "weights": {"TESTS": 100}},
            format="json",
        )
        .status_code
        == 400
    )
