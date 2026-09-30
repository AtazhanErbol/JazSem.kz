import json
import smtplib
import uuid
from datetime import timedelta

from celery import shared_task
from cryptography.fernet import InvalidToken
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import MailOutbox
from .services import mail_cipher


def recover_mail_leases():
    now = timezone.now()
    stale = MailOutbox.objects.filter(status="SENDING", lease_until__lte=now)
    stale.filter(cycle_attempts__gte=settings.MAIL_MAX_ATTEMPTS).update(
        status="FAILED",
        error_code="DELIVERY_UNCERTAIN",
        lease_token=None,
        lease_until=None,
    )
    stale.update(
        status="RETRY",
        error_code="DELIVERY_UNCERTAIN",
        next_retry_at=now,
        lease_token=None,
        lease_until=None,
    )


@transaction.atomic
def claim_mail(pk):
    mail = MailOutbox.objects.select_for_update().get(pk=pk)
    now = timezone.now()
    if mail.sent_at or mail.status not in ["PENDING", "RETRY"]:
        return None
    if mail.next_retry_at and mail.next_retry_at > now:
        return None
    if mail.cycle_attempts >= settings.MAIL_MAX_ATTEMPTS:
        mail.status = "FAILED"
        mail.save(update_fields=["status", "updated_at"])
        return None
    mail.status = "SENDING"
    mail.attempts += 1
    mail.cycle_attempts += 1
    mail.lease_token = uuid.uuid4()
    mail.lease_until = now + timedelta(seconds=settings.MAIL_LEASE_SECONDS)
    mail.save()
    return mail


def delivery_error(exc):
    if isinstance(exc, InvalidToken):
        return "ENCRYPTION_KEY_UNAVAILABLE"
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return "SMTP_AUTH_FAILED"
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "RECIPIENT_REJECTED"
    if isinstance(exc, (TimeoutError, OSError, smtplib.SMTPException)):
        return "SMTP_UNAVAILABLE"
    return "DELIVERY_FAILED"


@shared_task
def flush_mail():
    recover_mail_leases()
    due = (
        MailOutbox.objects.filter(status__in=["PENDING", "RETRY"])
        .filter(Q(next_retry_at=None) | Q(next_retry_at__lte=timezone.now()))
        .order_by("created_at", "pk")
    )
    for pk in list(due.values_list("pk", flat=True)[:100]):
        mail = claim_mail(pk)
        if mail is None:
            continue
        owned = MailOutbox.objects.filter(pk=pk, status="SENDING", lease_token=mail.lease_token)
        try:
            payload = json.loads(mail_cipher().decrypt(mail.encrypted_payload.encode()))
            message = EmailMultiAlternatives(
                payload["subject"],
                payload["text"],
                settings.DEFAULT_FROM_EMAIL,
                [mail.recipient],
            )
            message.attach_alternative(payload["html"], "text/html")
            # Network IO is outside the claim transaction. SMTP is at-least-once:
            # death after acceptance and before SENT commit may duplicate mail.
            if message.send() != 1:
                raise OSError("Transport did not confirm acceptance")
        except Exception as exc:
            code = delivery_error(exc)
            terminal = mail.cycle_attempts >= settings.MAIL_MAX_ATTEMPTS or code in [
                "ENCRYPTION_KEY_UNAVAILABLE",
                "SMTP_AUTH_FAILED",
                "RECIPIENT_REJECTED",
            ]
            owned.update(
                status="FAILED" if terminal else "RETRY",
                error_code=code,
                next_retry_at=None
                if terminal
                else timezone.now()
                + timedelta(seconds=min(3600, 30 * 2 ** (mail.cycle_attempts - 1))),
                lease_token=None,
                lease_until=None,
                updated_at=timezone.now(),
            )
        else:
            owned.update(
                status="SENT",
                sent_at=timezone.now(),
                encrypted_payload="",
                error_code="",
                next_retry_at=None,
                lease_token=None,
                lease_until=None,
                updated_at=timezone.now(),
            )


@shared_task
def deadline_reminders():
    from apps.assignments.models import Assignment
    from apps.enrollments.models import Enrollment

    from .services import notify

    now = timezone.now()
    for assignment in Assignment.objects.filter(
        status="PUBLISHED", deadline__gt=now, deadline__lte=now + timedelta(days=1)
    ):
        for enrollment in Enrollment.objects.filter(
            course_version=assignment.topic.week.course_version,
            status__in=["ASSIGNED", "IN_PROGRESS"],
        ):
            notify(
                enrollment.student,
                "DEADLINE",
                assignment.title,
                str(assignment.deadline),
                "/app/assignments",
                email=True,
                key=f"deadline:{assignment.pk}:{enrollment.pk}",
            )
