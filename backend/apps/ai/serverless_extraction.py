"""Resume document extraction between Function invocations without partial citations."""

import time
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.common.serverless import publish

from . import delivery
from .configuration import source_size_exceeded
from .extraction import extract_pages
from .models import DocumentChunk, SourceDocument, SourceExtractionState, TaskDelivery


def extract_chunk(pk, token=None, next_page=0):
    document = SourceDocument.objects.get(pk=pk)
    if token is None:
        lease = delivery.claim(source=document)
        if lease is None:
            return
    else:
        lease = TaskDelivery.objects.filter(
            source=document,
            status="RUNNING",
            lease_token=token,
            lease_until__gt=timezone.now(),
        ).first()
        if lease is None:
            return
    step_token = uuid.uuid4()
    try:
        with transaction.atomic():
            delivery.lock_course(lease)
            if delivery.owned(lease) is None:
                return
            if token is None:
                state, _ = SourceExtractionState.objects.update_or_create(
                    source=document,
                    defaults={
                        "lease_token": lease.lease_token,
                        "step_token": None,
                        "next_page": 0,
                        "chars": 0,
                        "elapsed": 0,
                        "chunks": [],
                    },
                )
            else:
                state = SourceExtractionState.objects.filter(
                    source=document, lease_token=lease.lease_token
                ).first()
            if state is None or state.next_page != next_page or state.step_token is not None:
                return
            state.step_token = step_token
            state.save(update_fields=["step_token"])

        with document.file.open("rb") as file:
            data = file.read(settings.MAX_UPLOAD_BYTES + 1)
        if len(data) > settings.MAX_UPLOAD_BYTES:
            raise ValueError("Source byte limit")
        started = time.monotonic()
        prior_elapsed = state.elapsed
        for page, text in extract_pages(
            data, document.filename, start_page=state.next_page, elapsed=prior_elapsed
        ):
            state.chars += len(text)
            if source_size_exceeded(state.chars, multiplier=5):
                raise ValueError("Source character limit")
            normalized = " ".join(text.split())
            state.chunks.extend(
                [page, normalized[offset : offset + 3500]]
                for offset in range(0, len(normalized), 3500)
                if normalized[offset : offset + 3500]
            )
            state.next_page = page
            state.elapsed = prior_elapsed + time.monotonic() - started
            with transaction.atomic():
                delivery.lock_course(lease)
                if delivery.owned(lease) is None:
                    return
                changed = SourceExtractionState.objects.filter(
                    source=document, lease_token=lease.lease_token, step_token=step_token
                ).update(
                    next_page=state.next_page,
                    chars=state.chars,
                    elapsed=state.elapsed,
                    chunks=state.chunks,
                )
                if not changed or not delivery.heartbeat(lease):
                    return
            # Yield between pages so the next invocation can resume before the
            # hosting Function deadline; this is not an overall extraction cap.
            if time.monotonic() - started >= 170:
                break
        else:
            if not state.chunks:
                raise ValueError("Empty source")
            with transaction.atomic():
                delivery.lock_course(lease)
                locked = delivery.owned(lease)
                if locked is None:
                    return
                if document.chunks.exists():
                    raise ValueError("Existing immutable chunks")
                DocumentChunk.objects.bulk_create(
                    [
                        DocumentChunk(
                            document=document, page_number=page, chunk_index=index, content=text
                        )
                        for index, (page, text) in enumerate(state.chunks)
                    ]
                )
                SourceDocument.objects.filter(pk=pk, processing_status="PROCESSING").update(
                    extracted_text="\n".join(text for _, text in state.chunks),
                    processing_status="COMPLETED",
                    error="",
                )
                delivery.complete(locked)
                state.delete()
            return

        # Fence duplicates before publishing the continuation. If publishing
        # fails, the durable delivery watchdog recovers the expired lease.
        with transaction.atomic():
            delivery.lock_course(lease)
            if delivery.owned(lease) is None:
                return
            SourceExtractionState.objects.filter(
                source=document, lease_token=lease.lease_token, step_token=step_token
            ).update(step_token=None)
        from .tasks import extract_document_continuation

        try:
            publish(
                extract_document_continuation,
                [str(pk), str(lease.lease_token), state.next_page],
            )
        except Exception:
            delivery.event(lease, "continuation_publish_failed")
    except Exception:
        delivery.failed(lease, "EXTRACTION_FAILED")
