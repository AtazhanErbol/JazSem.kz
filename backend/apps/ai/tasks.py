import time
from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

from .extraction import extract_pages
from .models import AICourseDraft, AIJob, AIUsageLog, DocumentChunk, SourceDocument
from .provider import OpenAIProvider
from .schema import CourseDraft, validate_citations


@shared_task(soft_time_limit=480, time_limit=540)
def extract_document(pk):
    document = SourceDocument.objects.get(pk=pk)
    if document.processing_status == "COMPLETED":
        return
    document.processing_status = "PROCESSING"
    document.save()
    try:
        with document.file.open("rb") as file:
            pages = list(extract_pages(file.read(), document.filename))
        chunks = []
        for page, text in pages:
            normalized = " ".join(text.split())
            for offset in range(0, len(normalized), 3500):
                content = normalized[offset : offset + 3500]
                if content:
                    chunks.append(
                        DocumentChunk(
                            document=document,
                            page_number=page,
                            chunk_index=len(chunks),
                            content=content,
                        )
                    )
        if not chunks or sum(len(c.content) for c in chunks) > settings.AI_MAX_SOURCE_CHARS * 5:
            raise ValueError("Empty or oversized source")
        with transaction.atomic():
            document.chunks.all().delete()
            DocumentChunk.objects.bulk_create(chunks)
            document.extracted_text = "\n".join(c.content for c in chunks)
            document.processing_status = "COMPLETED"
            document.error = ""
            document.save()
    except Exception as exc:
        document.processing_status = "FAILED"
        document.error = (
            f"Extraction failed ({type(exc).__name__}); verify file and OCR configuration."
        )
        document.save()


@shared_task(bind=True, max_retries=settings.AI_MAX_RETRIES, soft_time_limit=480, time_limit=540)
def generate_course(self, pk):
    with transaction.atomic():
        job = AIJob.objects.select_for_update().get(pk=pk)
        if job.status != "QUEUED":
            return
        job.status = "PROCESSING"
        job.save(update_fields=["status"])
    started = time.monotonic()
    AIJob.objects.filter(pk=pk, status="PROCESSING").update(
        started_at=timezone.now(),
        progress=10,
        current_step="VALIDATING_SOURCES",
    )
    try:
        documents = job.course.sources.filter(processing_status="COMPLETED")
        chunks = list(
            DocumentChunk.objects.filter(document__in=documents).order_by(
                "document_id", "chunk_index"
            )
        )
        if not chunks or sum(len(c.content) for c in chunks) > settings.AI_MAX_SOURCE_CHARS:
            raise ValueError("Sources missing or context budget exceeded")
        if not AIJob.objects.filter(pk=pk, status="PROCESSING").update(
            progress=30, current_step="GENERATING_DRAFT"
        ):
            return
        sources = [{"id": str(c.pk), "page": c.page_number, "text": c.content} for c in chunks]
        if job.type == "REGENERATE_TOPIC":
            draft = CourseDraft.model_validate(job.parameters["draft_data"])
            wi, ti = job.parameters["week_index"], job.parameters["topic_index"]
            topic, usage = OpenAIProvider().regenerate_topic(
                sources, draft.weeks[wi].topics[ti].model_dump(), job.parameters["instruction"]
            )
            draft.weeks[wi].topics[ti] = topic
        else:
            draft, usage = OpenAIProvider().generate_course(sources, job.parameters)
        validate_citations(draft, {str(c.pk) for c in chunks})
        if len(draft.weeks) != job.parameters["weeks"]:
            raise ValueError("Generated week count differs from request")
        if not job.parameters["assignments"] and any(
            t.assignments for w in draft.weeks for t in w.topics
        ):
            raise ValueError("Unexpected assignments")
        if not job.parameters["tests"] and any(t.questions for w in draft.weeks for t in w.topics):
            raise ValueError("Unexpected tests")
        cost = None
        if settings.AI_INPUT_PRICE and settings.AI_OUTPUT_PRICE:
            cost = (
                Decimal(usage.input_tokens) * Decimal(settings.AI_INPUT_PRICE)
                + Decimal(usage.output_tokens) * Decimal(settings.AI_OUTPUT_PRICE)
            ) / 1000000
        with transaction.atomic():
            job = AIJob.objects.select_for_update().get(pk=pk)
            AIUsageLog.objects.create(
                user=job.user,
                operation=job.type,
                model=settings.OPENAI_MODEL,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                estimated_cost=cost,
                duration=time.monotonic() - started,
                status="COMPLETED",
            )
            if job.status == "CANCELLED":
                return
            AICourseDraft.objects.update_or_create(job=job, defaults={"data": draft.model_dump()})
            job.status, job.progress, job.current_step, job.finished_at = (
                "COMPLETED",
                100,
                "DRAFT_READY",
                timezone.now(),
            )
            job.save()
    except (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError) as exc:
        if self.request.retries < self.max_retries:
            AIJob.objects.filter(pk=pk).exclude(status="CANCELLED").update(
                status="QUEUED", current_step="RETRYING"
            )
            raise self.retry(exc=exc, countdown=15 * (2**self.request.retries))
        fail(job, type(exc).__name__, started)
    except Exception as exc:
        fail(job, type(exc).__name__, started)


def fail(job, error_type, started):
    AIJob.objects.filter(pk=job.pk).exclude(status="CANCELLED").update(
        status="FAILED",
        error=f"Generation failed ({error_type}). Check provider configuration, sources and schema.",
        finished_at=timezone.now(),
    )
    AIUsageLog.objects.create(
        user=job.user,
        operation=job.type,
        model=settings.OPENAI_MODEL,
        status="FAILED",
        duration=time.monotonic() - started,
    )
