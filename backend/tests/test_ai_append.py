from unittest.mock import patch

import pytest
from rest_framework.exceptions import ValidationError

from apps.ai.contracts import GenerationInput
from apps.ai.jobs import snapshot
from apps.ai.models import AICourseDraft, AIJob, DocumentChunk, SourceDocument
from apps.ai.services import append_context, import_draft
from apps.courses.models import Week
from apps.courses.services import duplicate
from apps.grading.models import GradingComponent

pytestmark = pytest.mark.django_db


def make_draft(world, version):
    source = SourceDocument.objects.create(
        course=world["course"],
        uploaded_by=world["teacher"],
        filename="book.pdf",
        size=10,
        processing_status="COMPLETED",
    )
    chunk = DocumentChunk.objects.create(
        document=source, page_number=40, chunk_index=0, content="Supported material"
    )
    params = {
        "mode": "APPEND",
        "base_version": str(version.pk),
        "append_context": append_context(world["course"], version.pk, world["teacher"]),
        "weeks": 1,
    }
    job = AIJob.objects.create(
        user=world["teacher"],
        course=world["course"],
        status="COMPLETED",
        parameters=params,
        source_snapshot=snapshot(world["course"], [source.pk]),
    )
    data = {
        "title": "Do not replace title",
        "description": "Do not replace description",
        "source_gaps": [],
        "weeks": [
            {
                "title": "New week",
                "topics": [
                    {
                        "title": "New topic",
                        "content": "Supported content",
                        "source_chunks": [str(chunk.pk)],
                        "assignments": [
                            {
                                "title": "New assignment",
                                "instructions": "Explain",
                                "source_chunks": [str(chunk.pk)],
                            }
                        ],
                        "questions": [],
                    }
                ],
            }
        ],
    }
    return AICourseDraft.objects.create(job=job, data=data)


def test_append_published_clones_weeks_preserves_weights_and_enrollment(world):
    base = world["version"]
    Week.objects.create(course_version=base, number=3, order=3, title="Third week")
    title = world["course"].title
    draft = make_draft(world, base)
    target = import_draft(draft, world["teacher"])
    assert target.pk != base.pk and target.status == "DRAFT"
    assert list(target.weeks.values_list("number", flat=True)) == [1, 3, 4]
    assert (
        target.weeks.get(number=1).topics.get().assignments.get().instructions
        == world["assignment"].instructions
    )
    assert list(
        GradingComponent.objects.filter(scheme__course_version=target)
        .order_by("kind")
        .values_list("kind", "weight")
    ) == list(
        GradingComponent.objects.filter(scheme__course_version=base)
        .order_by("kind")
        .values_list("kind", "weight")
    )
    world["enrollment"].refresh_from_db()
    assert world["enrollment"].course_version_id == base.pk
    world["course"].refresh_from_db()
    assert world["course"].title == title and world["course"].current_version_id == base.pk
    assert import_draft(draft, world["teacher"]).pk == target.pk
    assert target.weeks.count() == 3


def test_append_draft_reuses_it_and_rejects_changed_structure(world):
    base = duplicate(world["version"], world["teacher"])
    draft = make_draft(world, base)
    count = world["course"].versions.count()
    assert import_draft(draft, world["teacher"]).pk == base.pk
    assert world["course"].versions.count() == count
    second = make_draft(world, base)
    Week.objects.create(course_version=base, number=9, title="Changed")
    with pytest.raises(ValidationError, match="изменились"):
        import_draft(second, world["teacher"])
    second.refresh_from_db()
    assert second.imported_version_id is None


def test_append_context_access(world, client_for):
    url = (
        f"/api/v1/ai-jobs/append-context/?course={world['course'].pk}&version={world['version'].pk}"
    )
    assert client_for(world["teacher"]).get(url).status_code == 200
    assert client_for(world["other"]).get(url).status_code == 404
    assert client_for(world["student"]).get(url).status_code == 403
    assert (
        client_for(world["teacher"]).get(url.replace(str(world["version"].pk), "bad")).status_code
        == 400
    )


def test_pdf_range_and_generation_instruction(world, client_for, settings):
    draft = make_draft(world, world["version"])
    source = SourceDocument.objects.get(course=world["course"])
    for i, page in enumerate([39, 41, 42, 43], 1):
        DocumentChunk.objects.create(
            document=source, page_number=page, chunk_index=i, content=f"Page {page}"
        )
    assert {c["page"] for c in snapshot(world["course"], [source.pk], 40, 42)} == {40, 41, 42}
    with pytest.raises(ValidationError):
        snapshot(world["course"], [source.pk], 100, 110)
    settings.AI_ENABLED = True
    settings.OPENAI_API_KEY = "fake-not-called"
    settings.OPENAI_MODEL = "fake"
    settings.AI_INPUT_PRICE = settings.AI_OUTPUT_PRICE = "1"
    with patch("apps.ai.views.require_worker"):
        result = client_for(world["teacher"]).post(
            "/api/v1/ai-jobs/",
            {
                "course": str(world["course"].pk),
                "sources": [str(source.pk)],
                "weeks": 1,
                "language": "kk",
                "mode": "APPEND",
                "base_version": str(world["version"].pk),
                "instruction": "Создай тест из пяти вопросов",
                "page_from": 40,
                "page_to": 42,
            },
            format="json",
        )
    assert result.status_code == 202, result.data
    job = AIJob.objects.get(pk=result.data["id"])
    assert job.parameters["instruction"] == "Создай тест из пяти вопросов"
    assert job.parameters["append_context"] == draft.job.parameters["append_context"]
    assert {c["page"] for c in job.source_snapshot} == {40, 41, 42}
    source.filename = "book.docx"
    source.save()
    with pytest.raises(ValidationError, match="PDF"):
        snapshot(world["course"], [source.pk], 40, 42)


@pytest.mark.parametrize(
    "extra",
    [
        {"mode": "APPEND"},
        {"page_from": 40},
        {"page_from": 42, "page_to": 40},
        {"instruction": "x" * 2001},
    ],
)
def test_invalid_generation_settings(world, extra):
    serializer = GenerationInput(
        data={
            "course": str(world["course"].pk),
            "sources": [str(world["course"].pk)],
            "weeks": 1,
            "language": "kk",
            **extra,
        }
    )
    assert not serializer.is_valid()


@pytest.mark.parametrize("filename", ["chapter.docx", "notes.png", "notes.jpg"])
def test_word_images_default_or_custom_instruction(world, client_for, settings, filename):
    source = SourceDocument.objects.create(
        course=world["course"],
        uploaded_by=world["teacher"],
        filename=filename,
        size=10,
        processing_status="COMPLETED",
    )
    DocumentChunk.objects.create(
        document=source, page_number=1, chunk_index=0, content="Recognized chapter or image text"
    )
    settings.AI_ENABLED = True
    settings.OPENAI_API_KEY = "fake-not-called"
    settings.OPENAI_MODEL = "fake"
    settings.AI_INPUT_PRICE = settings.AI_OUTPUT_PRICE = "1"
    for instruction in ["", "Составь задание по определению педагогики"]:
        with patch("apps.ai.views.require_worker"):
            result = client_for(world["teacher"]).post(
                "/api/v1/ai-jobs/",
                {
                    "course": str(world["course"].pk),
                    "sources": [str(source.pk)],
                    "weeks": 1,
                    "language": "kk",
                    "instruction": instruction,
                },
                format="json",
            )
        assert result.status_code == 202, result.data
        job = AIJob.objects.get(pk=result.data["id"])
        assert (
            job.parameters["instruction"] == instruction
            if instruction
            else "ключевые темы" in job.parameters["instruction"]
        )
        assert len(job.source_snapshot) == 1
        job.status = "CANCELLED"
        job.save()
