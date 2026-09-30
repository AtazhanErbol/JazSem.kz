import pytest
from drf_spectacular.generators import SchemaGenerator

from apps.common.inputs import GradeInput, SubmissionInput
from apps.testing.services import start


@pytest.mark.parametrize(
    "payload", [[], {"role": "ADMIN"}, {"first_name": 123}, {"first_name": None}]
)
def test_profile_rejects_wrong_types_and_unknown_fields(world, client_for, payload):
    client = client_for(world["student"])
    assert client.patch("/api/v1/auth/me/", payload, format="json").status_code == 400
    world["student"].refresh_from_db()
    assert world["student"].role == "STUDENT"


def test_attempt_and_tree_expose_only_role_contract(world, client_for):
    student = client_for(world["student"])
    attempt = start(world["test"], world["student"])
    data = student.get(f"/api/v1/attempts/{attempt.pk}/").json()
    assert set(data["questions"][0]) == {"id", "text", "type", "options"}
    assert set(data["questions"][0]["options"][0]) == {"id", "text"}
    tree = student.get(f"/api/v1/courses/{world['course'].pk}/tree/").json()
    topic = tree["weeks"][0]["topics"][0]
    assert "source_chunks" not in topic
    assert "questions" not in topic["tests"][0]
    author = client_for(world["teacher"]).get(f"/api/v1/courses/{world['course'].pk}/tree/").json()
    question = author["weeks"][0]["topics"][0]["tests"][0]["questions"][0]
    assert any(option["is_correct"] for option in question["options"])


def test_schema_has_runtime_constraints_and_nested_role_outputs():
    schema = SchemaGenerator().get_schema(request=None, public=True)
    components = schema["components"]["schemas"]
    assert (
        components["SubmissionInputRequest"]["properties"]["text_answer"]["maxLength"]
        == SubmissionInput().fields["text_answer"].max_length
    )
    assert (
        components["GradeInputRequest"]["properties"]["comment"]["maxLength"]
        == GradeInput().fields["comment"].max_length
    )
    assert "questions" in components["AttemptDetailOutput"]["properties"]
    assert "source_chunks" not in components["StudentTopicOutput"]["properties"]
    assert "questions" in components["AuthorTestOutput"]["properties"]
    assert "encrypted_payload" not in components["MailDelivery"]["properties"]
    assert "source_snapshot" not in components["JobOutput"]["properties"]
