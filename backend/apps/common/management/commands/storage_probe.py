from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Verify the private readiness sentinel; --initialize creates it once."

    def add_arguments(self, parser):
        parser.add_argument("--initialize", action="store_true")

    def handle(self, **options):
        key = settings.STORAGE_PROBE_KEY
        if not key or not key.startswith("private/health/"):
            raise CommandError("Configure a private/health/ readiness key.")
        if not default_storage.exists(key) and options["initialize"]:
            default_storage.save(key, ContentFile(b"JazSem readiness sentinel\n"))
        if not default_storage.exists(key):
            raise CommandError("Readiness sentinel is unavailable.")
        self.stdout.write("Storage read probe passed.")
