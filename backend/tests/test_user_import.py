import io

import pytest
import xlsxwriter
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.imports import HEADERS
from apps.accounts.models import User
from apps.notifications.models import MailOutbox

pytestmark = pytest.mark.django_db


def upload(rows):
    data = io.BytesIO()
    with xlsxwriter.Workbook(data, {"in_memory": True}) as book:
        sheet = book.add_worksheet()
        sheet.write_row(0, 0, HEADERS)
        for i, row in enumerate(rows, 1):
            sheet.write_row(i, 0, row)
    return SimpleUploadedFile("users.xlsx", data.getvalue())


def preview(client, rows):
    return client.post("/api/v1/users/import-preview/", {"file": upload(rows)}, format="multipart")


def test_admin_import_and_no_duplicate_invites(world, client_for):
    client = client_for(world["admin"])
    before = MailOutbox.objects.count()
    result = preview(
        client,
        [
            ["new@example.test", "New", "Teacher", "Преподаватель", "KZ", ""],
            ["pupil@example.test", "New", "Student", "Студент", "RU", world["teacher"].email],
        ],
    )
    assert result.status_code == 200, result.data
    assert not User.objects.filter(email="new@example.test").exists()
    assert MailOutbox.objects.count() == before
    token = result.data["token"]
    result = client.post("/api/v1/users/import-users/", {"token": token}, format="json")
    assert result.status_code == 201, result.data
    assert User.objects.get(email="new@example.test").preferred_language == "kk"
    student = User.objects.get(email="pupil@example.test")
    assert student.owner_teacher == world["teacher"]
    assert student.must_change_password
    assert MailOutbox.objects.count() == before + 2
    assert (
        client.post("/api/v1/users/import-users/", {"token": token}, format="json").status_code
        == 400
    )
    assert MailOutbox.objects.count() == before + 2


def test_teacher_scope_and_student_forbidden(world, client_for):
    client = client_for(world["teacher"])
    row = ["new@example.test", "New", "Student", "STUDENT", "ru", ""]
    result = preview(client, [row])
    assert result.status_code == 200
    assert result.data["users"][0]["owner_teacher"] == str(world["teacher"].pk)
    assert (
        client.post(
            "/api/v1/users/import-users/", {"token": result.data["token"]}, format="json"
        ).status_code
        == 201
    )
    assert (
        preview(client, [["teacher2@example.test", "A", "B", "TEACHER", "ru", ""]]).status_code
        == 400
    )
    assert (
        preview(
            client, [["other2@example.test", "A", "B", "STUDENT", "ru", world["other"].email]]
        ).status_code
        == 400
    )
    assert client_for(world["student"]).get("/api/v1/users/import-template/").status_code == 403


@pytest.mark.parametrize(
    "row",
    [
        ["ADMIN@example.test", "A", "B", "STUDENT", "ru", ""],
        ["bad", "A", "B", "STUDENT", "ru", ""],
        ["new@example.test", "A", "B", "ADMIN", "ru", ""],
        ["new@example.test", "A", "B", "STUDENT", "bad", ""],
        ["new@example.test", "=1+1", "B", "STUDENT", "ru", ""],
    ],
)
def test_invalid_rows(world, client_for, row):
    assert preview(client_for(world["admin"]), [row]).status_code == 400


def test_duplicate_rows_and_stale_preview_atomic(world, client_for):
    client = client_for(world["admin"])
    row = ["new@example.test", "A", "B", "STUDENT", "ru", ""]
    assert preview(client, [row, row]).status_code == 400
    result = preview(client, [row, ["later@example.test", "C", "D", "STUDENT", "ru", ""]])
    token = result.data["token"]
    assert (
        client_for(world["teacher"])
        .post("/api/v1/users/import-users/", {"token": token}, format="json")
        .status_code
        == 403
    )
    User.objects.create_user(username="later", email="later@example.test")
    assert (
        client.post("/api/v1/users/import-users/", {"token": token}, format="json").status_code
        == 400
    )
    assert not User.objects.filter(email="new@example.test").exists()
    assert (
        client.post(
            "/api/v1/users/import-users/", {"token": token + "broken"}, format="json"
        ).status_code
        == 400
    )


@pytest.mark.parametrize(
    "language, expected",
    [
        ("каз", "kk"),
        (" ҚАЗ ", "kk"),
        ("Қазақша", "kk"),
        ("казахский", "kk"),
        ("KZ", "kk"),
        ("KK", "kk"),
        ("рус", "ru"),
        ("Русский", "ru"),
        ("", "ru"),
    ],
)
def test_language_aliases(world, client_for, language, expected):
    result = preview(
        client_for(world["admin"]), [["new@example.test", "A", "B", "STUDENT", language, ""]]
    )
    assert result.status_code == 200, result.data
    assert result.data["users"][0]["preferred_language"] == expected


@pytest.mark.parametrize(
    "email, language, label", [("new@example.test", "unknown", "Язык"), ("bad", "каз", "Email")]
)
def test_readable_errors(world, client_for, email, language, label):
    result = preview(client_for(world["admin"]), [[email, "A", "B", "STUDENT", language, ""]])
    assert result.status_code == 400
    message = result.content.decode()
    assert "Строка 2" in message and label in message
    assert "ErrorDetail" not in message and "invalid_choice" not in message
