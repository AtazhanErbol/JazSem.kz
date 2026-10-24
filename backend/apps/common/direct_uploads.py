"""Private direct uploads: bounded grants, immutable server-validated attachments."""

import hashlib
import json
import logging
import re
import uuid
from datetime import timedelta
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.db import transaction
from django.http import Http404, QueryDict
from django.utils import timezone
from django.utils.datastructures import MultiValueDict
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import DataAndFiles
from rest_framework.response import Response
from rest_framework.views import APIView
from storages.backends.s3 import S3Storage

from apps.common.models import UploadTicket
from apps.common.permissions import is_teacher
from apps.materials.validation import MIMES, validate_upload

MEDIA_TYPE = "application/vnd.jazsem.upload+json"
log = logging.getLogger("uploads")
UUID = r"[0-9a-fA-F-]{36}"


def storage_client():
    if not isinstance(default_storage, S3Storage):
        raise ValidationError("Прямая загрузка не настроена.")
    return default_storage.connection.meta.client, default_storage.bucket_name


def context_digest(data):
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


class FileInput(serializers.Serializer):
    field = serializers.ChoiceField(choices=["file", "files"])
    name = serializers.CharField(max_length=255, trim_whitespace=False)
    type = serializers.CharField(max_length=150)
    size = serializers.IntegerField(min_value=1)

    def validate(self, data):
        name = data["name"]
        suffix = Path(name).suffix.lower()
        if (
            "/" in name
            or "\\" in name
            or any(ord(char) < 32 for char in name)
            or suffix not in MIMES
            or data["type"] != MIMES[suffix]
            or data["size"] > settings.MAX_UPLOAD_BYTES
        ):
            raise ValidationError("Недопустимое имя, тип или размер файла.")
        return data


class UploadInput(serializers.Serializer):
    target = serializers.CharField(max_length=255)
    method = serializers.ChoiceField(choices=["POST", "PATCH"])
    data = serializers.DictField(
        child=serializers.CharField(allow_blank=True, max_length=100000, trim_whitespace=False)
    )
    files = FileInput(many=True, allow_empty=False, max_length=5)


class UploadGrantOutput(serializers.Serializer):
    ticket = serializers.UUIDField()
    url = serializers.URLField()
    fields = serializers.DictField(child=serializers.CharField())


class UploadOutput(serializers.Serializer):
    uploads = UploadGrantOutput(many=True)


def authorize_target(user, target, method, data, files):
    # Business permissions are checked again by the original endpoint when attaching.
    from apps.assignments.models import Assignment
    from apps.common.api import lookup
    from apps.common.scope import editable
    from apps.courses.models import Course, Topic
    from apps.materials.models import Material

    if target == "materials/" and method == "POST":
        if not is_teacher(user):
            raise PermissionDenied()
        topic_id = serializers.UUIDField().run_validation(data.get("topic"))
        editable(lookup(Topic, topic_id, user), user)
    elif re.fullmatch(rf"materials/({UUID})/", target) and method == "PATCH":
        if not is_teacher(user):
            raise PermissionDenied()
        pk = serializers.UUIDField().run_validation(target.split("/")[1])
        editable(lookup(Material, pk, user), user)
    elif target == "sources/" and method == "POST":
        if not is_teacher(user):
            raise PermissionDenied()
        course_id = serializers.UUIDField().run_validation(data.get("course"))
        lookup(Course, course_id, user)
        from apps.common.background import require_worker

        require_worker()
    elif re.fullmatch(rf"assignments/({UUID})/submit/", target) and method == "POST":
        if user.role != "STUDENT":
            raise PermissionDenied()
        pk = serializers.UUIDField().run_validation(target.split("/")[1])
        lookup(Assignment, pk, user)
        if any(file["field"] != "files" for file in files):
            raise ValidationError("Ожидаются файлы работы.")
        return
    else:
        raise ValidationError("Недопустимое действие загрузки.")
    if len(files) != 1 or files[0]["field"] != "file":
        raise ValidationError("Ожидается один файл.")


class DirectUploadView(APIView):
    throttle_scope = "upload_grant"
    serializer_class = UploadInput

    @extend_schema(request=UploadInput, responses={201: UploadOutput})
    @transaction.atomic
    def post(self, request):
        if not settings.DIRECT_UPLOADS_ENABLED:
            raise Http404()
        serializer = UploadInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        params = serializer.validated_data
        authorize_target(request.user, **params)
        client, bucket = storage_client()
        uploads = []
        with transaction.atomic():
            for file in params["files"]:
                ticket = UploadTicket.objects.create(
                    owner=request.user,
                    target="/api/v1/" + params["target"],
                    method=params["method"],
                    context_digest=context_digest(params["data"]),
                    field=file["field"],
                    filename=file["name"],
                    mime_type=file["type"],
                    size=file["size"],
                    key=f"private/quarantine/{uuid.uuid4().hex}",
                    expires_at=timezone.now() + timedelta(minutes=15),
                )
                try:
                    grant = client.generate_presigned_post(
                        Bucket=bucket,
                        Key=ticket.key,
                        Fields={"Content-Type": ticket.mime_type},
                        Conditions=[
                            {"Content-Type": ticket.mime_type},
                            ["content-length-range", ticket.size, ticket.size],
                        ],
                        ExpiresIn=300,
                    )
                except (BotoCoreError, ClientError):
                    raise ValidationError("Хранилище временно недоступно.") from None
                uploads.append({"ticket": str(ticket.pk), **grant})
        return Response({"uploads": uploads}, status=201)


def load_file(ticket):
    client, bucket = storage_client()
    upload = TemporaryUploadedFile(ticket.filename, ticket.mime_type, ticket.size, None)
    try:
        obj = client.get_object(Bucket=bucket, Key=ticket.key)
        stream = obj["Body"]
        try:
            if obj["ContentLength"] != ticket.size or obj["ContentType"] != ticket.mime_type:
                raise ValidationError("Метаданные загруженного файла изменились.")
            total = 0
            while chunk := stream.read(min(1024 * 1024, ticket.size - total + 1)):
                total += len(chunk)
                if total > ticket.size:
                    raise ValidationError("Размер загруженного файла изменился.")
                upload.write(chunk)
            if total != ticket.size:
                raise ValidationError("Файл загружен не полностью.")
        finally:
            stream.close()
        upload.seek(0)
        validate_upload(upload)
        return upload
    except (BotoCoreError, ClientError):
        upload.close()
        raise ValidationError("Файл ещё не загружен или хранилище недоступно.") from None
    except Exception:
        upload.close()
        raise


def consume_uploads(body, request):
    if not settings.DIRECT_UPLOADS_ENABLED:
        raise ValidationError("Прямая загрузка не настроена.")
    if (
        not isinstance(body, dict)
        or set(body) != {"data", "tickets"}
        or not isinstance(body["data"], dict)
        or not all(isinstance(v, str) for v in body["data"].values())
        or not isinstance(body["tickets"], list)
        or not 1 <= len(body["tickets"]) <= 5
    ):
        raise ValidationError("Недопустимый запрос загрузки.")
    ids = [serializers.UUIDField().run_validation(value) for value in body["tickets"]]
    if len(set(ids)) != len(ids):
        raise ValidationError("Файл указан повторно.")
    files = MultiValueDict()
    try:
        with transaction.atomic():
            rows = list(UploadTicket.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
            if len(rows) != len(ids) or any(
                row.owner_id != request.user.pk
                or row.target != request.path
                or row.method != request.method
                or row.context_digest != context_digest(body["data"])
                or row.expires_at <= timezone.now()
                or row.consumed
                for row in rows
            ):
                raise ValidationError("Разрешение загрузки недействительно или уже использовано.")
            by_id = {row.pk: row for row in rows}
            for pk in ids:
                row = by_id[pk]
                files.appendlist(row.field, load_file(row))
                row.consumed = True
                row.save(update_fields=["consumed", "updated_at"])
    except Exception:
        for values in files.lists():
            for file in values[1]:
                file.close()
        raise
    # Django closes multipart uploads through HttpRequest.close(). Our custom
    # JSON media type must register its temporary files with the same lifecycle.
    request._request._files = files
    data = QueryDict("", mutable=True)
    data.update(body["data"])
    return DataAndFiles(data, files)


def cleanup_uploads():
    if not settings.DIRECT_UPLOADS_ENABLED:
        return
    client, bucket = storage_client()
    for ticket in UploadTicket.objects.filter(expires_at__lte=timezone.now())[:100]:
        try:
            client.delete_object(Bucket=bucket, Key=ticket.key)
        except (BotoCoreError, ClientError):
            log.warning("quarantine_cleanup_failed")
            continue
        ticket.delete()
