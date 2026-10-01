"""Real S3 cleanup on disposable fixtures, with an explicit 96h clock advance.

Only the command's clock is shifted: S3, DB references and deletion are real.
The orchestrator stops writers for the plan/recheck/apply sequence.
"""

import io
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import django

django.setup()
from apps.materials.models import Material
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage as storage
from django.core.management import call_command
from django.utils import timezone

assert settings.DATABASES["default"]["NAME"] == "jazsem_rc_runtime"
assert storage.bucket_name == "jazsem-acceptance-private"
client = storage.connection.meta.client


def objects():
    return {
        item["Key"]
        for page in client.get_paginator("list_objects_v2").paginate(
            Bucket=storage.bucket_name
        )
        for item in page.get("Contents", [])
    }


existing = objects()
material = Material.objects.exclude(file="").first()
assert material is not None
shared = material.file.name
assert Material.objects.filter(file=shared).count() >= 2
orphan = storage.save(
    "private/acceptance/confirmed-orphan.txt", ContentFile(b"Synthetic orphan")
)
new_reference = storage.save(
    "private/acceptance/referenced-after-plan.txt", ContentFile(b"Synthetic retained")
)
manifest = Path("/control/orphan-manifest.json")
with patch(
    "apps.materials.management.commands.orphan_uploads.timezone.now",
    return_value=timezone.now() + timedelta(hours=96),
):
    call_command("orphan_uploads", manifest=str(manifest), stdout=io.StringIO())
    planned = json.loads(manifest.read_text())
    assert set(planned["keys"]) == {orphan, new_reference}
    # A reference created after review must win over the stale manifest.
    Material.objects.create(
        topic=material.topic,
        title="Retained during cleanup",
        type="FILE",
        file=new_reference,
    )
    planned["keys"].extend([shared, settings.STORAGE_PROBE_KEY])
    manifest.write_text(json.dumps(planned))
    call_command(
        "orphan_uploads", manifest=str(manifest), apply=True, stdout=io.StringIO()
    )
assert not storage.exists(orphan)
assert storage.exists(new_reference)
assert existing <= objects()
print(
    json.dumps(
        {
            "s3_orphan_plan_and_apply": "passed",
            "deleted_synthetic_orphans": 1,
            "reference_recheck_shared_files_and_sentinel_preserved": True,
            "grace_clock_advance_hours": 96,
            "writers_stopped": True,
        }
    )
)
