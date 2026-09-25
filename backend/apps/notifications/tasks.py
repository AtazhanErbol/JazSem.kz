import json
from datetime import timedelta

from celery import shared_task
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils import timezone

from .models import MailOutbox


@shared_task
def flush_mail():
    for pk in MailOutbox.objects.filter(sent_at=None, attempts__lt=5).values_list("pk", flat=True)[
        :100
    ]:
        with transaction.atomic():
            mail = MailOutbox.objects.select_for_update().get(pk=pk)
            if mail.sent_at:
                continue
            mail.attempts += 1
            try:
                payload = json.loads(
                    Fernet(settings.MAIL_ENCRYPTION_KEY.encode()).decrypt(
                        mail.encrypted_payload.encode()
                    )
                )
                message = EmailMultiAlternatives(
                    payload["subject"],
                    payload["text"],
                    settings.DEFAULT_FROM_EMAIL,
                    [mail.recipient],
                )
                message.attach_alternative(payload["html"], "text/html")
                message.send()
                mail.sent_at = timezone.now()
                mail.encrypted_payload = ""
            except Exception:
                # Retry on subsequent beat run; do not log mail bodies or SMTP credentials.
                pass
            mail.save()


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
                key=f"deadline:{assignment.pk}:{enrollment.pk}",
            )
