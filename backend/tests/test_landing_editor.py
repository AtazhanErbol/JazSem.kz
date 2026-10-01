import pytest
from rest_framework.test import APIClient

from apps.cms.models import ContentBlock

pytestmark = pytest.mark.django_db


def test_draft_publish_and_language_isolation(world, client_for):
    admin = client_for(world["admin"])
    public = APIClient()
    data = {
        "language": "ru",
        "texts": {
            "heroTitle": "Новый заголовок",
            "learningTitle": "Учебные недели",
            "manualTitle": "Мой способ",
        },
        "hidden": ["faq", "creation"],
        "image": "",
    }
    assert admin.post("/api/v1/landing/", data, format="json").status_code == 200
    assert public.get("/api/v1/landing/?language=ru").data["texts"] == {}
    assert admin.get("/api/v1/landing/?language=ru&draft=1").data["texts"] == data["texts"]
    assert (
        admin.post("/api/v1/landing/", {**data, "publish": True}, format="json").status_code == 200
    )
    assert public.get("/api/v1/landing/?language=ru").data["texts"] == data["texts"]
    assert public.get("/api/v1/landing/?language=kk").data["texts"] == {}
    data["texts"] = {"heroTitle": "Следующий черновик"}
    admin.post("/api/v1/landing/", data, format="json")
    assert (
        public.get("/api/v1/landing/?language=ru").data["texts"]["heroTitle"] == "Новый заголовок"
    )
    assert not public.get("/api/v1/public-content/").data["results"]
    assert not admin.get("/api/v1/content/").data["results"]


@pytest.mark.parametrize("role", ["teacher", "student"])
def test_landing_admin_only(world, client_for, role):
    client = client_for(world[role])
    assert client.get("/api/v1/landing/?draft=1").status_code == 403
    assert client.post("/api/v1/landing/", {"language": "ru"}, format="json").status_code == 403
    assert client.get("/api/v1/landing/").status_code == 200


def test_landing_anonymous_and_reserved_keys(world, client_for):
    public = APIClient()
    assert public.get("/api/v1/landing/?draft=1").status_code == 403
    assert public.post("/api/v1/landing/", {"language": "ru"}, format="json").status_code == 403
    admin = client_for(world["admin"])
    assert (
        admin.post(
            "/api/v1/content/",
            {
                "key": "__landing_live",
                "title": "bad",
                "language": "ru",
                "body": "{}",
                "is_published": True,
            },
            format="json",
        ).status_code
        == 403
    )
    block = ContentBlock.objects.create(
        key="__landing_live", title="reserved", language="ru", body="{}", is_published=True
    )
    assert public.get(f"/api/v1/public-content/{block.pk}/").status_code == 404
    assert admin.delete(f"/api/v1/content/{block.pk}/").status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"language": "xx"},
        {"language": "ru", "texts": {"unknown": "x"}},
        {"language": "ru", "hidden": ["hero"]},
        {"language": "ru", "image": "javascript:alert(1)"},
        {"language": "ru", "image": "http://example.test/image.png"},
        {"language": "ru", "extra": 1},
    ],
)
def test_landing_validation(world, client_for, payload):
    assert (
        client_for(world["admin"]).post("/api/v1/landing/", payload, format="json").status_code
        == 400
    )
