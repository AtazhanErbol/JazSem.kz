import hashlib
import os
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage

from config.ocr_assets import COMMIT, MODELS, PREFIX


def tessdata_path():
    root = Path(tempfile.gettempdir()) / ("jazsem-tessdata-" + COMMIT)
    root.mkdir(mode=0o700, exist_ok=True)
    for language in settings.OCR_LANGUAGES.split("+"):
        if language not in MODELS:
            raise ValueError("OCR language asset is not configured")
        expected_hash, expected_size = MODELS[language]
        destination = root / f"{language}.traineddata"
        if (
            destination.is_file()
            and hashlib.sha256(destination.read_bytes()).hexdigest() == expected_hash
        ):
            continue
        with default_storage.open(f"{PREFIX}/{language}.traineddata", "rb") as source:
            data = source.read(expected_size + 1)
        if len(data) != expected_size or hashlib.sha256(data).hexdigest() != expected_hash:
            raise ValueError("OCR asset integrity check failed")
        with tempfile.NamedTemporaryFile(dir=root, delete=False) as target:
            temporary = target.name
            target.write(data)
        os.replace(temporary, destination)
    return str(root)


def embedded_ready():
    from tesserocr import PSM, PyTessBaseAPI

    with PyTessBaseAPI(path=tessdata_path(), lang=settings.OCR_LANGUAGES, psm=PSM.AUTO):
        pass


def recognize(image):
    if settings.OCR_ENGINE != "embedded":
        import pytesseract

        return pytesseract.image_to_string(image, lang=settings.OCR_LANGUAGES)
    from tesserocr import PSM, PyTessBaseAPI

    with PyTessBaseAPI(path=tessdata_path(), lang=settings.OCR_LANGUAGES, psm=PSM.AUTO) as api:
        api.SetImage(image)
        if not api.Recognize():
            raise ValueError("OCR recognition failed")
        return api.GetUTF8Text()
