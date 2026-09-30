import json
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from apps.ai.models import AIJob, SourceDocument
from apps.assignments.services import submit
from apps.notifications.models import MailOutbox
from apps.notifications.tasks import flush_mail


def test_invalid_and_expired_reset_links_do_not_change_password(world):
    cache.clear()
    client = APIClient()
    user = world["student"]
    payload = {"uid": "YmFk", "token": "invalid", "password": "Unchanged-secure-876!"}
    assert client.post("/api/v1/auth/reset-password/", payload).status_code == 400
    payload["uid"] = urlsafe_base64_encode(str(user.pk).encode())
    payload["token"] = default_token_generator.make_token(user)
    with patch.object(
        default_token_generator,
        "_now",
        return_value=default_token_generator._now() + timedelta(hours=2),
    ):
        assert client.post("/api/v1/auth/reset-password/", payload).status_code == 400
    user.refresh_from_db()
    assert user.check_password("Example-pass-583!")


@pytest.mark.parametrize("role,language", [("student", "ru"), ("teacher", "kk"), ("admin", "ru")])
def test_password_reset_email_and_change_confirmation(world, settings, role, language):
    cache.clear()
    MailOutbox.objects.all().delete()
    user = world[role]
    user.preferred_language = language
    user.save()
    client = APIClient(enforce_csrf_checks=True)
    csrf = client.get("/api/v1/auth/login/").data["csrfToken"]
    endpoint = "/api/v1/auth/forgot-password/"
    known = client.post(endpoint, {"email": user.email}, HTTP_X_CSRFTOKEN=csrf)
    unknown = client.post(endpoint, {"email": "nobody@example.test"}, HTTP_X_CSRFTOKEN=csrf)
    assert known.status_code == unknown.status_code == 200
    assert known.data == unknown.data
    queued = MailOutbox.objects.get()
    assert "reset-password" not in queued.encrypted_payload
    flush_mail()
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [user.email]
    body = mail.outbox[0].body
    url = next(word for word in body.split() if "/reset-password?" in word)
    params = {key: value[0] for key, value in parse_qs(urlparse(url).query).items()}
    params["password"] = "Changed-only-for-test-492!"
    response = client.post("/api/v1/auth/reset-password/", params, HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 200
    assert (
        client.post("/api/v1/auth/reset-password/", params, HTTP_X_CSRFTOKEN=csrf).status_code
        == 400
    )
    flush_mail()
    assert len(mail.outbox) == 2
    assert ("өзгертілді" if language == "kk" else "изменён") in mail.outbox[1].subject
    assert params["password"] not in mail.outbox[1].body
    user.refresh_from_db()
    assert user.check_password(params["password"])
    assert not MailOutbox.objects.exclude(encrypted_payload="").exists()


def test_submission_notifies_teacher_once_and_smtp_failure_retries(world, settings):
    MailOutbox.objects.all().delete()
    for _ in range(2):
        submit(world["assignment"], world["student"], "x = 1", [])
    queued = MailOutbox.objects.get()
    assert queued.recipient == world["teacher"].email
    payload = json.loads(
        Fernet(settings.MAIL_ENCRYPTION_KEY.encode()).decrypt(queued.encrypted_payload.encode())
    )
    assert settings.FRONTEND_URL + "/app/submissions" in payload["text"]
    with patch(
        "apps.notifications.tasks.EmailMultiAlternatives.send", side_effect=OSError("offline")
    ):
        flush_mail()
    queued.refresh_from_db()
    assert queued.attempts == 1 and queued.sent_at is None and queued.encrypted_payload
    MailOutbox.objects.filter(pk=queued.pk).update(next_retry_at=timezone.now())
    flush_mail()
    queued.refresh_from_db()
    assert queued.sent_at and queued.attempts == 2 and not queued.encrypted_payload


def test_ai_disabled_and_worker_down_fail_without_orphan_records(world, client_for, settings):
    cache.clear()
    teacher = client_for(world["teacher"])
    settings.AI_ENABLED = False
    response = teacher.post("/api/v1/ai-jobs/", {"course": str(world["course"].pk)})
    assert response.status_code == 400
    assert AIJob.objects.count() == 0
    with patch("apps.common.background.worker_available", return_value=False):
        response = teacher.post(
            "/api/v1/sources/",
            {
                "course": str(world["course"].pk),
                "file": SimpleUploadedFile("lesson.txt", b"Lesson text", content_type="text/plain"),
            },
            format="multipart",
        )
    assert response.status_code == 503
    assert SourceDocument.objects.count() == 0
    assert client_for(world["student"]).get("/api/v1/ai-status/").status_code == 403
    settings.OPENAI_API_KEY = "sentinel-never-return-this"
    response = teacher.get("/api/v1/ai-status/")
    assert response.status_code == 200 and not response.data["enabled"]
    assert settings.OPENAI_API_KEY not in str(response.data)
