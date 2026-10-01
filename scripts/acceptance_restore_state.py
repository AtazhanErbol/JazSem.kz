"""Synthetic restore fixtures and verification; no external sends/provider calls."""

import hashlib
import json
import sys
from datetime import timedelta
from pathlib import Path

import django

django.setup()
from apps.accounts.models import User
from apps.ai.models import AICourseDraft, SourceDocument
from apps.ai.services import import_draft
from apps.assignments.services import review, submit
from apps.courses.services import duplicate, publish
from apps.enrollments.models import Enrollment
from apps.enrollments.services import enroll
from apps.grading.services import grades
from apps.materials.models import Material
from apps.notifications.models import MailOutbox
from apps.notifications.services import mail_cipher, queue_mail
from apps.progress.models import StudentProgress
from apps.progress.services import summary
from apps.testing.services import finalize, save_answer, start
from django.apps import apps
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

database = settings.DATABASES["default"]["NAME"]
assert database in {"jazsem_rc_runtime", "jazsem_rc_restore"}
assert not settings.AI_ENABLED and not settings.OPENAI_API_KEY
folder = Path("/control/restore")
folder.mkdir(parents=True, exist_ok=True)
manifest = folder / "manifest.json"


def fingerprint():
    result = {}
    for model in apps.get_models(include_auto_created=True):
        # Session timestamps are exercised by the post-restore login below.
        rows = list(model.objects.order_by("pk").values())
        serialized = json.dumps(
            rows, default=str, sort_keys=True, separators=(",", ":")
        ).encode()
        result[model._meta.label] = {
            "count": len(rows),
            "sha256": hashlib.sha256(serialized).hexdigest(),
        }
    return result


def seed():
    assert database == "jazsem_rc_runtime" and not manifest.exists()
    teacher = User.objects.get(email="runtime-teacher@example.test")
    student = User.objects.get(email="runtime-student@example.test")
    student.owner_teacher = teacher
    student.created_by = User.objects.get(email="runtime-admin@example.test")
    student.save()
    draft = AICourseDraft.objects.filter(job__status="COMPLETED").first()
    assert draft is not None
    version = import_draft(draft, teacher)
    topic = version.weeks.first().topics.first()
    material = Material.objects.create(
        topic=topic,
        title="Restore attachment",
        type="FILE",
        file=SimpleUploadedFile(
            "restore.txt",
            b"Synthetic restored private material",
            content_type="text/plain",
        ),
        original_filename="restore.txt",
        mime_type="text/plain",
        size=35,
    )
    publish(version, teacher)
    course = version.course
    course.refresh_from_db()
    enrollment = enroll(teacher, student, course)
    for item in topic.materials.all():
        StudentProgress.objects.create(enrollment=enrollment, material=item)
    submission = submit(
        topic.assignments.first(), student, "Synthetic restore answer", []
    )
    review(submission, teacher, "grade", score=80)
    attempt = start(topic.tests.first(), student)
    for question in attempt.test.questions.all():
        save_answer(
            attempt,
            student,
            question.pk,
            [
                str(pk)
                for pk in question.options.filter(is_correct=True).values_list(
                    "pk", flat=True
                )
            ],
        )
    finalize(attempt, student)
    duplicate(version, teacher)
    enrollment.refresh_from_db()
    assert enrollment.course_version_id == version.pk
    expected = {
        "grades": grades(enrollment),
        "progress": summary(enrollment),
        "student": str(student.pk),
        "teacher": str(teacher.pk),
        "created_by": str(student.created_by_id),
        "enrollment": str(enrollment.pk),
        "version": str(version.pk),
        "material": str(material.pk),
        "source": str(draft.job.source_snapshot[0]["document"]),
        "citations": topic.source_chunks,
    }
    # Workers are stopped by the orchestrator before this fixture is created.
    queue_mail(student, "Restore retained mail", "Synthetic encrypted restore payload")
    mail = MailOutbox.objects.filter(recipient=student.email).latest("created_at")
    mail.next_retry_at = timezone.now() + timedelta(days=1)
    mail.save()
    expected["mail"] = str(mail.pk)
    expected["fingerprint"] = fingerprint()
    client = default_storage.connection.meta.client
    objects = []
    for page in client.get_paginator("list_objects_v2").paginate(
        Bucket=default_storage.bucket_name
    ):
        for obj in page.get("Contents", []):
            content = client.get_object(
                Bucket=default_storage.bucket_name, Key=obj["Key"]
            )["Body"].read()
            digest = hashlib.sha256(content).hexdigest()
            (folder / digest).write_bytes(content)
            objects.append({"key": obj["Key"], "sha256": digest, "bytes": len(content)})
    expected["objects"] = objects
    manifest.write_text(json.dumps(expected, default=str))
    print(
        json.dumps(
            {
                "fixture_ready": True,
                "objects": len(objects),
                "models": len(expected["fingerprint"]),
            }
        )
    )


def restore_objects():
    assert (
        database == "jazsem_rc_restore"
        and default_storage.bucket_name == "jazsem-acceptance-restored"
    )
    expected = json.loads(manifest.read_text())
    client = default_storage.connection.meta.client
    assert not any(
        b["Name"] == default_storage.bucket_name
        for b in client.list_buckets()["Buckets"]
    )
    client.create_bucket(Bucket=default_storage.bucket_name)
    for obj in expected["objects"]:
        content = (folder / obj["sha256"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == obj["sha256"]
        client.put_object(
            Bucket=default_storage.bucket_name, Key=obj["key"], Body=content
        )
    print(json.dumps({"restored_objects": len(expected["objects"])}))


def verify():
    assert (
        database == "jazsem_rc_restore"
        and default_storage.bucket_name == "jazsem-acceptance-restored"
    )
    expected = json.loads(manifest.read_text())
    assert fingerprint() == expected["fingerprint"]
    enrollment = Enrollment.objects.get(pk=expected["enrollment"])
    assert str(enrollment.course_version_id) == expected["version"]
    assert str(enrollment.student.owner_teacher_id) == expected["teacher"]
    assert str(enrollment.student.created_by_id) == expected["created_by"]
    assert (
        grades(enrollment) == expected["grades"]
        and summary(enrollment) == expected["progress"]
    )
    source = SourceDocument.objects.get(pk=expected["source"])
    assert set(expected["citations"]) <= {
        str(pk) for pk in source.chunks.values_list("pk", flat=True)
    }
    restored_mail = MailOutbox.objects.get(pk=expected["mail"])
    assert (
        json.loads(mail_cipher().decrypt(restored_mail.encrypted_payload.encode()))[
            "text"
        ]
        == "Synthetic encrypted restore payload"
    )
    client = default_storage.connection.meta.client
    for obj in expected["objects"]:
        content = client.get_object(Bucket=default_storage.bucket_name, Key=obj["key"])[
            "Body"
        ].read()
        assert hashlib.sha256(content).hexdigest() == obj["sha256"]
    # Exercise real session authentication and scoped Django download endpoint
    # against restored DB/storage (in-process HTTP client, not a network smoke).
    http = APIClient()
    assert http.login(
        username=enrollment.student.username, password="Synthetic-runtime-login-7482!"
    )
    response = http.get(
        f"/api/v1/materials/{expected['material']}/download/",
        secure=True,
        HTTP_HOST="rc.example.test",
    )
    assert response.status_code == 200
    assert (
        b"".join(response.streaming_content) == b"Synthetic restored private material"
    )
    response.close()
    http.logout()
    assert (
        http.get(
            f"/api/v1/materials/{expected['material']}/download/",
            secure=True,
            HTTP_HOST="rc.example.test",
        ).status_code
        == 403
    )
    print(
        json.dumps(
            {
                "restore_verified": True,
                "model_fingerprints": len(expected["fingerprint"]),
                "objects": len(expected["objects"]),
                "ownership_versions_history_grades_progress_citations": True,
                "mail_decryption": True,
                "authenticated_scoped_download": "Django session HTTP client",
                "outgoing_mail_and_ai": False,
            }
        )
    )


{"seed": seed, "objects": restore_objects, "verify": verify}[sys.argv[1]]()
