import io

import pytest
import xlsxwriter
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import ValidationError

from apps.courses.services import duplicate
from apps.testing.imports import HEADERS, read_questions, template


def file(data=None):
    return SimpleUploadedFile("test.xlsx", template() if data is None else data)


def test_template_roundtrip():
    rows = read_questions(file())
    assert rows[0]["correct"] == ["C"] and len(rows[0]["options"]) == 5


def test_append_confirm_and_replay_protection(world, client_for):
    v = duplicate(world["version"], world["teacher"])
    test = v.weeks.first().topics.first().tests.first()
    api = client_for(world["teacher"])
    base = f"/api/v1/tests/{test.pk}/"
    assert api.get(base + "import-template/").status_code == 200
    before = test.questions.count()
    response = api.post(base + "import-preview/", {"file": file()}, format="multipart")
    assert response.status_code == 200
    assert test.questions.count() == before
    token = response.data["token"]
    response = api.post(base + "import-questions/", {"token": token}, format="json")
    assert response.status_code == 200 and test.questions.count() == before + 1
    assert api.post(base + "import-questions/", {"token": token}, format="json").status_code == 400
    assert (
        api.post(base + "import-questions/", {"token": token + "bad"}, format="json").status_code
        == 400
    )


@pytest.mark.parametrize("role", ["student", "other"])
def test_permission(world, client_for, role):
    v = duplicate(world["version"], world["teacher"])
    test = v.weeks.first().topics.first().tests.first()
    assert client_for(world[role]).post(
        f"/api/v1/tests/{test.pk}/import-preview/", {"file": file()}, format="multipart"
    ).status_code in [403, 404]


def test_published_rejected(world, client_for):
    assert (
        client_for(world["teacher"])
        .post(
            f"/api/v1/tests/{world['test'].pk}/import-preview/",
            {"file": file()},
            format="multipart",
        )
        .status_code
        == 400
    )


@pytest.mark.parametrize("answer,score", [("F", 1), ("A,A", 1), ("A", 0), ("A", 1.5)])
def test_bad_rows(answer, score):
    stream = io.BytesIO()
    with xlsxwriter.Workbook(stream, {"in_memory": True}) as b:
        s = b.add_worksheet()
        s.write_row(0, 0, HEADERS)
        s.write_row(1, 0, ["Question", "a", "b", "", "", "", answer, score, ""])
    with pytest.raises(ValidationError):
        read_questions(file(stream.getvalue()))


def test_multiple_answers():
    stream = io.BytesIO()
    with xlsxwriter.Workbook(stream, {"in_memory": True}) as b:
        s = b.add_worksheet()
        s.write_row(0, 0, HEADERS)
        s.write_row(1, 0, ["Question", "a", "b", "c", "", "", "A,C", 2, ""])
    assert read_questions(file(stream.getvalue()))[0]["correct"] == ["A", "C"]


def test_invalid_file():
    with pytest.raises(ValidationError):
        read_questions(file(b"not a spreadsheet"))
