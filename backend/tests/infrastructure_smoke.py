"""Run through manage.py shell on an isolated, seeded CI Compose stack."""

import subprocess
import uuid

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from apps.ai.models import SourceDocument
from apps.ai.tasks import extract_document
from apps.courses.models import Course

assert settings.DEBUG and not settings.AI_ENABLED, "CI smoke requires development and disabled AI"
marker = "ci/" + uuid.uuid4().hex + ".txt"
cache.set(marker, "redis-ok", 30)
assert cache.get(marker) == "redis-ok"
cache.delete(marker)
path = default_storage.save(marker, ContentFile(b"Private object storage round trip"))
try:
    with default_storage.open(path, "rb") as stream:
        assert stream.read() == b"Private object storage round trip"
finally:
    default_storage.delete(path)

course = Course.objects.first()
source = SourceDocument.objects.create(
    course=course,
    uploaded_by=course.teacher,
    filename="ci-source.txt",
    mime_type="text/plain",
    size=34,
    file=ContentFile(b"Linear equation: x + 1 = 2, x = 1.", name="ci-source.txt"),
)
try:
    extract_document.delay(str(source.pk)).get(timeout=60)
    source.refresh_from_db()
    assert source.processing_status == "COMPLETED", source.error
    assert source.chunks.filter(content__contains="x + 1 = 2").exists()
finally:
    source.file.delete(save=False)
    source.delete()

languages = subprocess.check_output(["tesseract", "--list-langs"], text=True).splitlines()
assert {"rus", "kaz", "eng"}.issubset(languages)
print("Redis, private S3, asynchronous Celery extraction and OCR language packs: PASS")
