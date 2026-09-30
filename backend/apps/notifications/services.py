import json

from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings
from django.utils.html import escape

from .models import MailOutbox, Notification


def mail_cipher():
    # New messages use the primary key; retained keys decrypt older queued mail.
    keys = [settings.MAIL_ENCRYPTION_KEY, *settings.MAIL_PREVIOUS_ENCRYPTION_KEYS]
    return MultiFernet([Fernet(key.encode()) for key in keys])


def password_changed(user):
    kazakh = user.preferred_language == "kk"
    queue_mail(
        user,
        "JazSem — құпиясөз өзгертілді" if kazakh else "JazSem — пароль изменён",
        (
            "Аккаунтыңыздың құпиясөзі сәтті өзгертілді. Егер мұны сіз жасамасаңыз, "
            "құпиясөзді дереу қалпына келтіріп, әкімшіге хабарласыңыз."
            if kazakh
            else "Пароль вашего аккаунта успешно изменён. Если это сделали не вы, "
            "сразу восстановите пароль и обратитесь к администратору."
        )
        + "\n\n"
        + settings.FRONTEND_URL.rstrip("/")
        + "/forgot-password",
    )


def queue_mail(user, subject, message):
    payload = {
        "subject": subject,
        "text": message,
        "html": f'<html lang="{user.preferred_language}"><body><h1>JazSem.kz</h1><p>{escape(message).replace(chr(10), "<br>")}</p></body></html>',
    }
    encrypted = mail_cipher().encrypt(json.dumps(payload).encode()).decode()
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
        body = message or title
        if link.startswith("/app/"):
            body += "\n\n" + settings.FRONTEND_URL.rstrip("/") + link
        queue_mail(user, title, body)
    return note
