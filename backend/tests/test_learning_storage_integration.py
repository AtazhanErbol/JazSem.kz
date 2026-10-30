"""Opt-in real S3 interoperability checks against a disposable local MinIO only."""

import os
import struct
import time
from unittest.mock import patch
from urllib.parse import urlsplit

import pytest
import requests
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

from apps.accounts.models import User
from apps.common.direct_uploads import storage_client
from apps.common.models import UploadTicket
from apps.courses.services import duplicate, publish
from apps.enrollments.services import enroll
from apps.materials.models import LearningAttachment
from apps.materials.remote_uploads import RemoteFile

pytestmark = pytest.mark.skipif(
    os.environ.get("JAZSEM_STORAGE_INTEGRATION") != "1",
    reason="Requires the explicit disposable MinIO integration profile",
)


@pytest.fixture(scope="session", autouse=True)
def private_test_bucket():
    if os.environ.get("JAZSEM_STORAGE_INTEGRATION") != "1":
        return
    options = settings.STORAGES["default"]["OPTIONS"]
    host = urlsplit(options["endpoint_url"]).hostname
    assert options["bucket_name"] == "jazsem-attachment-integration"
    assert options["access_key"] == "synthetic-acceptance"
    assert host in {"localhost", "127.0.0.1"} or (
        host == "minio" and os.environ.get("E2E_ISOLATED_STORAGE") == "1"
    )
    client, bucket = storage_client()
    deadline = time.monotonic() + 60
    while True:
        try:
            client.list_buckets()
            break
        except (BotoCoreError, ClientError):
            if time.monotonic() > deadline:
                raise
            time.sleep(0.25)
    try:
        client.create_bucket(Bucket=bucket)
    except ClientError as error:
        if error.response["Error"]["Code"] != "BucketAlreadyOwnedByYou":
            raise


def prepare_video(world, client_for, settings):
    settings.DIRECT_UPLOADS_ENABLED = True
    version = duplicate(world["version"], world["teacher"])
    topic = version.weeks.get().topics.get()
    data = {
        "assignment": str(topic.assignments.get().pk),
        "kind": "VIDEO",
        "title": "Storage integration video",
    }
    content = struct.pack(">I", 24) + b"ftypisom" + bytes(4) + b"isommp42" + bytes(1024 * 1024)
    teacher = client_for(world["teacher"])
    response = teacher.post(
        "/api/v1/uploads/",
        {
            "target": "attachments/",
            "method": "POST",
            "data": data,
            "files": [
                {"field": "file", "name": "example.mp4", "type": "video/mp4", "size": len(content)}
            ],
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    grant = response.data["uploads"][0]
    result = requests.post(
        grant["url"],
        data=grant["fields"],
        files={"file": ("example.mp4", content, "video/mp4")},
        timeout=20,
    )
    assert result.status_code in {200, 201, 204}, result.text
    return teacher, version, data, grant["ticket"], content


def test_real_private_storage_copy_range_playback_and_version_permissions(
    world, client_for, settings
):
    teacher, version, data, ticket, content = prepare_video(world, client_for, settings)
    with patch(
        "apps.common.direct_uploads.TemporaryUploadedFile",
        side_effect=AssertionError("Never proxy video through a temporary upload"),
    ):
        result = teacher.post(
            "/api/v1/attachments/", {**data, "upload_ticket": ticket}, format="json"
        )
    assert result.status_code == 201, result.data
    assert int(result.wsgi_request.META["CONTENT_LENGTH"]) < 2048
    attachment = LearningAttachment.objects.get(pk=result.data["id"])
    client, bucket = storage_client()
    # Subsequent changes to a grant's quarantine object cannot alter the immutable promoted object.
    client.put_object(
        Bucket=bucket,
        Key=UploadTicket.objects.get(pk=ticket).key,
        Body=b"changed",
        ContentType="video/mp4",
    )
    obj = client.get_object(Bucket=bucket, Key=attachment.file.name)
    try:
        assert obj["Body"].read() == content
    finally:
        obj["Body"].close()
    publish(version, world["teacher"])
    assert (
        client_for(world["student"])
        .get(f"/api/v1/attachments/{attachment.pk}/download/")
        .status_code
        == 404
    )
    student = User.objects.create_user(
        username="storage-student",
        role="STUDENT",
        owner_teacher=world["teacher"],
        must_change_password=False,
    )
    world["course"].refresh_from_db()
    enroll(world["teacher"], student, world["course"])
    response = client_for(student).get(f"/api/v1/attachments/{attachment.pk}/preview/")
    assert response.status_code == 302
    played = requests.get(response["Location"], headers={"Range": "bytes=0-31"}, timeout=10)
    assert played.status_code == 206 and played.content == content[:32]
    assert "no-store" in response["Cache-Control"]
    unsigned = (
        settings.STORAGES["default"]["OPTIONS"]["endpoint_url"].rstrip("/")
        + "/"
        + bucket
        + "/"
        + attachment.file.name
    )
    assert requests.get(unsigned, timeout=10).status_code == 403
    assert (
        client_for(world["other"]).get(f"/api/v1/attachments/{attachment.pk}/download/").status_code
        == 404
    )


def test_real_storage_rejects_an_object_changed_between_validation_and_copy(
    world, client_for, settings
):
    teacher, _version, data, ticket, content = prepare_video(world, client_for, settings)
    client, bucket = storage_client()
    original_read = RemoteFile.read
    changed = False

    def race(file, length=-1):
        nonlocal changed
        result = original_read(file, length)
        if not changed:
            changed = True
            client.put_object(
                Bucket=bucket,
                Key=UploadTicket.objects.get(pk=ticket).key,
                Body=b"MZ" + bytes(len(content) - 2),
                ContentType="video/mp4",
            )
        return result

    with patch.object(RemoteFile, "read", race):
        result = teacher.post(
            "/api/v1/attachments/", {**data, "upload_ticket": ticket}, format="json"
        )
    assert result.status_code == 400, result.data
    assert not UploadTicket.objects.get(pk=ticket).consumed
    assert not LearningAttachment.objects.filter(assignment_id=data["assignment"]).exists()
