import json
from datetime import timedelta
from pathlib import Path, PurePosixPath

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.ai.models import SourceDocument
from apps.assignments.models import SubmissionFile
from apps.materials.models import Material


def referenced(key):
    return any(
        model.objects.filter(file=key).exists()
        for model in [Material, SubmissionFile, SourceDocument]
    )


def keys(prefix):
    folders, files = default_storage.listdir(prefix)
    for filename in files:
        yield f"{prefix}/{filename}"
    for folder in folders:
        yield from keys(f"{prefix}/{folder}")


class Command(BaseCommand):
    help = "Plan orphan private-upload cleanup. --apply rechecks a reviewed JSON manifest and deletes only still-unreferenced old keys."

    def add_arguments(self, parser):
        parser.add_argument("--manifest", required=True)
        parser.add_argument("--grace-hours", type=int, default=72)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if options["grace_hours"] < 24:
            raise CommandError("Grace period must be at least 24 hours.")
        manifest = Path(options["manifest"])
        cutoff = timezone.now() - timedelta(hours=options["grace_hours"])
        if not options["apply"]:
            candidates = []
            try:
                for key in keys("private"):
                    if default_storage.get_modified_time(key) < cutoff and not referenced(key):
                        candidates.append(key)
            except FileNotFoundError:
                pass
            manifest.write_text(
                json.dumps(
                    {"created_at": timezone.now().isoformat(), "keys": candidates}, indent=2
                ),
                encoding="utf-8",
            )
            self.stdout.write(
                f"Dry run: {len(candidates)} orphan candidates. Review {manifest.name} before --apply."
            )
            return
        data = json.loads(manifest.read_text(encoding="utf-8"))
        candidates = data.get("keys")
        if not isinstance(candidates, list) or any(
            not isinstance(key, str)
            or not key.startswith("private/")
            or ".." in PurePosixPath(key).parts
            or "\\" in key
            for key in candidates
        ):
            raise CommandError("Manifest contains invalid object keys.")
        deleted = preserved = 0
        for key in set(candidates):
            # Recheck immediately before delete, including shared version keys.
            if (
                referenced(key)
                or not default_storage.exists(key)
                or default_storage.get_modified_time(key) >= cutoff
            ):
                preserved += 1
                continue
            default_storage.delete(key)
            deleted += 1
        self.stdout.write(
            f"Deleted: {deleted}; preserved/missing: {preserved}. Object versions follow storage retention policy."
        )
