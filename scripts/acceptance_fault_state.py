"""Phases for real-process fault injection in the disposable production lab.

Run only through acceptance_faults.py. State contains synthetic IDs/counts only.
Lease expiration is injected explicitly after SIGKILL; this does not claim a
ten-minute wall-clock observation of the configured lease duration.
"""

import io
import json
import sys
import time
from datetime import timedelta
from pathlib import Path

import django

django.setup()
import requests
from apps.academics.models import Discipline
from apps.accounts.models import User
from apps.ai import delivery
from apps.ai.models import (
    AIBudgetDay,
    AICourseDraft,
    AIJob,
    AIUsageLog,
    SourceDocument,
    TaskDelivery,
)
from apps.ai.tasks import generate_course
from apps.courses.models import Course
from apps.notifications.models import MailOutbox
from apps.notifications.services import queue_mail
from apps.notifications.tasks import flush_mail
from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from tests.acceptance_provider import control_path

assert settings.ACCEPTANCE_SYNTHETIC
assert settings.DATABASES["default"]["NAME"] == "jazsem_rc_runtime"
assert settings.OPENAI_API_KEY == "synthetic-acceptance-not-a-provider-key"
folder = Path("/control")
state_path = folder / "fault-state.json"
state = json.loads(state_path.read_text()) if state_path.exists() else {}
base = "https://rc.example.test:8443"


def wait(check, seconds=90):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if check():
            return
        time.sleep(0.5)
    raise AssertionError("Synthetic fault condition did not converge")


def client():
    session = requests.Session()
    session.trust_env = False
    session.verify = "/certs/ca.pem"
    csrf = session.get(base + "/api/v1/auth/login/", timeout=15).json()["csrfToken"]
    session.headers.update({"X-CSRFToken": csrf, "Origin": base})
    response = session.post(
        base + "/api/v1/auth/login/",
        json={
            "email": "runtime-teacher@example.test",
            "password": "Synthetic-runtime-login-7482!",
        },
        timeout=15,
    )
    assert response.status_code == 200
    csrf = session.get(base + "/api/v1/auth/login/", timeout=15).json()["csrfToken"]
    session.headers["X-CSRFToken"] = csrf
    return session


def budget():
    return str(AIBudgetDay.objects.aggregate(total=Sum("reserved_usd"))["total"] or 0)


def start(kind):
    session = client()
    user = User.objects.get(email="runtime-teacher@example.test")
    discipline, _ = Discipline.objects.get_or_create(
        code="FAULT-LAB", defaults={"name": "Synthetic faults", "created_by": user}
    )
    discipline.teachers.add(user)
    course = Course.objects.create(
        title="Synthetic fault " + kind, discipline=discipline, teacher=user
    )
    response = session.post(
        base + "/api/v1/sources/",
        data={"course": str(course.pk)},
        files={"file": ("fault-source.txt", b"One plus one equals two.", "text/plain")},
        timeout=15,
    )
    assert response.status_code == 201, response.status_code
    source = response.json()["id"]
    wait(
        lambda: SourceDocument.objects.filter(
            pk=source, processing_status="COMPLETED"
        ).exists()
    )
    control = (
        {"gate": "before_provider" if kind == "before" else "provider"}
        if kind in {"before", "after", "cancel"}
        else {"failure": "timeout"}
        if kind == "timeout"
        else {}
    )
    control_path(course.pk).write_text(json.dumps(control))
    state[kind] = {
        "course": str(course.pk),
        "source": source,
        "budget_before": budget(),
    }
    if kind == "broker":
        return {"source_ready": True}
    response = session.post(
        base + "/api/v1/ai-jobs/",
        json={
            "course": str(course.pk),
            "sources": [source],
            "weeks": 1,
            "language": "ru",
            "complexity": "basic",
            "assignments": True,
            "tests": True,
        },
        timeout=15,
    )
    assert response.status_code == 202, response.status_code
    state[kind]["job"] = response.json()["id"]
    if kind in {"before", "after", "cancel"}:
        stage = control["gate"]
        wait(
            lambda: any(
                json.loads(p.read_text()).get("course") == str(course.pk)
                and json.loads(p.read_text()).get("stage") == stage
                for p in (folder / "events").glob("*.json")
            )
        )
        state[kind]["budget_at_gate"] = budget()
    return {"accepted": 202, "stage": kind}


def finish(kind):
    row = state[kind]
    job = AIJob.objects.get(pk=row["job"])
    if kind in {"before", "after"}:
        lease = TaskDelivery.objects.get(job=job)
        assert lease.status == "RUNNING"
        assert bool(job.provider_started_at) == (kind == "after")
        TaskDelivery.objects.filter(pk=lease.pk).update(
            lease_until=timezone.now() - timedelta(seconds=1)
        )
        control_path(job.course_id).write_text("{}")
        # The real short worker/beat performs reconciliation and dispatch.
    if kind == "cancel":
        response = client().post(
            base + f"/api/v1/ai-jobs/{job.pk}/cancel/", json={}, timeout=15
        )
        assert response.status_code == 200 and response.json()["status"] == "CANCELLED"
        control_path(job.course_id).write_text("{}")
        wait(lambda: AIUsageLog.objects.filter(job=job, status="COMPLETED").exists())
    expected = (
        "FAILED"
        if kind in {"after", "timeout"}
        else "CANCELLED"
        if kind == "cancel"
        else "COMPLETED"
    )
    wait(lambda: AIJob.objects.filter(pk=job.pk, status=expected).exists())
    job.refresh_from_db()
    lease = TaskDelivery.objects.get(job=job)
    if kind in {"after", "timeout"}:
        assert job.error == "PROVIDER_OUTCOME_UNCERTAIN"
        assert AIUsageLog.objects.filter(job=job, status="UNCERTAIN").count() == 1
        assert not AICourseDraft.objects.filter(job=job).exists()
        assert float(budget()) > float(row["budget_before"])
        if kind == "after":
            assert budget() == row["budget_at_gate"]
        executions = lease.executions
        delivery.dispatch()
        assert TaskDelivery.objects.get(pk=lease.pk).executions == executions
    elif kind == "cancel":
        assert not AICourseDraft.objects.filter(job=job).exists()
        assert lease.status == "CANCELLED"
    else:
        assert AICourseDraft.objects.filter(job=job).count() == 1
        assert AIUsageLog.objects.filter(job=job, status="COMPLETED").count() == 1
        generate_course.apply_async(args=[str(job.pk)], task_id=str(lease.pk))
        time.sleep(2)
        assert AICourseDraft.objects.filter(job=job).count() == 1
        assert TaskDelivery.objects.get(pk=lease.pk).executions == lease.executions
    return {
        "scenario": kind,
        "status": expected,
        "executions": lease.executions,
        "drafts": AICourseDraft.objects.filter(job=job).count(),
        "usage_rows": AIUsageLog.objects.filter(job=job).count(),
        "lease_expiration_injected": kind in {"before", "after"},
    }


def broker_down():
    # HTTP admission fails closed if Redis throttling cannot run. An already
    # accepted job remains durable when its subsequent broker dispatch fails.
    session = requests.Session()
    session.trust_env = False
    session.verify = "/certs/ca.pem"
    response = session.get(base + "/api/v1/auth/login/", timeout=15)
    assert (
        response.status_code == 503 and response.json()["code"] == "service_unavailable"
    )
    delivery.dispatch()
    row = TaskDelivery.objects.get(job_id=state["broker"]["job"])
    assert row.status == "PENDING" and row.error_code == "BROKER_UNAVAILABLE"
    assert AIJob.objects.get(pk=row.job_id).status == "QUEUED"
    return {
        "cache_outage_http": 503,
        "accepted_job_retained": True,
        "delivery": row.status,
    }


def enqueue_broker():
    row = state["broker"]
    response = client().post(
        base + "/api/v1/ai-jobs/",
        json={
            "course": row["course"],
            "sources": [row["source"]],
            "weeks": 1,
            "language": "ru",
            "assignments": True,
            "tests": True,
        },
        timeout=15,
    )
    assert response.status_code == 202
    row["job"] = response.json()["id"]
    assert TaskDelivery.objects.get(job_id=row["job"]).status == "PENDING"
    return {"accepted_before_broker_loss": 202}


def smtp():
    user = User.objects.get(email="runtime-student@example.test")
    control = "http://mail:8025/mode/"
    report = []
    try:
        for mode in ["temporary", "permanent", "available"]:
            assert requests.post(control + mode, timeout=5).status_code == 200
            queue_mail(user, "Synthetic fault", "Synthetic content")
            row = MailOutbox.objects.filter(recipient=user.email).latest("created_at")
            if mode == "available":
                MailOutbox.objects.filter(pk=row.pk).update(
                    encrypted_payload="invalid-synthetic-ciphertext"
                )
            flush_mail.delay()
            expected = "RETRY" if mode == "temporary" else "FAILED"
            wait(
                lambda pk=row.pk, status=expected: MailOutbox.objects.filter(
                    pk=pk, status=status
                ).exists()
            )
            row.refresh_from_db()
            assert row.cycle_attempts == 1
            if mode == "temporary":
                assert row.next_retry_at > timezone.now()
                requests.post(control + "available", timeout=5)
                wait(
                    lambda pk=row.pk: MailOutbox.objects.filter(
                        pk=pk, status="SENT"
                    ).exists(),
                    seconds=100,
                )
                row.refresh_from_db()
                assert row.cycle_attempts == 2 and not row.encrypted_payload
            else:
                assert row.error_code == (
                    "SMTP_PERMANENT_FAILURE"
                    if mode == "permanent"
                    else "ENCRYPTION_KEY_UNAVAILABLE"
                )
                assert row.encrypted_payload and row.next_retry_at is None
            report.append(
                {
                    "fault": mode if mode != "available" else "decryption",
                    "status": row.status,
                    "attempts": row.cycle_attempts,
                    "error_code": row.error_code,
                }
            )
    finally:
        requests.post(control + "available", timeout=5)
    return {"smtp": report, "transport": "real STARTTLS local sink"}


def heavy_isolation():
    from apps.testing.models import Test as Quiz
    from apps.testing.models import TestAttempt
    from apps.testing.services import start as start_attempt
    from apps.testing.tasks import expire_attempts
    from PIL import Image, ImageDraw

    session = client()
    course = Course.objects.get(pk=state["broker"]["course"])
    student = User.objects.get(email="runtime-student@example.test")
    test = Quiz.objects.filter(
        topic__week__course_version__enrollments__student=student
    ).first()
    if test is None:
        # This phase is run after restore fixture creation.
        raise AssertionError("Synthetic learning history fixture required")
    attempt = start_attempt(test, student)
    TestAttempt.objects.filter(pk=attempt.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    image = Image.new("RGB", (2400, 6000), "white")
    draw = ImageDraw.Draw(image)
    for y in range(0, 5900, 20):
        draw.text(
            (10, y),
            "Synthetic university lesson. One plus one equals two. " * 7,
            fill="black",
        )
    content = io.BytesIO()
    image.save(content, format="PNG")
    image.close()
    response = session.post(
        base + "/api/v1/sources/",
        data={"course": str(course.pk)},
        files={"file": ("synthetic-ocr.png", content.getvalue(), "image/png")},
        timeout=20,
    )
    assert response.status_code == 201
    source = response.json()["id"]
    wait(
        lambda: SourceDocument.objects.filter(
            pk=source, processing_status="PROCESSING"
        ).exists()
    )
    began = time.monotonic()
    queue_mail(student, "Heavy isolation", "Synthetic short queue notification")
    mail = MailOutbox.objects.filter(recipient=student.email).latest("created_at")
    flush_mail.delay()
    expire_attempts.delay()
    wait(
        lambda: (
            MailOutbox.objects.filter(pk=mail.pk, status="SENT").exists()
            and TestAttempt.objects.filter(pk=attempt.pk, status="EXPIRED").exists()
        ),
        seconds=20,
    )
    assert SourceDocument.objects.filter(
        pk=source, processing_status="PROCESSING"
    ).exists()
    latency = time.monotonic() - began
    wait(
        lambda: SourceDocument.objects.filter(
            pk=source, processing_status__in=["COMPLETED", "FAILED"]
        ).exists(),
        seconds=75,
    )
    document = SourceDocument.objects.get(pk=source)
    return {
        "actual_ocr_pixels": 14400000,
        "short_mail_and_expiry_while_heavy_processing": True,
        "short_seconds": round(latency, 2),
        "heavy_terminal": document.processing_status,
        "heavy_bounded_seconds": round(time.monotonic() - began, 2),
    }


def extraction(stage):
    if stage == "prepare-extraction":
        course = Course.objects.get(pk=state["broker"]["course"])
        session = client()
        # A just-reconnected control channel can report temporary unavailability.
        # Retry only the explicit pre-admission worker failure: no business row
        # exists yet. Do not retry ambiguous HTTP failures or a paid operation.
        for retry in range(4):
            response = session.post(
                base + "/api/v1/sources/",
                data={"course": str(course.pk)},
                files={
                    "file": (
                        "storage-outage.txt",
                        b"Synthetic source survives storage outage.",
                        "text/plain",
                    )
                },
                timeout=15,
            )
            if (
                response.status_code != 503
                or response.json().get("code") != "background_unavailable"
            ):
                break
            time.sleep(1)
        assert response.status_code == 201
        state["extraction"] = {
            "source": response.json()["id"],
            "course": str(course.pk),
        }
        assert (
            SourceDocument.objects.get(
                pk=state["extraction"]["source"]
            ).processing_status
            == "QUEUED"
        )
        return {
            "accepted_source_before_storage_loss": 201,
            "transient_admission_retries": retry,
        }
    row = state["extraction"]
    if stage == "failed-extraction":
        wait(
            lambda: SourceDocument.objects.filter(
                pk=row["source"], processing_status="FAILED"
            ).exists()
        )
        document = SourceDocument.objects.get(pk=row["source"])
        assert document.error == "EXTRACTION_FAILED" and not document.chunks.exists()
        return {"storage_outage_extraction": "FAILED", "partial_chunks": 0}
    session = client()
    response = session.post(
        base + f"/api/v1/sources/{row['source']}/retry/", json={}, timeout=15
    )
    assert response.status_code == 200
    wait(
        lambda: SourceDocument.objects.filter(
            pk=row["source"], processing_status="COMPLETED"
        ).exists()
    )
    document = SourceDocument.objects.get(pk=row["source"])
    chunks = list(document.chunks.values_list("pk", flat=True))
    response = session.post(
        base + f"/api/v1/sources/{row['source']}/retry/", json={}, timeout=15
    )
    assert response.status_code == 400
    assert (
        session.post(
            base + f"/api/v1/sources/{row['source']}/exclude/", json={}, timeout=15
        ).status_code
        == 200
    )
    assert list(document.chunks.values_list("pk", flat=True)) == chunks
    assert (
        session.get(
            base + f"/api/v1/sources/{row['source']}/download/", timeout=15
        ).status_code
        == 200
    )
    corrupt = session.post(
        base + "/api/v1/sources/",
        data={"course": row["course"]},
        files={"file": ("corrupt.pdf", b"%PDF-1.7\n", "application/pdf")},
        timeout=15,
    )
    assert corrupt.status_code == 201
    wait(
        lambda: SourceDocument.objects.filter(
            pk=corrupt.json()["id"], processing_status="FAILED"
        ).exists()
    )
    oversized = session.post(
        base + "/api/v1/sources/",
        data={"course": row["course"]},
        files={
            "file": (
                "oversized.txt",
                b"x" * (settings.MAX_UPLOAD_BYTES + 1),
                "text/plain",
            )
        },
        timeout=30,
    )
    assert oversized.status_code == 400 and "errors" in oversized.json()
    return {
        "storage_restored_retry": "COMPLETED",
        "completed_chunk_ids_immutable": True,
        "corrupt_pdf": "FAILED",
        "oversized_upload_http": 400,
    }


stage = sys.argv[1]
if stage.startswith("start-"):
    result = start(stage.removeprefix("start-"))
elif stage.startswith("finish-") and stage != "finish-extraction":
    result = finish(stage.removeprefix("finish-"))
elif stage == "broker-down":
    result = broker_down()
elif stage == "enqueue-broker":
    result = enqueue_broker()
elif stage == "smtp":
    result = smtp()
elif stage == "heavy-isolation":
    result = heavy_isolation()
elif stage in {"prepare-extraction", "failed-extraction", "finish-extraction"}:
    result = extraction(stage)
else:
    raise SystemExit("Unknown fault phase")
state_path.write_text(json.dumps(state))
print(json.dumps(result))
