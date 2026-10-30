import json
from unittest.mock import patch

import pytest

from apps.ai.lectures import LectureSection, sections
from apps.ai.models import AICourseDraft, AIJob, AIUsageLog
from apps.ai.tasks import generate_course
from apps.courses.services import duplicate
from tests.lecture_fixture import lecture_data
from tests.test_gemini_provider import configure, response


@pytest.fixture
def lecture(world, settings, monkeypatch):
    configure(settings)
    settings.GEMINI_APP_LIMITS_ENABLED = False
    monkeypatch.setattr("apps.ai.views.require_worker", lambda: None)
    version = duplicate(world["version"], world["teacher"])
    return version.weeks.get().topics.get()


@pytest.mark.parametrize(
    "language,heading",
    [("ru", "Цель лекции"), ("kk", "Дәрістің мақсаты"), ("en", "Lecture objective")],
)
def test_async_lecture_is_reviewed_before_saving_and_preserves_manual_edits(
    world, lecture, client_for, language, heading
):
    teacher = client_for(world["teacher"])
    queued = teacher.post(
        "/api/v1/ai-jobs/lecture/",
        {
            "topic": str(lecture.pk),
            "language": language,
            "audience": "Second year",
            "detail": "detailed",
            "objective": "Solve equations",
        },
        format="json",
    )
    assert queued.status_code == 202, queued.data
    job = AIJob.objects.get(pk=queued.data["id"])
    assert job.type == "LECTURE" and job.parameters["discipline"] == "Mathematics"
    with patch("apps.ai.gemini.urlopen", return_value=response(lecture_data())) as call:
        generate_course(str(job.pk))
    job.refresh_from_db()
    assert job.status == "COMPLETED", job.error
    payload = json.loads(call.call_args.args[0].data)
    assert "maxOutputTokens" not in payload["generationConfig"]
    draft = AICourseDraft.objects.get(job=job)
    assert f"## {heading}" in draft.data["content"]
    assert len(draft.data["content"].split()) >= 1200
    lecture.refresh_from_db()
    assert not lecture.content  # No automatic replacement, publication or new course version.
    edited = {**draft.data, "content": draft.data["content"] + "\n\nTeacher's manual correction."}
    result = teacher.patch(f"/api/v1/ai-drafts/{draft.pk}/", {"data": edited}, format="json")
    assert result.status_code == 200, result.data
    assert result.data["data"]["content"].endswith("Teacher's manual correction.")
    assert (
        teacher.post(f"/api/v1/ai-drafts/{draft.pk}/confirm/", {}, format="json").status_code == 400
    )
    assert client_for(world["student"]).get(f"/api/v1/ai-jobs/{job.pk}/draft/").status_code == 404
    saved = teacher.patch(
        f"/api/v1/topics/{lecture.pk}/",
        {"content": edited["content"], "expected_updated_at": lecture.updated_at.isoformat()},
        format="json",
    )
    assert saved.status_code == 200, saved.data
    conflict = teacher.patch(
        f"/api/v1/topics/{lecture.pk}/",
        {"content": "Stale content", "expected_updated_at": lecture.updated_at.isoformat()},
        format="json",
    )
    assert conflict.status_code == 409
    assert AIUsageLog.objects.get(job=job).status == "COMPLETED"


def test_regenerating_one_section_preserves_every_other_section(world, lecture, client_for):
    original = "## Introduction\n\nOriginal opening.\n\n## Theory\n\nOriginal theory.\n\n## Conclusion\n\nManual conclusion."
    teacher = client_for(world["teacher"])
    queued = teacher.post(
        "/api/v1/ai-jobs/lecture/",
        {
            "topic": str(lecture.pk),
            "operation": "EXPAND",
            "existing_content": original,
            "section_index": 1,
        },
        format="json",
    )
    assert queued.status_code == 202, queued.data
    body = "### Worked explanation\n\n" + "Explain the next operation carefully. " * 25
    with patch(
        "apps.ai.gemini.urlopen",
        return_value=response(LectureSection(content=body, source_gaps=[]).model_dump()),
    ):
        generate_course(queued.data["id"])
    draft = AICourseDraft.objects.get(job_id=queued.data["id"])
    assert draft.data["content"].startswith("## Introduction\n\nOriginal opening.\n\n## Theory\n")
    assert draft.data["content"].endswith("## Conclusion\n\nManual conclusion.")
    assert body.strip() in draft.data["content"] and "Original theory" not in draft.data["content"]


@pytest.mark.parametrize(
    "operation,extra",
    [
        ("EXPAND", {}),
        ("IMPROVE", {}),
        ("EXPAND", {"existing_content": "## One\n\nBody", "section_index": 9}),
    ],
)
def test_lecture_inputs_are_validated_before_a_paid_job(
    world, lecture, client_for, operation, extra
):
    result = client_for(world["teacher"]).post(
        "/api/v1/ai-jobs/lecture/",
        {"topic": str(lecture.pk), "operation": operation, **extra},
        format="json",
    )
    assert result.status_code == 400
    assert not AIJob.objects.exists()


def test_lecture_roles_disabled_provider_and_immutable_versions(
    world, lecture, client_for, settings
):
    for user, topic, status in [
        (world["student"], lecture, 403),
        (world["other"], lecture, 404),
        (world["teacher"], world["topic"], 400),
    ]:
        assert (
            client_for(user)
            .post("/api/v1/ai-jobs/lecture/", {"topic": str(topic.pk)}, format="json")
            .status_code
            == status
        )
    settings.AI_ENABLED = False
    result = client_for(world["teacher"]).post(
        "/api/v1/ai-jobs/lecture/", {"topic": str(lecture.pk)}, format="json"
    )
    assert result.status_code == 400 and "отключена" in str(result.data)
    assert not AIJob.objects.exists()


@pytest.mark.parametrize("failure", ["short", "html", "references", "timeout"])
def test_invalid_or_uncertain_lecture_never_replaces_content_or_replays(
    world, lecture, client_for, failure
):
    queued = client_for(world["teacher"]).post(
        "/api/v1/ai-jobs/lecture/", {"topic": str(lecture.pk)}, format="json"
    )
    data = lecture_data()
    if failure == "short":
        for key in ["introduction", "terminology", "theory", "examples", "mistakes", "conclusions"]:
            data[key] = "A brief explanation. " * (
                51 if key == "theory" else 21 if key == "examples" else 6
            )
    if failure == "html":
        data["theory"] += "<script>alert(1)</script>"
    if failure == "references":
        data["references"] = [{"source_id": "invented-book", "relevance": "Fake reference"}]
    with patch(
        "apps.ai.gemini.urlopen",
        side_effect=TimeoutError("private provider detail") if failure == "timeout" else None,
        return_value=response(data),
    ) as call:
        generate_course(queued.data["id"])
        generate_course(queued.data["id"])
    job = AIJob.objects.get(pk=queued.data["id"])
    assert job.status == "FAILED" and call.call_count == 1
    assert not AICourseDraft.objects.filter(job=job).exists()
    lecture.refresh_from_db()
    assert not lecture.content
    assert "private provider detail" not in job.error


def test_section_detection_ignores_headings_inside_code_fences():
    value = "## One\n\n```python\n## Not a heading\n```\n\n## Two\n\nTwo."
    assert [section["heading"] for section in sections(value)] == ["One", "Two"]
