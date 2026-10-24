from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.ai.models import DocumentChunk, SourceDocument, SourceExtractionState, TaskDelivery
from apps.ai.serverless_extraction import extract_chunk


def source(world):
    obj = SourceDocument.objects.create(
        course=world["course"],
        uploaded_by=world["teacher"],
        file=SimpleUploadedFile("source.txt", b"synthetic source"),
        filename="source.txt",
        mime_type="text/plain",
        size=16,
    )
    TaskDelivery.objects.create(source=obj)
    return obj


@pytest.mark.django_db
def test_simple_extraction_keeps_immutable_citation_contract(world):
    obj = source(world)
    extract_chunk(str(obj.pk))
    obj.refresh_from_db()
    assert obj.processing_status == "COMPLETED"
    original = list(obj.chunks.values_list("id", "content"))
    assert original[0][1] == "synthetic source"
    extract_chunk(str(obj.pk))
    assert list(obj.chunks.values_list("id", "content")) == original
    assert not SourceExtractionState.objects.filter(source=obj).exists()


@pytest.mark.django_db
def test_long_document_continues_without_exposing_partial_citations(world):
    obj = source(world)
    with (
        patch(
            "apps.ai.serverless_extraction.extract_pages", return_value=iter([(1, "First page")])
        ),
        patch("apps.ai.serverless_extraction.time.monotonic", side_effect=[0, 175, 175]),
        patch("apps.ai.serverless_extraction.publish") as continuation,
    ):
        extract_chunk(str(obj.pk))
    obj.refresh_from_db()
    assert obj.processing_status == "PROCESSING"
    assert not DocumentChunk.objects.filter(document=obj).exists()
    state = SourceExtractionState.objects.get(source=obj)
    assert state.chunks == [[1, "First page"]]
    args = continuation.call_args.args[1]
    with patch(
        "apps.ai.serverless_extraction.extract_pages", return_value=iter([(2, "Second page")])
    ) as read:
        extract_chunk(*args)
    assert read.call_args.kwargs["start_page"] == 1
    obj.refresh_from_db()
    assert obj.processing_status == "COMPLETED"
    assert list(obj.chunks.order_by("chunk_index").values_list("page_number", "content")) == [
        (1, "First page"),
        (2, "Second page"),
    ]
    # An already delivered continuation cannot overwrite citation IDs.
    ids = list(obj.chunks.values_list("id", flat=True))
    extract_chunk(*args)
    assert list(obj.chunks.values_list("id", flat=True)) == ids


@pytest.mark.django_db
def test_extraction_failure_does_not_publish_partial_chunks(world):
    obj = source(world)
    with patch("apps.ai.serverless_extraction.extract_pages", side_effect=ValueError("synthetic")):
        extract_chunk(str(obj.pk))
    obj.refresh_from_db()
    assert obj.processing_status == "FAILED"
    assert not obj.chunks.exists()
