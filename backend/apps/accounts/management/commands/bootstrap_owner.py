"""Initialize an empty deployment without a shared/default administrator password."""

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create the first owner in an empty database; activate via password reset email."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)

    @transaction.atomic
    def handle(self, **options):
        email = options["email"].strip().lower()
        try:
            validate_email(email)
        except ValidationError:
            raise CommandError("A valid owner email is required.") from None
        if User.objects.exists():
            if User.objects.filter(role="ADMIN", is_active=True, is_superuser=True).exists():
                self.stdout.write("Existing administrator retained; no account changed.")
                return
            raise CommandError("Nonempty database: owner creation requires manual administration.")
        User.objects.create_superuser(username="owner", email=email, password=None)
        self.stdout.write(
            "Initial owner created with password login disabled. Use password reset to activate."
        )
