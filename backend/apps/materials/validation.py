import zipfile
from pathlib import Path

from django.conf import settings
from PIL import Image
from rest_framework.exceptions import ValidationError

MIMES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def validate_upload(file):
    suffix = Path(file.name).suffix.lower()
    if suffix not in MIMES or not 0 < file.size <= settings.MAX_UPLOAD_BYTES:
        raise ValidationError("Недопустимый тип или размер файла.")
    if file.content_type != MIMES[suffix]:
        raise ValidationError("MIME не соответствует расширению файла.")
    try:
        head = file.read(8)
        file.seek(0)
        if suffix == ".pdf" and not head.startswith(b"%PDF-"):
            raise ValueError()
        if suffix in [".png", ".jpg", ".jpeg"]:
            image = Image.open(file)
            if image.format != ("PNG" if suffix == ".png" else "JPEG"):
                raise ValueError()
            image.verify()
        if suffix in [".docx", ".pptx"]:
            with zipfile.ZipFile(file) as archive:
                if sum(i.file_size for i in archive.infolist()) > settings.MAX_UPLOAD_BYTES * 10:
                    raise ValueError()
                marker = "word/document.xml" if suffix == ".docx" else "ppt/presentation.xml"
                if marker not in archive.namelist() or any(
                    "vbaProject" in name for name in archive.namelist()
                ):
                    raise ValueError()
        if suffix == ".txt":
            text = file.read().decode("utf-8")
            if "\x00" in text:
                raise ValueError()
    except Exception:
        raise ValidationError("Содержимое файла не соответствует заявленному формату.")
    finally:
        file.seek(0)
    return file
