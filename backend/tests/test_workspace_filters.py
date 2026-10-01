from datetime import timedelta

from django.utils import timezone

from apps.assignments.services import review, submit
from apps.enrollments.services import add_member, assign_group


def test_workspace_filters_narrow_results_without_expanding_scope(world, client_for):
    teacher = client_for(world["teacher"])
    add_member(world["teacher"], world["group"], world["student"])
    assign_group(world["teacher"], world["group"], world["course"])
    paths = [
        f"courses/?group={world['group'].pk}",
        f"users/?role=STUDENT&group={world['group'].pk}",
        f"assignments/?course={world['course'].pk}&teacher={world['teacher'].pk}",
        f"tests/?course={world['course'].pk}",
        f"enrollments/summaries/?group={world['group'].pk}&teacher={world['teacher'].pk}",
    ]
    for path in paths:
        result = teacher.get("/api/v1/" + path)
        assert result.status_code == 200, (path, result.data)
        assert result.data["count"] == 1, path
    for path in [paths[0], paths[1], *paths[2:]]:
        result = client_for(world["other"]).get("/api/v1/" + path)
        assert result.status_code == 200 and result.data["count"] == 0, path
    teachers = client_for(world["admin"]).get(
        f"/api/v1/users/?role=TEACHER&discipline={world['discipline'].pk}"
    )
    assert teachers.status_code == 200 and teachers.data["count"] == 1
    members = teacher.get(f"/api/v1/groups/{world['group'].pk}/members/").json()
    assert members[0]["student_email"] == world["student"].email
    assert members[0]["student_name"] == world["student"].email


def test_deadline_and_review_queue_are_real_filters(world, client_for):
    client = client_for(world["teacher"])
    assignment = world["assignment"]
    url = "/api/v1/assignments/"
    assert client.get(url, {"due": "none"}).data["count"] == 1
    assignment.deadline = timezone.now() + timedelta(days=1)
    assignment.save(update_fields=["deadline"])
    assert client.get(url, {"due": "future"}).data["count"] == 1
    assert client.get(url, {"due": "overdue"}).data["count"] == 0
    assert client.get(url, {"due": "invalid"}).status_code == 400
    row = submit(assignment, world["student"], "Synthetic answer", [])
    queue = f"/api/v1/submissions/?pending=true&course={world['course'].pk}"
    assert client.get(queue).data["count"] == 1
    response = client.post(f"/api/v1/submissions/{row.pk}/grade/", {"score": 101})
    assert response.status_code == 400 and "score" in response.data["errors"]
    review(row, world["teacher"], "revision", comment="Please revise")
    assert client.get(queue).data["count"] == 0


def test_ai_history_and_sources_paginate_with_scope_and_no_snapshot_text(world, client_for):
    from apps.ai.models import AIJob, SourceDocument

    for index in range(26):
        AIJob.objects.create(
            user=world["teacher"],
            course=world["course"],
            status="FAILED",
            source_snapshot=[
                {"document": str(world["course"].pk), "text": "PRIVATE SOURCE SNAPSHOT"}
            ],
        )
        SourceDocument.objects.create(
            uploaded_by=world["teacher"],
            course=world["course"],
            filename=f"Synthetic {index}.txt",
            file=f"private/synthetic-{index}.txt",
            mime_type="text/plain",
            size=1,
            processing_status="FAILED",
        )
    teacher = client_for(world["teacher"])
    for endpoint in ["ai-jobs", "sources"]:
        url = f"/api/v1/{endpoint}/?course={world['course'].pk}"
        first, second = teacher.get(url), teacher.get(url + "&page=2")
        assert first.status_code == second.status_code == 200
        assert first.data["count"] == second.data["count"] == 26
        assert len(first.data["results"]) == 25 and len(second.data["results"]) == 1
        assert not (
            {r["id"] for r in first.data["results"]} & {r["id"] for r in second.data["results"]}
        )
        assert "PRIVATE SOURCE SNAPSHOT" not in str(first.data) + str(second.data)
        assert "source_snapshot" not in str(first.data)
        assert client_for(world["other"]).get(url).data["count"] == 0
        detail = f"/api/v1/{endpoint}/{second.data['results'][0]['id']}/"
        assert client_for(world["other"]).get(detail).status_code == 404
        assert client_for(world["student"]).get(detail).status_code in {403, 404}
