"""Bounded XLSX template import. No external services or formula evaluation."""

import io
import re
from zipfile import BadZipFile, ZipFile

import xlsxwriter
from lxml import etree
from rest_framework.exceptions import ValidationError

HEADERS = [
    "Вопрос",
    "Вариант A",
    "Вариант B",
    "Вариант C",
    "Вариант D",
    "Вариант E",
    "Правильный ответ",
    "Баллы",
    "Пояснение",
]
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def template():
    output = io.BytesIO()
    with xlsxwriter.Workbook(
        output, {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False}
    ) as book:
        sheet = book.add_worksheet("Тест")
        header = book.add_format({"bold": True, "bg_color": "#FDECEF", "text_wrap": True})
        sheet.write_row(0, 0, HEADERS, header)
        sheet.write_row(
            1, 0, ["Сколько будет 2 + 2?", "2", "3", "4", "5", "6", "C", 1, "2 + 2 = 4"]
        )
        sheet.freeze_panes(1, 1)
        sheet.set_column(0, 0, 50)
        sheet.set_column(1, 5, 24)
        sheet.set_column(6, 8, 24)
        help_sheet = book.add_worksheet("Инструкция")
        for i, text in enumerate(
            [
                "Замените пример своими вопросами на листе Тест.",
                "До 200 вопросов, от 2 до 5 вариантов; A и B обязательны. Не оставляйте пропуски между вариантами.",
                "Правильный ответ: A или несколько букв через запятую, например A,C.",
                "Баллы: целое число от 1 до 100. Пояснение необязательно.",
                "Сохраняйте заголовки. Формулы, макросы и старый формат .xls не поддерживаются.",
                "Импорт добавляет вопросы в черновик после предпросмотра, существующие вопросы остаются.",
            ]
        ):
            help_sheet.write_string(i, 0, text)
        help_sheet.set_column(0, 0, 125)
    return output.getvalue()


def read_questions(upload):
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
                values = [""] * 9
                for cell in row.findall("m:c", NS):
                    if cell.find("m:f", NS) is not None:
                        raise ValidationError(
                            f"Строка {row.get('r')}: замените формулы обычным текстом."
                        )
                    ref = cell.get("r", "")
                    column = re.match(r"([A-Z]+)", ref)
                    if not column or column[1] not in "ABCDEFGHI" or len(column[1]) != 1:
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
                    raise ValidationError("Не более 200 вопросов в одном файле.")
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
    if not rows or rows[0][1] != HEADERS:
        raise ValidationError("Заголовки первого листа должны совпадать с шаблоном.")
    questions, errors = [], []
    for number, values in rows[1:]:
        text, *rest = values
        options, answer, score, explanation = rest[:5], rest[5], rest[6], rest[7]
        used = [v for v in options if v]
        correct = [v.strip() for v in answer.upper().split(",")]
        if not text or len(used) < 2 or options[: len(used)] != used or len(set(used)) != len(used):
            errors.append(
                f"Строка {number}: нужны вопрос и от 2 до 5 разных вариантов без пропусков."
            )
            continue
        if (
            not correct
            or len(set(correct)) != len(correct)
            or any(c not in list("ABCDE"[: len(used)]) for c in correct)
        ):
            errors.append(f"Строка {number}: укажите правильные ответы буквами A–E через запятую.")
            continue
        try:
            points = int(score)
            if not 1 <= points <= 100:
                raise ValueError()
        except ValueError:
            errors.append(f"Строка {number}: баллы должны быть целым числом от 1 до 100.")
            continue
        questions.append(
            {
                "text": text,
                "options": used,
                "correct": correct,
                "score": points,
                "explanation": explanation,
            }
        )
    if errors:
        raise ValidationError(errors[:20])
    if not questions:
        raise ValidationError("В файле нет вопросов.")
    return questions
