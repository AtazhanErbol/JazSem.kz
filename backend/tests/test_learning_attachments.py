import io
import struct
import zipfile
from datetime import timedelta
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.accounts.models import User
from apps.common.models import UploadTicket
from apps.courses.services import duplicate, publish
from apps.enrollments.services import enroll
from apps.materials.management.commands.orphan_uploads import referenced
from apps.materials.models import LearningAttachment
from apps.materials.validation import validate_upload
from apps.materials.youtube import embed_url, normalize_youtube


@pytest.fixture
def draft(world):
    version = duplicate(world["version"], world["teacher"])
    topic = version.weeks.get().topics.get()
    return {
        "version": version,
        "topic": topic,
        "assignment": topic.assignments.get(),
        "test": topic.tests.get(),
        "question": topic.tests.get().questions.get(),
    }


def file(name="notes.txt", content=b"Lesson notes", mime="text/plain"):
    return SimpleUploadedFile(name, content, content_type=mime)


def upload(client, parent, **overrides):
    data = {
        **parent,
        "title": "Дополнительный материал",
        "kind": "FILE",
        "file": file(),
        **overrides,
    }
    return client.post("/api/v1/attachments/", data, format="multipart")


@pytest.mark.parametrize("owner", ["topic", "assignment", "test", "question"])
def test_multiple_attachments_survive_metadata_edits_and_remain_private(
    world, draft, client_for, owner
):
    client = client_for(world["teacher"])
    first = upload(client, {owner: str(draft[owner].pk)})
    second = upload(client, {owner: str(draft[owner].pk)}, title="Второй файл")
    assert first.status_code == second.status_code == 201, first.data
    identity = first.data["id"]
    original = LearningAttachment.objects.get(pk=identity).file.name
    response = client.patch(
        f"/api/v1/attachments/{identity}/", {"title": "Новое имя", "order": 9}, format="json"
    )
    assert response.status_code == 200
    assert response.data["file"] is True
    assert "private/" not in str(response.data)
    assert LearningAttachment.objects.get(pk=identity).file.name == original
    assert (
        client_for(world["other"]).get(f"/api/v1/attachments/{identity}/download/").status_code
        == 404
    )
    assert (
        client_for(world["student"]).get(f"/api/v1/attachments/{identity}/download/").status_code
        == 404
    )
    assert (
        client_for(world["admin"]).get(f"/api/v1/attachments/{identity}/download/").status_code
        == 200
    )
    assert LearningAttachment.objects.filter(**{owner: draft[owner]}).count() == 2
    assert referenced(original)


def test_publishing_keeps_old_students_files_attempts_and_version_ownership(world, client_for):
    student = client_for(world["student"])
    attempt = student.post(f"/api/v1/tests/{world['test'].pk}/start/", {}, format="json")
    assert attempt.status_code == 200
    from apps.testing.models import TestAttempt

    active_attempt = TestAttempt.objects.get(pk=attempt.data["id"])
    original_questions = list(active_attempt.question_order)
    old = LearningAttachment.objects.create(
        topic=world["topic"],
        title="Old notes",
        file=file(),
        original_filename="notes.txt",
        mime_type="text/plain",
        size=12,
    )
    version = duplicate(world["version"], world["teacher"])
    cloned = version.weeks.get().topics.get().attachments.get()
    assert cloned.pk != old.pk and cloned.file.name == old.file.name
    teacher = client_for(world["teacher"])
    changed = teacher.patch(
        f"/api/v1/attachments/{cloned.pk}/",
        {"file": file(content=b"Revised notes")},
        format="multipart",
    )
    assert changed.status_code == 200, changed.data
    cloned.refresh_from_db()
    assert cloned.file.name != old.file.name
    publish(version, world["teacher"])
    active_attempt.refresh_from_db()
    assert active_attempt.test_id == world["test"].pk
    assert active_attempt.question_order == original_questions
    assert active_attempt.status == "IN_PROGRESS"
    world["enrollment"].refresh_from_db()
    assert world["enrollment"].course_version_id == world["version"].pk
    student = client_for(world["student"])
    response = student.get(f"/api/v1/attachments/{old.pk}/download/")
    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"Lesson notes"
    assert student.get(f"/api/v1/attachments/{cloned.pk}/download/").status_code == 404
    assert (
        teacher.patch(
            f"/api/v1/attachments/{cloned.pk}/", {"title": "Forbidden"}, format="json"
        ).status_code
        == 400
    )
    assert teacher.delete(f"/api/v1/attachments/{old.pk}/").status_code == 400
    assert student.delete(f"/api/v1/attachments/{old.pk}/").status_code == 403


def test_reorder_direction_crosses_pages_and_skips_the_other_material_group(
    world, draft, client_for
):
    topic = draft["topic"]
    rows = [
        LearningAttachment.objects.create(
            topic=topic, title=f"File {index}", kind="FILE", file=f"notes-{index}.txt", order=index
        )
        for index in range(26)
    ]
    video = LearningAttachment.objects.create(
        topic=topic,
        title="Video",
        kind="YOUTUBE",
        external_url="https://youtu.be/dQw4w9WgXcQ",
        order=24,
    )
    teacher = client_for(world["teacher"])
    response = teacher.post(
        "/api/v1/attachments/reorder/",
        {"first": str(rows[25].pk), "direction": "UP"},
        format="json",
    )
    assert response.status_code == 204, response.data
    files = list(topic.attachments.filter(kind="FILE").values_list("id", flat=True))
    assert files[-2:] == [rows[25].pk, rows[24].pk]
    assert topic.attachments.filter(pk=video.pk).exists()
    assert (
        teacher.post(
            "/api/v1/attachments/reorder/",
            {"first": str(rows[0].pk), "direction": "UP"},
            format="json",
        ).status_code
        == 204
    )
    assert (
        teacher.post(
            "/api/v1/attachments/reorder/", {"first": str(rows[0].pk)}, format="json"
        ).status_code
        == 400
    )


def test_reorder_is_atomic_owned_and_does_not_delete_shared_files(world, draft, client_for):
    teacher = client_for(world["teacher"])
    first = upload(teacher, {"topic": str(draft["topic"].pk)})
    second = upload(teacher, {"topic": str(draft["topic"].pk)}, title="Second")
    data = {"first": first.data["id"], "second": second.data["id"]}
    assert teacher.post("/api/v1/attachments/reorder/", data, format="json").status_code == 204
    assert list(draft["topic"].attachments.values_list("id", flat=True)) == [
        LearningAttachment.objects.get(pk=second.data["id"]).pk,
        LearningAttachment.objects.get(pk=first.data["id"]).pk,
    ]
    assert (
        client_for(world["student"])
        .post("/api/v1/attachments/reorder/", data, format="json")
        .status_code
        == 403
    )
    attachment = LearningAttachment.objects.get(pk=first.data["id"])
    stored_name, storage = attachment.file.name, attachment.file.storage
    assert teacher.delete(f"/api/v1/attachments/{attachment.pk}/").status_code == 204
    assert storage.exists(stored_name)


@pytest.mark.parametrize(
    "extension,mime,marker",
    [
        (
            "docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "word/document.xml",
        ),
        (
            "pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "ppt/presentation.xml",
        ),
        (
            "xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xl/workbook.xml",
        ),
    ],
)
def test_office_container_signatures_and_macro_rejection(extension, mime, marker):
    def package(macro=False):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr(marker, "<document/>")
            if macro:
                archive.writestr("word/vbaProject.bin", b"macro")
        return file("lesson." + extension, data.getvalue(), mime)

    validate_upload(package())
    with pytest.raises(Exception):
        validate_upload(package(macro=True))


@pytest.mark.parametrize(
    "extension,mime,stream_name",
    [
        ("doc", "application/msword", "WordDocument"),
        ("ppt", "application/vnd.ms-powerpoint", "PowerPoint Document"),
        ("xls", "application/vnd.ms-excel", "Workbook"),
    ],
)
def test_legacy_office_checks_the_compound_directory(extension, mime, stream_name):
    # A minimal valid CFB v3 directory/FAT. No real teaching documents are used.
    end, free, fat_sector = 0xFFFFFFFE, 0xFFFFFFFF, 0xFFFFFFFD
    header = bytearray(512)
    header[:8] = bytes.fromhex("D0CF11E0A1B11AE1")
    struct.pack_into("<HHHHH", header, 24, 0x3E, 3, 0xFFFE, 9, 6)
    struct.pack_into("<IIIIIIIII", header, 40, 0, 1, 0, 0, 4096, end, 0, end, 0)
    struct.pack_into("<109I", header, 76, 1, *([free] * 108))
    directory = bytearray(512)
    for offset, name, kind, child, sector, size in [
        (0, "Root Entry", 5, 1, end, 0),
        (128, stream_name, 2, free, 2, 4096),
    ]:
        encoded = (name + "\0").encode("utf-16le")
        directory[offset : offset + len(encoded)] = encoded
        struct.pack_into(
            "<HBBIII", directory, offset + 64, len(encoded), kind, 1, free, free, child
        )
        struct.pack_into("<IQ", directory, offset + 116, sector, size)
    sectors = [free] * 128
    sectors[0], sectors[1], sectors[9] = end, fat_sector, end
    for index in range(2, 9):
        sectors[index] = index + 1
    content = bytes(header) + bytes(directory) + struct.pack("<128I", *sectors) + bytes(4096)
    validate_upload(file("lesson." + extension, content, mime))
    with pytest.raises(Exception):
        validate_upload(
            file(
                "renamed.doc" if extension != "doc" else "renamed.xls",
                content,
                "application/msword" if extension != "doc" else "application/vnd.ms-excel",
            )
        )


@pytest.mark.parametrize(
    "name,mime,size",
    [
        ("clip.mp4", "video/mp4", 251 * 1024 * 1024),
        ("notes.pdf", "application/pdf", 26 * 1024 * 1024),
        ("clip.mov", "video/quicktime", 1024),
        ("empty.txt", "text/plain", 0),
        ("script.svg", "image/svg+xml", 100),
    ],
)
def test_invalid_upload_metadata_never_receives_a_storage_grant(
    world, draft, client_for, settings, monkeypatch, name, mime, size
):
    settings.DIRECT_UPLOADS_ENABLED = True
    storage = Mock()
    monkeypatch.setattr(
        "apps.common.direct_uploads.storage_client", lambda: (storage, "private-test")
    )
    result = client_for(world["teacher"]).post(
        "/api/v1/uploads/",
        {
            "target": "attachments/",
            "method": "POST",
            "data": {
                "topic": str(draft["topic"].pk),
                "kind": "VIDEO" if mime.startswith("video/") else "FILE",
                "title": "Invalid",
            },
            "files": [{"field": "file", "name": name, "type": mime, "size": size}],
        },
        format="json",
    )
    assert result.status_code == 400
    assert storage.generate_presigned_post.call_count == 0


def test_test_and_question_files_do_not_expose_answers_and_require_an_attempt(
    world, draft, client_for
):
    teacher = client_for(world["teacher"])
    test_file = upload(teacher, {"test": str(draft["test"].pk)})
    question_file = upload(teacher, {"question": str(draft["question"].pk)})
    publish(draft["version"], world["teacher"])
    new_student = User.objects.create_user(
        username="attachment-student",
        role="STUDENT",
        owner_teacher=world["teacher"],
        must_change_password=False,
    )
    world["course"].refresh_from_db()
    enroll(world["teacher"], new_student, world["course"])
    student = client_for(new_student)
    response = student.get(f"/api/v1/attachments/?test={draft['test'].pk}")
    assert response.status_code == 200
    assert response.data["count"] == 1
    assert not {"is_correct", "explanation", "source_chunks"} & set(response.data["results"][0])
    assert student.get(f"/api/v1/attachments/{test_file.data['id']}/download/").status_code == 200
    question_url = f"/api/v1/attachments/{question_file.data['id']}/download/"
    assert student.get(question_url).status_code == 404
    attempt = student.post(f"/api/v1/tests/{draft['test'].pk}/start/", {}, format="json")
    assert attempt.status_code == 200, attempt.data
    assert student.get(question_url).status_code == 200
    detail = student.get(f"/api/v1/attempts/{attempt.data['id']}/")
    assert "is_correct" not in str(detail.data) and "explanation" not in str(detail.data)


def test_a_file_only_lecture_is_published_visible_and_counted_in_progress(world, draft, client_for):
    from apps.courses.models import Topic
    from apps.progress.services import summary

    topic = Topic.objects.create(week=draft["topic"].week, title="File-only lecture")
    uploaded = upload(client_for(world["teacher"]), {"topic": str(topic.pk)})
    assert uploaded.status_code == 201
    publish(draft["version"], world["teacher"])
    new_student = User.objects.create_user(
        username="file-only-student",
        role="STUDENT",
        owner_teacher=world["teacher"],
        must_change_password=False,
    )
    world["course"].refresh_from_db()
    enrollment = enroll(world["teacher"], new_student, world["course"])
    student = client_for(new_student)
    tree = student.get(f"/api/v1/courses/{world['course'].pk}/tree/").data
    lecture = next(
        item for week in tree["weeks"] for item in week["topics"] if item["id"] == str(topic.pk)
    )
    assert lecture["content"] == "" and lecture["has_attachment_content"] is True
    before = summary(enrollment)
    result = student.post(f"/api/v1/topics/{topic.pk}/complete/", {}, format="json")
    assert result.status_code == 200
    assert str(topic.pk) in result.data["read_topics"]
    assert result.data["completed"] == before["completed"] + 1


@pytest.mark.parametrize(
    "url",
    [
        "https://youtu.be/dQw4w9WgXcQ?t=4",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&feature=shared",
        "https://youtube.com/shorts/dQw4w9WgXcQ",
        "https://m.youtube.com/live/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "youtu.be/dQw4w9WgXcQ",
    ],
)
def test_youtube_links_are_normalized_to_a_safe_embed(url):
    assert normalize_youtube(url) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert embed_url(url) == "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ",
        "https://youtube.com@evil.test/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/playlist?list=secret",
        "<iframe src='https://evil.test'></iframe>",
        "https://youtu.be/invalid",
        "https://youtube.com:8443/watch?v=dQw4w9WgXcQ",
    ],
)
def test_invalid_video_links_are_rejected(url):
    with pytest.raises(Exception):
        normalize_youtube(url)


def test_assignment_accepts_multiple_videos_and_safe_youtube(world, draft, client_for):
    client = client_for(world["teacher"])
    parent = {"assignment": str(draft["assignment"].pk)}
    mp4 = struct.pack(">I", 24) + b"ftypisom" + b"\x00\x00\x00\x00" + b"isommp42" + b"mdat"
    uploaded = upload(client, parent, kind="VIDEO", file=file("lesson.mp4", mp4, "video/mp4"))
    assert uploaded.status_code == 201, uploaded.data
    youtube = client.post(
        "/api/v1/attachments/",
        {
            **parent,
            "title": "Example",
            "kind": "YOUTUBE",
            "external_url": "https://youtube.com/shorts/dQw4w9WgXcQ",
        },
        format="json",
    )
    assert youtube.status_code == 201, youtube.data
    assert youtube.data["embed_url"].startswith("https://www.youtube-nocookie.com/embed/")
    assert draft["assignment"].attachments.count() == 2


@pytest.mark.parametrize(
    "name,mime,data",
    [
        ("bad.pdf", "application/pdf", b"MZ executable"),
        ("bad.mp4", "video/mp4", b"not a video"),
        ("bad.mov", "video/quicktime", b"ftypqt"),
        (
            "bad.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            b"PKnotxlsx",
        ),
    ],
)
def test_attachment_types_are_checked_on_the_server(name, mime, data):
    with pytest.raises(Exception):
        validate_upload(file(name, data, mime), allow_video=True)


@pytest.mark.parametrize(
    "case",
    ["success", "incomplete", "expired", "wrong_context", "wrong_owner", "changed", "corrupt"],
)
def test_direct_video_uses_bounded_ranges_and_conditional_storage_copy(
    world, draft, client_for, settings, monkeypatch, case
):
    settings.DIRECT_UPLOADS_ENABLED = True
    size = 100 * 1024 * 1024
    prefix = struct.pack(">I", 24) + b"ftypisom" + b"\x00\x00\x00\x00" + b"isommp42"
    storage = Mock()
    storage.generate_presigned_post.return_value = {
        "url": "https://private.example.test/",
        "fields": {"policy": "test"},
    }
    storage.head_object.return_value = {
        "ContentLength": size,
        "ContentType": "video/mp4",
        "ETag": '"version-1"',
    }

    def read_range(**kwargs):
        start, end = map(int, kwargs["Range"].removeprefix("bytes=").split("-"))
        assert kwargs["IfMatch"] == '"version-1"'
        return {"Body": io.BytesIO(prefix[start : end + 1].ljust(end - start + 1, b"\x00"))}

    storage.get_object.side_effect = read_range
    for target in (
        "apps.common.direct_uploads.storage_client",
        "apps.materials.remote_uploads.storage_client",
    ):
        monkeypatch.setattr(target, lambda: (storage, "private-test-bucket"))
    client = client_for(world["teacher"])
    data = {"assignment": str(draft["assignment"].pk), "kind": "VIDEO", "title": "Large lecture"}
    response = client.post(
        "/api/v1/uploads/",
        {
            "target": "attachments/",
            "method": "POST",
            "data": data,
            "files": [{"field": "file", "name": "lecture.mp4", "type": "video/mp4", "size": size}],
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    ticket = response.data["uploads"][0]["ticket"]
    if case == "incomplete":
        storage.head_object.return_value["ContentLength"] = size - 1
    elif case == "expired":
        UploadTicket.objects.filter(pk=ticket).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
    elif case == "wrong_context":
        data["title"] = "Changed after signing"
    elif case == "wrong_owner":
        client = client_for(world["admin"])
    elif case == "changed":
        storage.copy_object.side_effect = ClientError(
            {"Error": {"Code": "PreconditionFailed"}}, "CopyObject"
        )
    elif case == "corrupt":
        prefix = b"Not a video"
    attached = client.post("/api/v1/attachments/", {**data, "upload_ticket": ticket}, format="json")
    if case != "success":
        assert attached.status_code == 400, attached.data
        assert not UploadTicket.objects.get(pk=ticket).consumed
        assert not draft["assignment"].attachments.exists()
        assert storage.copy_object.call_count == (1 if case == "changed" else 0)
        return
    assert attached.status_code == 201, attached.data
    assert attached.data["size"] == size
    assert storage.get_object.call_count == 1
    assert storage.get_object.call_args.kwargs["Range"] == "bytes=0-65535"
    assert storage.copy_object.call_args.kwargs["CopySourceIfMatch"] == '"version-1"'
    assert UploadTicket.objects.get(pk=ticket).consumed
    assert (
        client.post(
            "/api/v1/attachments/", {**data, "upload_ticket": ticket}, format="json"
        ).status_code
        == 400
    )
