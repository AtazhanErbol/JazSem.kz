from django.core.files.uploadedfile import SimpleUploadedFile

from apps.courses.models import Topic, Week
from apps.courses.services import new_version
from apps.materials.models import Material


def test_replacing_draft_material_updates_download_name(world, client_for):
    version = new_version(world["course"], world["teacher"])
    topic = Topic.objects.create(
        week=Week.objects.create(course_version=version, number=1, title="Week"), title="Topic"
    )
    material = Material.objects.create(
        topic=topic,
        title="Notes",
        type="FILE",
        file=SimpleUploadedFile("old.txt", b"old"),
        original_filename="old.txt",
    )
    response = client_for(world["teacher"]).patch(
        f"/api/v1/materials/{material.pk}/",
        {"file": SimpleUploadedFile("new.txt", b"new content", content_type="text/plain")},
        format="multipart",
    )
    assert response.status_code == 200
    material.refresh_from_db()
    assert material.original_filename == "new.txt"
    assert material.size == 11 and material.mime_type == "text/plain"


def test_orphan_cleanup_preserves_shared_references_and_grace_period(world, tmp_path):
    import json
    import os
    import time

    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from django.core.management import call_command

    old = default_storage.save("private/orphan.txt", ContentFile(b"orphan"))
    recent = default_storage.save("private/recent.txt", ContentFile(b"recent"))
    shared = world["material"].file.name
    Material.objects.create(topic=world["topic"], title="Shared reference", file=shared)
    for key in [old, shared]:
        os.utime(default_storage.path(key), (time.time() - 4 * 86400, time.time() - 4 * 86400))
    manifest = tmp_path / "cleanup.json"
    call_command("orphan_uploads", manifest=str(manifest))
    assert json.loads(manifest.read_text())["keys"] == [old]
    assert default_storage.exists(old)
    # Even a stale/expanded plan cannot remove a referenced or recent object.
    manifest.write_text(json.dumps({"keys": [old, recent, shared]}))
    call_command("orphan_uploads", manifest=str(manifest), apply=True)
    assert not default_storage.exists(old)
    assert default_storage.exists(shared) and default_storage.exists(recent)
