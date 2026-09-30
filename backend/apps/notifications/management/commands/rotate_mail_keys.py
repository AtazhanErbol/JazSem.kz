from cryptography.fernet import InvalidToken
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.notifications.models import MailOutbox
from apps.notifications.services import mail_cipher


class Command(BaseCommand):
    help = "Validate queued mail keys; --apply re-encrypts unsent messages using the primary key."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        cipher = mail_cipher()
        count = failed = 0
        ids = MailOutbox.objects.exclude(encrypted_payload="").values_list("pk", flat=True)
        for pk in ids.iterator(chunk_size=100):
            with transaction.atomic():
                row = MailOutbox.objects.select_for_update().get(pk=pk)
                if not row.encrypted_payload:
                    continue
                try:
                    rotated = cipher.rotate(row.encrypted_payload.encode()).decode()
                except InvalidToken:
                    failed += 1
                    continue
                if options["apply"]:
                    row.encrypted_payload = rotated
                    row.save(update_fields=["encrypted_payload", "updated_at"])
                count += 1
        self.stdout.write(f"Validated: {count}; unreadable: {failed}; applied: {options['apply']}")
        if failed:
            raise CommandError("Keep previous keys: some queued mail cannot be decrypted.")
