"""Size-limited XLSX text reader; formulas and macros are rejected."""

import re
from zipfile import BadZipFile, ZipFile

from lxml import etree
from rest_framework.exceptions import ValidationError

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def read_rows(upload, headers):
    if not upload or not upload.name.lower().endswith(".xlsx") or upload.size > 2 * 1024 * 1024:
        raise ValidationError("Загрузите файл .xlsx размером до 2 МБ по шаблону.")
    try:
        with ZipFile(upload) as archive:
            infos = archive.infolist()
            if len(infos) > 100 or sum(i.file_size for i in infos) > 10 * 1024 * 1024:
                raise ValueError()
            if any("vbaProject" in i.filename for i in infos):
                raise ValueError()

            def xml(name):
                data = archive.read(name)
                if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
                    raise ValueError()
                return etree.fromstring(
                    data, etree.XMLParser(resolve_entities=False, no_network=True)
                )

            shared = []
            if "xl/sharedStrings.xml" in archive.namelist():
                shared = [
                    "".join(si.itertext()) for si in xml("xl/sharedStrings.xml").findall("m:si", NS)
                ]
            rows = []
            for row in xml("xl/worksheets/sheet1.xml").findall("m:sheetData/m:row", NS):
                values = [""] * len(headers)
                for cell in row.findall("m:c", NS):
                    if cell.find("m:f", NS) is not None:
                        raise ValidationError(
                            f"Строка {row.get('r')}: замените формулы обычным текстом."
                        )
                    ref = cell.get("r", "")
                    column = re.match(r"([A-Z]+)", ref)
                    if (
                        not column
                        or column[1] not in "ABCDEFGHI"[: len(headers)]
                        or len(column[1]) != 1
                    ):
                        continue
                    value = cell.findtext("m:v", default="", namespaces=NS)
                    if cell.get("t") == "s":
                        value = shared[int(value)]
                    if cell.get("t") == "inlineStr":
                        value = "".join(cell.find("m:is", NS).itertext())
                    if len(value) > 10000:
                        raise ValueError()
                    values[ord(column[1]) - 65] = value.strip()
                if any(values):
                    rows.append((row.get("r"), values))
                if len(rows) > 201:
                    raise ValidationError("Не более 200 строк в одном файле.")
    except ValidationError:
        raise
    except (
        RuntimeError,
        NotImplementedError,
        BadZipFile,
        KeyError,
        ValueError,
        IndexError,
        AttributeError,
        etree.XMLSyntaxError,
        OSError,
    ):
        raise ValidationError(
            "Не удалось прочитать Excel. Скачайте шаблон и сохраните файл как .xlsx."
        ) from None
    if not rows or rows[0][1] != headers:
        raise ValidationError("Заголовки первого листа должны совпадать с шаблоном.")
    return rows[1:]
