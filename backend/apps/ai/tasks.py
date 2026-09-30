import time
from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import delivery
from .extraction import extract_pages
from .models import AICourseDraft, AIJob, AIUsageLog, DocumentChunk, SourceDocument
from .provider import AIProvider, OpenAIProvider
from .schema import CourseDraft, validate_citations


@shared_task
def dispatch_pending():
    delivery.dispatch()


@shared_task(soft_time_limit=480, time_limit=540)
def extract_document(pk):
    document = SourceDocument.objects.get(pk=pk)
    lease = delivery.claim(source=document)
    if lease is None:
        return
    try:
        chunks, chars = [], 0
        with document.file.open("rb") as file:
            data = file.read(settings.MAX_UPLOAD_BYTES + 1)
        if len(data) > settings.MAX_UPLOAD_BYTES:
            raise ValueError("Source byte limit")
        for page, text in extract_pages(data, document.filename):
            chars += len(text)
            if chars > settings.AI_MAX_SOURCE_CHARS * 5:
                raise ValueError("Source character limit")
            if not delivery.heartbeat(lease):
                return
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
        if not chunks:
            raise ValueError("Empty source")
        with transaction.atomic():
            delivery.lock_course(lease)
            locked = delivery.owned(lease)
            if locked is None:
                return
            # Completed sources are immutable. Never replace already cited IDs.
            if document.chunks.exists():
                raise ValueError("Existing immutable chunks")
            DocumentChunk.objects.bulk_create(chunks)
            SourceDocument.objects.filter(pk=pk, processing_status="PROCESSING").update(
                extracted_text="\n".join(c.content for c in chunks),
                processing_status="COMPLETED",
                error="",
            )
            delivery.complete(locked)
    except Exception:
        delivery.failed(lease, "EXTRACTION_FAILED")


def usage_record(job, started, usage=None, status="FAILED"):
    cost = None
    if usage and settings.AI_INPUT_PRICE and settings.AI_OUTPUT_PRICE:
        cost = (
            Decimal(usage.input_tokens) * Decimal(settings.AI_INPUT_PRICE)
            + Decimal(usage.output_tokens) * Decimal(settings.AI_OUTPUT_PRICE)
        ) / 1000000
    AIUsageLog.objects.update_or_create(
        job=job,
        defaults={
            "user": job.user,
            "operation": job.type,
            "model": settings.OPENAI_MODEL,
            "input_tokens": usage.input_tokens if usage else 0,
            "output_tokens": usage.output_tokens if usage else 0,
            "estimated_cost": cost,
            "duration": time.monotonic() - started,
            "status": status,
        },
    )


@shared_task(soft_time_limit=480, time_limit=540)
def generate_course(pk):
    job = AIJob.objects.get(pk=pk)
    lease = delivery.claim(job=job)
    if lease is None:
        return
    started = time.monotonic()
    provider_called = False
    responded = False
    try:
        if not settings.AI_ENABLED:
            delivery.failed(lease, "AI_DISABLED")
            return
        sources = job.source_snapshot
        if not sources or sum(len(c["text"]) for c in sources) > settings.AI_MAX_SOURCE_CHARS:
            raise ValueError("Sources missing or context limit")
        # Persist the possible paid-call boundary before network IO. After this
        # point a timeout/kill is uncertain and must never trigger automatic replay.
        with transaction.atomic():
            delivery.lock_course(lease)
            if delivery.owned(lease) is None:
                return
            if not AIJob.objects.filter(pk=pk, status="PROCESSING").update(
                provider_started_at=timezone.now(),
                progress=30,
                current_step="GENERATING_DRAFT",
            ):
                return
        provider_called = True
        provider: AIProvider = OpenAIProvider()
        if job.type == "REGENERATE_TOPIC":
            draft = CourseDraft.model_validate(job.parameters["draft_data"])
            wi, ti = job.parameters["week_index"], job.parameters["topic_index"]
            topic, usage = provider.regenerate_topic(
                sources, draft.weeks[wi].topics[ti].model_dump(), job.parameters["instruction"]
            )
            draft.weeks[wi].topics[ti] = topic
        else:
            draft, usage = provider.generate_course(sources, job.parameters)
        # Account for a response even if cancellation won while the call ran.
        responded = True
        usage_record(job, started, usage, "COMPLETED")
        validate_citations(draft, {c["id"] for c in sources})
        if len(draft.weeks) != job.parameters["weeks"]:
            raise ValueError("Week count mismatch")
        if not job.parameters["assignments"] and any(
            t.assignments for w in draft.weeks for t in w.topics
        ):
            raise ValueError("Unexpected assignments")
        if not job.parameters["tests"] and any(t.questions for w in draft.weeks for t in w.topics):
            raise ValueError("Unexpected tests")
        with transaction.atomic():
            delivery.lock_course(lease)
            locked = delivery.owned(lease)
            if locked is None:
                return
            job = AIJob.objects.select_for_update().get(pk=pk)
            if job.status != "PROCESSING":
                return
            AICourseDraft.objects.get_or_create(job=job, defaults={"data": draft.model_dump()})
            job.status, job.progress, job.current_step, job.finished_at = (
                "COMPLETED",
                100,
                "DRAFT_READY",
                timezone.now(),
            )
            job.save()
            delivery.complete(locked)
    except Exception:
        code = (
            "OUTPUT_VALIDATION_FAILED"
            if responded
            else "PROVIDER_OUTCOME_UNCERTAIN"
            if provider_called
            else "GENERATION_VALIDATION_FAILED"
        )
        delivery.failed(lease, code)
        if not AIUsageLog.objects.filter(job=job).exists():
            usage_record(job, started, status="UNCERTAIN" if provider_called else "FAILED")
