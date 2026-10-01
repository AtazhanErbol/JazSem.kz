from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import User
from apps.assignments.services import review, submit
from apps.courses.services import duplicate
from apps.enrollments.models import Enrollment
from apps.grading.services import grades
from apps.progress.services import summary
from apps.testing.models import AnswerOption


def test_summary_page_matches_learning_rules_and_scope(world, client_for):
    row = submit(world["assignment"], world["student"], "Synthetic answer", [])
    review(row, world["teacher"], "grade", score=80)
    expected_grades, expected_progress = grades(world["enrollment"]), summary(world["enrollment"])
    with CaptureQueriesContext(connection) as queries:
        response = client_for(world["teacher"]).get("/api/v1/enrollments/summaries/")
    assert response.status_code == 200
    assert len(queries) <= 13
    row = response.json()["results"][0]
    assert row["grades"] == expected_grades and row["progress"] == expected_progress
    assert client_for(world["outsider"]).get("/api/v1/enrollments/summaries/").json()["count"] == 0
    assert client_for(world["other"]).get("/api/v1/enrollments/summaries/").json()["count"] == 0


def test_student_tree_does_not_query_question_tables(world, client_for):
    with CaptureQueriesContext(connection) as queries:
        response = client_for(world["student"]).get(f"/api/v1/courses/{world['course'].pk}/tree/")
    assert response.status_code == 200
    assert not any(
        '"testing_question"' in q["sql"] or '"testing_answeroption"' in q["sql"] for q in queries
    )


def test_summary_query_budget_is_bounded_at_25_and_100_students(world, client_for):
    client = client_for(world["teacher"])
    users = User.objects.bulk_create(
        [
            User(
                username=f"budget-{index}",
                email=f"budget-{index}@example.test",
                role="STUDENT",
                owner_teacher=world["teacher"],
            )
            for index in range(99)
        ]
    )
    for selected, count in ((users[:24], 25), (users[24:], 100)):
        Enrollment.objects.bulk_create(
            [
                Enrollment(
                    student=user,
                    course=world["course"],
                    course_version=world["version"],
                    assigned_by=world["teacher"],
                    source_type="INDIVIDUAL",
                )
                for user in selected
            ]
        )
        with CaptureQueriesContext(connection) as queries:
            response = client.get("/api/v1/enrollments/summaries/")
        assert response.status_code == 200 and response.data["count"] == count
        assert len(response.data["results"]) == 25
        assert len(queries) <= 13  # Includes auth/count, not one query per enrollment.
    response = client.get("/api/v1/enrollments/summaries/?page=4")
    assert len(response.data["results"]) == 25


def test_clone_option_query_budget_uses_bulk_insert(world):
    question = world["test"].questions.get()
    AnswerOption.objects.bulk_create(
        [AnswerOption(question=question, text=f"Extra option {index}") for index in range(100)]
    )
    with CaptureQueriesContext(connection) as queries:
        copied = duplicate(world["version"], world["teacher"])
    assert copied.weeks.get().topics.get().tests.get().questions.get().options.count() == 102
    assert len(queries) <= 50  # A row-by-row option copy alone would exceed 100.


def test_copy_preserves_parent_links_files_and_enrollment_version(world):
    copied = duplicate(world["version"], world["teacher"])
    topic = copied.weeks.first().topics.first()
    assert topic.materials.get().file.name == world["material"].file.name
    assert topic.tests.get().questions.get().options.count() == 2
    assert (
        Enrollment.objects.get(pk=world["enrollment"].pk).course_version_id == world["version"].pk
    )
    assert copied.pk != world["version"].pk and copied.status == "DRAFT"
    source = world["test"].questions.get()
    question = topic.tests.get().questions.get()
    assert question.pk != source.pk
    assert (
        question.text,
        question.type,
        question.score,
        question.explanation,
        question.order,
    ) == (source.text, source.type, source.score, source.explanation, source.order)
    fields = ["text", "is_correct", "order"]
    assert list(question.options.order_by("text").values(*fields)) == list(
        source.options.order_by("text").values(*fields)
    )
    assert not set(question.options.values_list("pk", flat=True)) & set(
        source.options.values_list("pk", flat=True)
    )
    assert topic.tests.get().status == "DRAFT" and topic.assignments.get().status == "DRAFT"
    assert list(copied.grading_scheme.components.values("kind", "weight")) == list(
        world["scheme"].components.values("kind", "weight")
    )
    option = question.options.get(is_correct=True)
    option.text = "Independent clone edit"
    option.save()
    world["correct"].refresh_from_db()
    assert world["correct"].text == "2"


def test_failed_clone_never_leaves_a_partial_version(world, monkeypatch):
    import pytest

    before = world["course"].versions.count()

    def unavailable(*args, **kwargs):
        raise RuntimeError("Synthetic insert failure")

    monkeypatch.setattr(AnswerOption.objects, "bulk_create", unavailable)
    with pytest.raises(RuntimeError):
        duplicate(world["version"], world["teacher"])
    assert world["course"].versions.count() == before
