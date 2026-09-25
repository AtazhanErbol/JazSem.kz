import io
from pathlib import Path

from django.conf import settings
from PIL import Image


def extract_pages(data, filename):
    suffix = Path(filename).suffix.lower()
    if suffix == ".txt":
        yield 1, data.decode("utf-8")
    elif suffix == ".docx":
        from docx import Document

        document = Document(io.BytesIO(data))
        # DOCX has no stable pagination: locator is the document section.
        yield (
            1,
            "\n".join(
                [p.text for p in document.paragraphs]
                + [
                    " | ".join(c.text for c in row.cells)
                    for table in document.tables
                    for row in table.rows
                ]
            ),
        )
    elif suffix == ".pptx":
        from pptx import Presentation

        for number, slide in enumerate(Presentation(io.BytesIO(data)).slides, 1):
            yield number, "\n".join(shape.text for shape in slide.shapes if shape.has_text_frame)
    elif suffix == ".pdf":
        from pypdf import PdfReader

        pages = PdfReader(io.BytesIO(data)).pages
        if len(pages) > 300:
            raise ValueError("PDF exceeds 300 pages")
        for index, page in enumerate(pages):
            text = page.extract_text() or ""
            if len(text.strip()) < 40:
                import pypdfium2 as pdfium
                import pytesseract

                with pdfium.PdfDocument(data) as pdf:
                    bitmap = pdf[index].render(scale=2)
                    text = pytesseract.image_to_string(
                        bitmap.to_pil(), lang=settings.OCR_LANGUAGES, timeout=60
                    )
            yield index + 1, text
    else:
        import pytesseract

        yield (
            1,
            pytesseract.image_to_string(
                Image.open(io.BytesIO(data)), lang=settings.OCR_LANGUAGES, timeout=60
            ),
        )
