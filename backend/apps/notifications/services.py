import json

from cryptography.fernet import Fernet
from django.conf import settings
from django.utils.html import escape

from .models import MailOutbox, Notification


def queue_mail(user, subject, message):
    payload = {
        "subject": subject,
        "text": message,
        "html": f'<html lang="{user.preferred_language}"><body><h1>JazSem.kz</h1><p>{escape(message).replace(chr(10), "<br>")}</p></body></html>',
    }
    encrypted = (
        Fernet(settings.MAIL_ENCRYPTION_KEY.encode()).encrypt(json.dumps(payload).encode()).decode()
    )
    MailOutbox.objects.create(recipient=user.email, encrypted_payload=encrypted)


def notify(user, kind, title, message="", link="", email=False, key=None):
    note, created = (
        Notification.objects.get_or_create(
            dedupe_key=key,
            defaults={
                "recipient": user,
                "type": kind,
                "title": title,
                "message": message,
                "link": link,
            },
        )
        if key
        else (
            Notification.objects.create(
                recipient=user, type=kind, title=title, message=message, link=link
            ),
            True,
        )
    )
    if email and created:
        queue_mail(user, title, message)
    return note
