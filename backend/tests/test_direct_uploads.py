import io
import json
from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.assignments.models import SubmissionFile
from apps.common.direct_uploads import MEDIA_TYPE, cleanup_uploads
from apps.common.models import UploadTicket
from apps.courses.models import Topic, Week
from apps.courses.services import new_version
from apps.materials.models import Material


@pytest.fixture
def direct(settings, monkeypatch):
    settings.DIRECT_UPLOADS_ENABLED = True
    objects = {}
    client = Mock()
    client.generate_presigned_post.return_value = {
        "url": "https://storage.example.test/",
        "fields": {"policy": "synthetic-test-policy"},
    }

    def get_object(**kwargs):
        data, content_type = objects[kwargs["Key"]]
        return {"Body": io.BytesIO(data), "ContentLength": len(data), "ContentType": content_type}

    client.get_object.side_effect = get_object
    monkeypatch.setattr(
        "apps.common.direct_uploads.storage_client", lambda: (client, "test-private")
    )
    return objects, client


def grant(client, target, data, *, size=10, field="file", count=1, method="POST", name="notes.txt"):
    response = client.post(
        "/api/v1/uploads/",
        {
            "target": target,
            "method": method,
            "data": data,
            "files": [{"field": field, "name": name, "type": "text/plain", "size": size}] * count,
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    return response.data["uploads"]


def attach(client, target, data, grants, *, method="post"):
    return getattr(client, method)(
        "/api/v1/" + target,
        json.dumps({"data": data, "tickets": [g["ticket"] for g in grants]}),
        content_type=MEDIA_TYPE,
    )


def draft_topic(world):
    version = new_version(world["course"], world["teacher"])
    week = Week.objects.create(course_version=version, number=1, title="Draft")
    return Topic.objects.create(week=week, title="Direct uploads")


def store_grants(direct, grants, data=b"notes data", mime="text/plain"):
    for g in grants:
        ticket = UploadTicket.objects.get(pk=g["ticket"])
        direct[0][ticket.key] = (data, mime)


@pytest.mark.django_db
def test_full_25_mib_upload_keeps_original_validation_and_metadata(world, client_for, direct):
    client = client_for(world["teacher"])
    topic = draft_topic(world)
    data = {"topic": str(topic.pk), "title": "Large file", "type": "FILE"}
    content = b"a" * (25 * 1024 * 1024)
    grants = grant(client, "materials/", data, size=len(content))
    store_grants(direct, grants, content)
    policy = direct[1].generate_presigned_post.call_args.kwargs
    assert ["content-length-range", len(content), len(content)] in policy["Conditions"]
    assert policy["ExpiresIn"] == 300
    response = attach(client, "materials/", data, grants)
    assert response.status_code == 201, response.data
    material = Material.objects.get(pk=response.data["id"])
    assert material.size == len(content)
    assert material.original_filename == "notes.txt"
    assert "quarantine" not in material.file.name
    with material.file.open("rb") as file:
        assert file.read() == content
    assert UploadTicket.objects.get(pk=grants[0]["ticket"]).consumed
    assert attach(client, "materials/", data, grants).status_code == 400


@pytest.mark.django_db
def test_student_submission_preserves_five_attachments(world, client_for, direct):
    client = client_for(world["student"])
    target = f"assignments/{world['assignment'].pk}/submit/"
    data = {"text_answer": "  My solution\n "}
    grants = grant(client, target, data, field="files", count=5)
    store_grants(direct, grants)
    response = attach(client, target, data, grants)
    assert response.status_code == 201, response.data
    assert SubmissionFile.objects.filter(submission_id=response.data["id"]).count() == 5


@pytest.mark.django_db
def test_private_download_redirect_preserves_authorization_and_expiry(
    world, client_for, direct, monkeypatch
):
    from urllib.parse import parse_qs, urlsplit

    from storages.backends.s3 import S3Storage

    storage = S3Storage(
        access_key="synthetic-key",
        secret_key="synthetic-secret",
        bucket_name="test-private",
        endpoint_url="https://storage.example.test",
        region_name="auto",
    )
    monkeypatch.setattr(Material._meta.get_field("file"), "storage", storage)
    target = f"/api/v1/materials/{world['material'].pk}/download/"
    assert client_for(world["outsider"]).get(target).status_code == 404
    response = client_for(world["student"]).get(target)
    assert response.status_code == 302
    query = parse_qs(urlsplit(response["Location"]).query)
    assert query["X-Amz-Expires"] == ["60"]
    assert query["response-content-type"] == ["application/octet-stream"]
    assert query["response-content-disposition"][0].startswith("attachment;")
    assert response["Cache-Control"] == "private, no-store"
    assert response["Referrer-Policy"] == "no-referrer"


@pytest.mark.django_db
@pytest.mark.parametrize("change", ["owner", "context", "target", "method", "expiry", "duplicate"])
def test_ticket_cannot_be_rebound_or_reused(world, client_for, direct, change):
    client = client_for(world["teacher"])
    data = {"topic": str(draft_topic(world).pk), "title": "Bound file", "type": "FILE"}
    grants = grant(client, "materials/", data)
    store_grants(direct, grants)
    target = "materials/"
    method = "post"
    if change == "owner":
        client = client_for(world["other"])
    elif change == "context":
        data["title"] = "Changed context"
    elif change == "target":
        target = "sources/"
    elif change == "method":
        method = "patch"
        target = f"materials/{world['material'].pk}/"
    elif change == "expiry":
        UploadTicket.objects.filter(pk=grants[0]["ticket"]).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
    elif change == "duplicate":
        grants *= 2
    assert attach(client, target, data, grants, method=method).status_code == 400
    assert not UploadTicket.objects.get(pk=grants[0]["ticket"]).consumed
    direct[1].get_object.assert_not_called()


@pytest.mark.django_db
def test_invalid_contents_are_rejected_and_not_saved(world, client_for, direct):
    client = client_for(world["teacher"])
    data = {"topic": str(draft_topic(world).pk), "title": "Bad file"}
    grants = grant(client, "materials/", data)
    store_grants(direct, grants, b"a\x00invalid!")
    response = attach(client, "materials/", data, grants)
    assert response.status_code == 400
    assert not Material.objects.filter(title="Bad file").exists()
    assert not UploadTicket.objects.get(pk=grants[0]["ticket"]).consumed


@pytest.mark.django_db
def test_upload_authorization_and_size_limit_precede_grants(world, client_for, direct):
    payload = {
        "target": "sources/",
        "method": "POST",
        "data": {"course": str(world["course"].pk)},
        "files": [{"field": "file", "name": "x.txt", "type": "text/plain", "size": 10}],
    }
    assert (
        client_for(world["student"]).post("/api/v1/uploads/", payload, format="json").status_code
        == 403
    )
    assert (
        client_for(world["other"]).post("/api/v1/uploads/", payload, format="json").status_code
        == 404
    )
    payload["files"][0]["size"] = 25 * 1024 * 1024 + 1
    assert (
        client_for(world["teacher"]).post("/api/v1/uploads/", payload, format="json").status_code
        == 400
    )
    direct[1].generate_presigned_post.assert_not_called()


@pytest.mark.django_db
def test_only_expired_quarantine_objects_are_cleaned(world, client_for, direct):
    client = client_for(world["teacher"])
    grants = grant(client, "sources/", {"course": str(world["course"].pk)}, count=1)
    ticket = UploadTicket.objects.get(pk=grants[0]["ticket"])
    cleanup_uploads()
    direct[1].delete_object.assert_not_called()
    ticket.expires_at = timezone.now() - timedelta(seconds=1)
    ticket.save()
    cleanup_uploads()
    direct[1].delete_object.assert_called_once_with(Bucket="test-private", Key=ticket.key)
    assert not UploadTicket.objects.filter(pk=ticket.pk).exists()
