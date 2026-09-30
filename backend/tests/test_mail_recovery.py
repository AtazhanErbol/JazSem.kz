from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from django.core import mail
from django.core.management import call_command
from django.db import connection
from django.utils import timezone

from apps.notifications.models import MailOutbox
from apps.notifications.services import queue_mail
from apps.notifications.tasks import claim_mail, flush_mail


@pytest.mark.django_db(transaction=True)
def test_smtp_runs_without_database_transaction(world):
    MailOutbox.objects.all().delete()
    queue_mail(world["student"], "Synthetic subject", "Synthetic body")
    with patch("apps.notifications.tasks.EmailMultiAlternatives.send") as send:

        def transport():
            assert not connection.in_atomic_block, "SMTP must not hold database locks"
            return 1

        send.side_effect = transport
        flush_mail()
    assert MailOutbox.objects.get().sent_at is not None


def test_smtp_failure_is_visible_and_retry_is_scheduled(world):
    MailOutbox.objects.all().delete()
    queue_mail(world["student"], "Synthetic subject", "Synthetic body")
    with patch(
        "apps.notifications.tasks.EmailMultiAlternatives.send", side_effect=OSError("SECRET")
    ):
        flush_mail()
    queued = MailOutbox.objects.get()
    assert getattr(queued, "status", None) == "RETRY"
    assert queued.next_retry_at > timezone.now()
    assert "SECRET" not in queued.error_code
    with patch("apps.notifications.tasks.EmailMultiAlternatives.send") as send:
        flush_mail()
        send.assert_not_called()


def test_admin_can_see_failed_delivery_and_retry_without_exposing_body(world, client_for):
    MailOutbox.objects.all().delete()
    queue_mail(world["student"], "Sensitive subject", "Sensitive body")
    queued = MailOutbox.objects.get()
    queued.attempts = 5
    queued.save()
    admin = client_for(world["admin"])
    response = admin.get("/api/v1/mail-outbox/")
    assert response.status_code == 200
    assert "encrypted_payload" not in str(response.data)
    assert "Sensitive" not in str(response.data)
    assert admin.post(f"/api/v1/mail-outbox/{queued.pk}/retry/").status_code == 200
    flush_mail()
    queued.refresh_from_db()
    assert queued.sent_at is not None
    assert client_for(world["teacher"]).get("/api/v1/mail-outbox/").status_code == 403


def test_lease_recovers_crashed_sender_and_completed_mail_is_not_sent_twice(world):
    MailOutbox.objects.all().delete()
    queue_mail(world["student"], "Subject", "Body")
    queued = MailOutbox.objects.get()
    claim_mail(queued.pk)
    flush_mail()
    assert not hasattr(mail, "outbox") or not mail.outbox
    MailOutbox.objects.filter(pk=queued.pk).update(
        lease_until=timezone.now() - timedelta(seconds=1)
    )
    flush_mail()
    flush_mail()
    assert len(mail.outbox) == 1
    queued.refresh_from_db()
    assert queued.status == "SENT" and queued.attempts == 2 and not queued.encrypted_payload


def test_rotation_keeps_queued_mail_readable_and_reports_missing_key(world, settings):
    MailOutbox.objects.all().delete()
    old = settings.MAIL_ENCRYPTION_KEY
    queue_mail(world["student"], "Subject", "Private body")
    settings.MAIL_ENCRYPTION_KEY = Fernet.generate_key().decode()
    flush_mail()
    queued = MailOutbox.objects.get()
    assert queued.error_code == "ENCRYPTION_KEY_UNAVAILABLE" and queued.status == "FAILED"
    settings.MAIL_PREVIOUS_ENCRYPTION_KEYS = [old]
    output = StringIO()
    call_command("rotate_mail_keys", apply=True, stdout=output)
    settings.MAIL_PREVIOUS_ENCRYPTION_KEYS = []
    queued.refresh_from_db()
    assert b"Private body" in Fernet(settings.MAIL_ENCRYPTION_KEY.encode()).decrypt(
        queued.encrypted_payload.encode()
    )
    assert "Private body" not in output.getvalue()
