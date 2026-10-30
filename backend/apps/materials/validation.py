import unicodedata
import zipfile
from pathlib import Path

from django.conf import settings
from PIL import Image
from rest_framework.exceptions import ValidationError

MIMES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".doc": "application/msword",
    ".ppt": "application/vnd.ms-powerpoint",
    ".xls": "application/vnd.ms-excel",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".odp": "application/vnd.oasis.opendocument.presentation",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
}
VIDEO_MIMES = {".mp4": "video/mp4", ".webm": "video/webm"}
ZIP_MARKERS = {
    ".docx": "word/document.xml",
    ".pptx": "ppt/presentation.xml",
    ".xlsx": "xl/workbook.xml",
    ".odt": "content.xml",
    ".odp": "content.xml",
    ".ods": "content.xml",
}


def validate_metadata(name, mime, size, *, allow_video=False):
    suffix = Path(name).suffix.lower()
    if suffix in {".mov", ".qt"}:
        raise ValidationError(
            "MOV не поддерживается для встроенного просмотра. Экспортируйте видео в MP4 (H.264) или WebM."
        )
    types = MIMES | VIDEO_MIMES if allow_video else MIMES
    limit = settings.MAX_VIDEO_UPLOAD_BYTES if suffix in VIDEO_MIMES else settings.MAX_UPLOAD_BYTES
    if (
        not name
        or len(name) > 255
        or "/" in name
        or "\\" in name
        or any(unicodedata.category(char).startswith("C") for char in name)
        or suffix not in types
        or mime != types.get(suffix)
        or not 0 < size <= limit
    ):
        raise ValidationError("Недопустимое имя, тип или размер файла.")
    return suffix


def validate_upload(file, *, allow_video=False):
    suffix = validate_metadata(file.name, file.content_type, file.size, allow_video=allow_video)
    try:
        head = file.read(65536)
        file.seek(0)
        if suffix == ".pdf" and not head.startswith(b"%PDF-"):
            raise ValueError()
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            image = Image.open(file)
            expected = {
                ".png": "PNG",
                ".jpg": "JPEG",
                ".jpeg": "JPEG",
                ".webp": "WEBP",
                ".gif": "GIF",
            }
            if image.format != expected[suffix] or image.width * image.height > 20_000_000:
                raise ValueError()
            image.verify()
        if suffix in ZIP_MARKERS:
            with zipfile.ZipFile(file) as archive:
                entries = archive.infolist()
                if (
                    len(entries) > 2000
                    or sum(i.file_size for i in entries) > settings.MAX_UPLOAD_BYTES * 10
                    or any(i.flag_bits & 1 for i in entries)
                    or ZIP_MARKERS[suffix] not in archive.namelist()
                    or any(
                        "vbaproject" in n.lower() or n.lower().endswith(".exe")
                        for n in archive.namelist()
                    )
                ):
                    raise ValueError()
                if (
                    suffix in {".odt", ".odp", ".ods"}
                    and archive.read("mimetype").decode() != MIMES[suffix]
                ):
                    raise ValueError()
        if suffix in {".doc", ".ppt", ".xls"}:
            from olefile import DEFECT_INCORRECT, OleFileIO

            file.seek(0)
            markers = {
                ".doc": ["WordDocument"],
                ".ppt": ["PowerPoint Document"],
                ".xls": ["Workbook", "Book"],
            }
            # Parse the compound-file directory/FAT rather than scanning arbitrary
            # byte ranges: valid legacy Office streams need not be contiguous.
            with OleFileIO(file, raise_defects=DEFECT_INCORRECT) as archive:
                entries = archive.listdir(streams=True, storages=True)
                if len(entries) > 2000 or not any(
                    archive.exists(marker) for marker in markers[suffix]
                ):
                    raise ValueError()
                if any(
                    part.casefold() in {"vba", "macros", "_vba_project"}
                    for path in entries
                    for part in path
                ):
                    raise ValueError()
        if suffix in {".txt", ".csv"}:
            file.seek(0)
            if "\x00" in file.read().decode("utf-8-sig"):
                raise ValueError()
        if suffix == ".mp4":
            if len(head) < 20 or head[4:8] != b"ftyp":
                raise ValueError()
            box_size = int.from_bytes(head[:4], "big")
            if not 16 <= box_size <= min(len(head), 4096):
                raise ValueError()
            brands = [head[8:12], *[head[i : i + 4] for i in range(16, box_size, 4)]]
            if b"qt  " in brands or not set(brands) & {
                b"isom",
                b"iso2",
                b"mp41",
                b"mp42",
                b"avc1",
                b"dash",
                b"M4V ",
            }:
                raise ValueError()
        if suffix == ".webm" and (
            not head.startswith(b"\x1aE\xdf\xa3") or b"\x42\x82\x84webm" not in head[:4096]
        ):
            raise ValueError()
    except Exception:
        raise ValidationError("Содержимое файла не соответствует заявленному формату.") from None
    finally:
        file.seek(0)
    return file
