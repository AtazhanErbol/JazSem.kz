import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.ai.models import AIJob, DocumentChunk, SourceDocument, TaskDelivery

pytestmark = pytest.mark.django_db


def source(world, status="COMPLETED"):
    obj = SourceDocument.objects.create(
        course=world["course"],
        uploaded_by=world["teacher"],
        filename="picture.png",
        size=4,
        file=SimpleUploadedFile("picture.png", b"test"),
        processing_status=status,
    )
    DocumentChunk.objects.create(document=obj, page_number=1, chunk_index=0, content="Text")
    return obj


def test_private_preview_and_text(world, client_for):
    obj = source(world)
    client = client_for(world["teacher"])
    response = client.get(f"/api/v1/sources/{obj.pk}/preview/")
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert response["Cache-Control"] == "private, no-store"
    assert b"".join(response.streaming_content) == b"test"
    response.close()
    assert client_for(world["other"]).get(f"/api/v1/sources/{obj.pk}/preview/").status_code == 404
    assert client_for(world["student"]).get(f"/api/v1/sources/{obj.pk}/chunks/").status_code == 404
    assert client.get(f"/api/v1/sources/{obj.pk}/chunks/").data["results"][0]["content"] == "Text"


def test_unused_delete_confirmation_and_blob_cleanup(
    world, client_for, django_capture_on_commit_callbacks
):
    obj = source(world)
    TaskDelivery.objects.create(source=obj, status="DONE")
    storage, name = obj.file.storage, obj.file.name
    url = f"/api/v1/sources/{obj.pk}/delete-file/"
    assert client_for(world["other"]).post(url, {"filename": obj.filename}).status_code == 404
    client = client_for(world["teacher"])
    assert client.post(url, {"filename": "wrong"}).status_code == 400
    assert storage.exists(name)
    with django_capture_on_commit_callbacks(execute=True):
        assert client.post(url, {"filename": obj.filename}).status_code == 204
    assert not SourceDocument.objects.filter(pk=obj.pk).exists()
    assert not storage.exists(name)


@pytest.mark.parametrize("reason", ["processing", "delivery", "job", "citation"])
def test_used_or_processing_sources_are_protected(world, client_for, reason):
    obj = source(world, "PROCESSING" if reason == "processing" else "COMPLETED")
    if reason == "delivery":
        TaskDelivery.objects.create(source=obj, status="RUNNING")
    if reason == "job":
        AIJob.objects.create(
            course=world["course"],
            user=world["teacher"],
            status="FAILED",
            source_snapshot=[{"document": str(obj.pk)}],
        )
    if reason == "citation":
        topic = world["topic"]
        topic.source_chunks = [str(obj.chunks.get().pk)]
        topic.save()
    assert (
        client_for(world["teacher"])
        .post(f"/api/v1/sources/{obj.pk}/delete-file/", {"filename": obj.filename})
        .status_code
        == 400
    )
    assert SourceDocument.objects.filter(pk=obj.pk).exists()
    assert obj.file.storage.exists(obj.file.name)
