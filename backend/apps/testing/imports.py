"""Bounded XLSX template import. No external services or formula evaluation."""

import io

import xlsxwriter
from rest_framework.exceptions import ValidationError

from apps.common.xlsx import read_rows

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
    rows = read_rows(upload, HEADERS)
    questions, errors = [], []
    for number, values in rows:
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
