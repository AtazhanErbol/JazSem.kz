import json
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from apps.ai.models import AICourseDraft, AIJob, SourceDocument
from apps.ai.schema import CourseDraft
from apps.ai.tasks import extract_document, generate_course
from apps.notifications.models import MailOutbox


def test_csrf_refresh_does_not_consume_login_quota(world):
    cache.clear()
    client = APIClient()
    for _ in range(12):
        assert client.get("/api/v1/auth/login/").status_code == 200
    for _ in range(10):
        assert (
            client.post(
                "/api/v1/auth/login/", {"email": "student@example.test", "password": "wrong"}
            ).status_code
            == 400
        )
    assert (
        client.post(
            "/api/v1/auth/login/", {"email": "student@example.test", "password": "wrong"}
        ).status_code
        == 429
    )
    cache.clear()


def test_polling_and_reading_do_not_consume_generation_or_upload_quotas(world, client_for):
    cache.clear()
    teacher = client_for(world["teacher"])
    for _ in range(35):
        for path in ["ai-jobs", "sources", "materials"]:
            assert teacher.get(f"/api/v1/{path}/").status_code == 200
    cache.clear()


def test_csrf_login_and_temporary_password_gate(world):
    user = world["student"]
    user.must_change_password = True
    user.save()
    client = APIClient(enforce_csrf_checks=True)
    assert (
        client.post(
            "/api/v1/auth/login/", {"email": user.email, "password": "Example-pass-583!"}
        ).status_code
        == 403
    )
    csrf = client.get("/api/v1/auth/login/").data["csrfToken"]
    response = client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "Example-pass-583!"},
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert response.status_code == 200
    assert client.get("/api/v1/courses/").status_code == 403
    assert client.get("/api/v1/auth/me/").status_code == 200
    csrf = client.cookies["csrftoken"].value
    assert (
        client.post(
            "/api/v1/auth/change-password/",
            {"current_password": "Example-pass-583!", "password": "Changed-secure-971!"},
            HTTP_X_CSRFTOKEN=csrf,
        ).status_code
        == 200
    )
    assert client.get("/api/v1/courses/").status_code == 200


def test_create_account_encrypts_password_and_reset_is_single_use(world, client_for):
    response = client_for(world["teacher"]).post(
        "/api/v1/users/",
        {
            "email": "created@example.test",
            "first_name": "New",
            "last_name": "Student",
            "role": "STUDENT",
        },
        format="json",
    )
    assert response.status_code == 201
    assert "password" not in response.data
    outbox = MailOutbox.objects.get(recipient="created@example.test")
    assert "Временный пароль" not in outbox.encrypted_payload
    payload = json.loads(
        Fernet(settings.MAIL_ENCRYPTION_KEY.encode()).decrypt(outbox.encrypted_payload.encode())
    )
    assert "Временный пароль" in payload["text"]
    user = world["student"]
    token = default_token_generator.make_token(user)
    data = {
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": token,
        "password": "Another-strong-984!",
    }
    client = APIClient()
    assert client.post("/api/v1/auth/reset-password/", data).status_code == 200
    assert client.post("/api/v1/auth/reset-password/", data).status_code == 400


def draft_data(chunk):
    return {
        "title": "Course",
        "description": "Grounded",
        "source_gaps": [],
        "weeks": [
            {
                "title": "Week",
                "topics": [
                    {
                        "title": "Topic",
                        "content": "Supported content",
                        "source_chunks": [str(chunk.pk)],
                        "assignments": [
                            {
                                "title": "Work",
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


def test_ai_private_draft_import_does_not_publish(world, client_for):
    source = SourceDocument.objects.create(
        course=world["course"],
        uploaded_by=world["teacher"],
        filename="notes.txt",
        mime_type="text/plain",
        size=10,
        file=SimpleUploadedFile("notes.txt", b"Valid text source"),
    )
    extract_document(str(source.pk))
    source.refresh_from_db()
    assert source.processing_status == "COMPLETED"
    chunk = source.chunks.first()
    job = AIJob.objects.create(
        user=world["teacher"],
        course=world["course"],
        parameters={"weeks": 1, "assignments": True, "tests": False},
    )
    with patch(
        "apps.ai.tasks.OpenAIProvider.generate_course",
        return_value=(
            CourseDraft.model_validate(draft_data(chunk)),
            SimpleNamespace(input_tokens=100, output_tokens=200),
        ),
    ):
        generate_course(str(job.pk))
    job.refresh_from_db()
    assert job.status == "COMPLETED"
    draft = AICourseDraft.objects.get(job=job)
    assert client_for(world["student"]).get(f"/api/v1/ai-drafts/{draft.pk}/").status_code == 404
    teacher = client_for(world["teacher"])
    response = teacher.post(f"/api/v1/ai-drafts/{draft.pk}/confirm/")
    assert response.status_code == 200
    assert response.data["status"] == "DRAFT"
    assert teacher.post(f"/api/v1/ai-drafts/{draft.pk}/confirm/").data["id"] == response.data["id"]
    world["course"].refresh_from_db()
    assert world["course"].current_version_id == world["version"].pk


def test_ai_rejects_invented_citations(world, client_for):
    job = AIJob.objects.create(user=world["teacher"], course=world["course"])
    draft = AICourseDraft.objects.create(job=job, data={})
    data = draft_data(SimpleNamespace(pk="unknown"))
    response = client_for(world["teacher"]).patch(
        f"/api/v1/ai-drafts/{draft.pk}/", {"data": data}, format="json"
    )
    assert response.status_code == 400


def test_upload_rejects_spoofed_type(world, client_for):
    response = client_for(world["teacher"]).post(
        "/api/v1/sources/",
        {
            "course": str(world["course"].pk),
            "file": SimpleUploadedFile(
                "bad.pdf", b"<script>bad</script>", content_type="application/pdf"
            ),
        },
    )
    assert response.status_code == 400
