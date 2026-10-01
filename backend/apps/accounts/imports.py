import io

import xlsxwriter
from rest_framework.exceptions import ValidationError

from apps.common.permissions import is_admin
from apps.common.xlsx import read_rows

from .models import User
from .serializers import UserSerializer

HEADERS = ["Email", "Имя", "Фамилия", "Роль", "Язык", "Email преподавателя"]


def template():
    output = io.BytesIO()
    with xlsxwriter.Workbook(
        output, {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False}
    ) as book:
        sheet = book.add_worksheet("Пользователи")
        style = book.add_format({"bold": True, "bg_color": "#FDECEF"})
        sheet.write_row(0, 0, HEADERS, style)
        sheet.set_column(0, 5, 28)
        sheet.freeze_panes(1, 0)
        help_sheet = book.add_worksheet("Инструкция")
        for i, text in enumerate(
            [
                "Заполните первый лист: Email, Имя, Фамилия, Роль, Язык, Email преподавателя.",
                "Роль: Студент или Преподаватель (также STUDENT / TEACHER). Администраторов импортировать нельзя.",
                "Язык: RU или KZ (также KK). Пустое значение означает RU.",
                "Email преподавателя необязателен: укажите существующего активного преподавателя для студента.",
                "У администратора пустое поле оставляет студента нераспределённым; у преподавателя студент закрепляется за ним.",
                "Сначала импортируйте преподавателей, затем студентов, если хотите указать их преподавателей в файле.",
                "До 200 пользователей, файл до 2 МБ. Формулы и макросы не поддерживаются.",
                "Существующие адреса и повторы считаются ошибкой. Исправьте все ошибки перед импортом.",
                "После подтверждения каждому новому пользователю будет поставлено в очередь письмо с временным паролем.",
            ]
        ):
            help_sheet.write_string(i, 0, text)
        help_sheet.set_column(0, 0, 135)
    return output.getvalue()


def read_users(upload, request):
    users, errors, seen = [], [], set()
    for number, values in read_rows(upload, HEADERS):
        email, first, last, role, language, owner = values
        email = email.lower()
        role = {"СТУДЕНТ": "STUDENT", "ПРЕПОДАВАТЕЛЬ": "TEACHER"}.get(role.upper(), role.upper())
        language = language.lower() or "ru"
        if language == "kz":
            language = "kk"
        if role not in ("STUDENT", "TEACHER") or (not is_admin(request.user) and role != "STUDENT"):
            errors.append(
                f"Строка {number}: недоступная роль. Преподаватель может добавлять только студентов."
            )
            continue
        if email in seen or User.objects.filter(email__iexact=email).exists():
            errors.append(f"Строка {number}: email уже существует или повторяется в файле.")
            continue
        seen.add(email)
        teacher = None
        if owner:
            teacher = User.objects.filter(
                email__iexact=owner, role="TEACHER", is_active=True
            ).first()
            if (
                not teacher
                or role != "STUDENT"
                or (not is_admin(request.user) and teacher != request.user)
            ):
                errors.append(f"Строка {number}: проверьте email и доступность преподавателя.")
                continue
        elif role == "STUDENT" and not is_admin(request.user):
            teacher = request.user
        data = dict(
            email=email,
            first_name=first,
            last_name=last,
            role=role,
            preferred_language=language,
            owner_teacher=str(teacher.pk) if teacher else None,
        )
        serializer = UserSerializer(data=data, context={"request": request})
        if not first or not last:
            errors.append(f"Строка {number}: заполните имя и фамилию.")
        elif not serializer.is_valid():
            errors.append(f"Строка {number}: {serializer.errors}")
        else:
            users.append(data)
    if errors:
        raise ValidationError(errors[:20])
    if not users:
        raise ValidationError("В файле нет пользователей.")
    return users
