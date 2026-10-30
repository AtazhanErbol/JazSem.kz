"""Validate immutable S3 ranges and copy objects inside storage, not via Django."""

import io
import uuid
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.common.direct_uploads import context_digest, storage_client
from apps.common.models import UploadTicket

from .validation import VIDEO_MIMES, validate_upload


class RemoteFile(io.RawIOBase):
    block_size = 65536

    def __init__(self, client, bucket, ticket, etag):
        self.client, self.bucket, self.ticket, self.etag = client, bucket, ticket, etag
        self.name, self.content_type, self.size = ticket.filename, ticket.mime_type, ticket.size
        self.position, self.cache = 0, {}

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        position = (
            offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        )
        if whence not in (0, 1, 2) or not 0 <= position <= self.size:
            raise ValueError("Invalid file offset")
        self.position = position
        return position

    def read(self, size=-1):
        remaining = self.size - self.position if size < 0 else min(size, self.size - self.position)
        output = []
        while remaining:
            start = self.position // self.block_size * self.block_size
            if start not in self.cache:
                end = min(self.size, start + self.block_size) - 1
                result = self.client.get_object(
                    Bucket=self.bucket,
                    Key=self.ticket.key,
                    Range=f"bytes={start}-{end}",
                    IfMatch=self.etag,
                )
                body = result["Body"]
                try:
                    chunk = body.read(end - start + 2)
                finally:
                    body.close()
                if len(chunk) != end - start + 1:
                    raise ValueError("Incomplete storage range")
                self.cache[start] = chunk
            offset = self.position - start
            chunk = self.cache[start][offset : offset + remaining]
            if not chunk:
                raise ValueError("Incomplete storage range")
            output.append(chunk)
            self.position += len(chunk)
            remaining -= len(chunk)
        return b"".join(output)


def promote_attachment(ticket_id, request, *, kind):
    """Caller holds a transaction and the parent's version lock."""
    data = {key: value for key, value in request.data.items() if key != "upload_ticket"}
    if not all(isinstance(value, str) for value in data.values()):
        raise ValidationError("Метаданные прямой загрузки должны совпадать с разрешением.")
    ticket = UploadTicket.objects.select_for_update().filter(pk=ticket_id).first()
    if (
        not ticket
        or ticket.owner_id != request.user.pk
        or ticket.target != request.path
        or ticket.method != request.method
        or ticket.consumed
        or ticket.expires_at <= timezone.now()
        or ticket.context_digest != context_digest(data)
        or ticket.field != "file"
    ):
        raise ValidationError("Разрешение загрузки недействительно или уже использовано.")
    if (ticket.mime_type in VIDEO_MIMES.values()) != (kind == "VIDEO"):
        raise ValidationError({"kind": "Тип вложения не соответствует загруженному файлу."})
    client, bucket = storage_client()
    try:
        metadata = client.head_object(Bucket=bucket, Key=ticket.key)
        if metadata["ContentLength"] != ticket.size or metadata["ContentType"] != ticket.mime_type:
            raise ValidationError("Размер или тип загруженного файла изменились.")
        etag = metadata["ETag"]
        with RemoteFile(client, bucket, ticket, etag) as file:
            validate_upload(file, allow_video=True)
        key = f"private/attachments/{uuid.uuid4().hex}{Path(ticket.filename).suffix.lower()}"
        # A changed quarantine object must never replace the bytes we validated.
        client.copy_object(
            Bucket=bucket,
            Key=key,
            CopySource={"Bucket": bucket, "Key": ticket.key},
            CopySourceIfMatch=etag,
            MetadataDirective="REPLACE",
            ContentType=ticket.mime_type,
        )
    except (BotoCoreError, ClientError):
        raise ValidationError(
            "Файл загружен не полностью, изменился или хранилище недоступно."
        ) from None
    ticket.consumed = True
    ticket.save(update_fields=["consumed", "updated_at"])
    return {
        "file": key,
        "original_filename": ticket.filename,
        "mime_type": ticket.mime_type,
        "size": ticket.size,
    }
