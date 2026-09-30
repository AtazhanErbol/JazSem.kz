import io
import time
import zipfile
from contextlib import ExitStack, closing
from pathlib import Path

from django.conf import settings
from PIL import Image

MAX_PAGES = 300
MAX_PIXELS = 20_000_000
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024


def bounded_text(parts):
    output, size = [], 0
    for part in parts:
        size += len(part) + 1
        if size > settings.AI_MAX_SOURCE_CHARS * 5:
            raise ValueError("Text limit exceeded")
        output.append(part)
    return "\n".join(output)


def validate_archive(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > 2000 or sum(e.file_size for e in entries) > MAX_ARCHIVE_BYTES:
            raise ValueError("Archive expansion limit")
        if any(e.flag_bits & 1 for e in entries):
            raise ValueError("Encrypted archive")


def extract_pages(data, filename):
    suffix = Path(filename).suffix.lower()
    started = time.monotonic()
    if suffix == ".txt":
        yield 1, bounded_text([data.decode("utf-8")])
    elif suffix == ".docx":
        from docx import Document

        validate_archive(data)
        document = Document(io.BytesIO(data))

        def parts():
            for paragraph in document.paragraphs:
                yield paragraph.text
            for table in document.tables:
                for row in table.rows:
                    for cell in row.cells:
                        yield cell.text

        # DOCX has no fixed pages; citations refer to the document section.
        yield 1, bounded_text(parts())
    elif suffix == ".pptx":
        from pptx import Presentation

        validate_archive(data)
        slides = Presentation(io.BytesIO(data)).slides
        if len(slides) > MAX_PAGES:
            raise ValueError("Slide limit")
        for number, slide in enumerate(slides, 1):
            yield number, bounded_text(shape.text for shape in slide.shapes if shape.has_text_frame)
    elif suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted or not 0 < len(reader.pages) <= MAX_PAGES:
            raise ValueError("Encrypted, empty or oversized PDF")
        with ExitStack() as stack:
            pdf = None
            for index, page in enumerate(reader.pages):
                if time.monotonic() - started > 420:
                    raise ValueError("Extraction deadline")
                text = bounded_text([page.extract_text() or ""])
                if len(text.strip()) < 40:
                    import pypdfium2 as pdfium
                    import pytesseract

                    if pdf is None:
                        pdf = stack.enter_context(pdfium.PdfDocument(data))
                    with closing(pdf[index]) as rendered_page:
                        width, height = rendered_page.get_size()
                        if width <= 0 or height <= 0 or width * height * 4 > MAX_PIXELS:
                            raise ValueError("Rendered page pixel limit")
                        with closing(rendered_page.render(scale=2)) as bitmap:
                            with bitmap.to_pil() as image:
                                text = pytesseract.image_to_string(
                                    image, lang=settings.OCR_LANGUAGES, timeout=60
                                )
                yield index + 1, bounded_text([text])
    elif suffix in [".png", ".jpg", ".jpeg"]:
        import pytesseract

        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > MAX_PIXELS or getattr(image, "n_frames", 1) != 1:
                raise ValueError("Image pixel/frame limit")
            yield (
                1,
                bounded_text(
                    [pytesseract.image_to_string(image, lang=settings.OCR_LANGUAGES, timeout=60)]
                ),
            )
    else:
        raise ValueError("Unsupported source")
