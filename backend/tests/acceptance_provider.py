"""No-network provider transport for separate-process synthetic acceptance only.

The real OpenAIProvider, budget reservation/settlement and worker state machine
remain active. Only the SDK network boundary is replaced. This app is never in
normal development/production INSTALLED_APPS.
"""

import json
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def control_path(course):
    return Path(settings.ACCEPTANCE_CONTROL_DIR) / (str(course) + ".json")


def mode(course):
    path = control_path(course)
    return json.loads(path.read_text()) if path.exists() else {}


def gate(course, stage):
    folder = Path(settings.ACCEPTANCE_CONTROL_DIR) / "events"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / (uuid.uuid4().hex + ".json")).write_text(
        json.dumps({"course": str(course), "stage": stage, "at": time.time()}), encoding="utf-8"
    )
    deadline = time.monotonic() + 180
    while mode(course).get("gate") == stage:
        if time.monotonic() > deadline:
            raise TimeoutError("Synthetic provider gate timed out")
        time.sleep(0.1)


class SyntheticOpenAI:
    def __init__(self, **kwargs):
        if kwargs.get("api_key") != "synthetic-acceptance-not-a-provider-key":
            raise ImproperlyConfigured("Synthetic provider refuses non-test credentials")
        self.responses = self

    def parse(self, **kwargs):
        from apps.ai.models import SourceDocument

        payload = json.loads(kwargs["input"][-1]["content"])
        chunks = payload["sources"]
        course = SourceDocument.objects.values_list("course_id", flat=True).get(
            pk=chunks[0]["document"]
        )
        gate(course, "provider")
        if mode(course).get("failure") == "timeout":
            raise TimeoutError("Synthetic uncertain provider response")
        references = [chunks[0]["id"]]
        if "topic" in payload:
            data = payload["topic"]
            data["title"] = "Обновлённая тема / Жаңартылған тақырып"
        else:
            parameters = payload["settings"]
            topic = {
                "title": "Тестовая тема / Сынақ тақырыбы",
                "content": "Синтетический учебный материал. Қазақша әріптер: Ә Ғ Қ Ң Ө Ұ Ү Һ І.",
                "source_chunks": references,
                "assignments": [
                    {
                        "title": "Учебное задание",
                        "instructions": "Объясните материал своими словами.",
                        "source_chunks": references,
                    }
                ]
                if parameters["assignments"]
                else [],
                "questions": [
                    {
                        "text": "Сколько будет один плюс один?",
                        "type": "SINGLE_CHOICE",
                        "explanation": "Один плюс один равно двум.",
                        "source_chunks": references,
                        "options": [
                            {"text": "2", "is_correct": True},
                            {"text": "3", "is_correct": False},
                        ],
                    }
                ]
                if parameters["tests"]
                else [],
            }
            data = {
                "title": "Учебный черновик / Оқу жобасы",
                "description": "Synthetic worker acceptance",
                "source_gaps": [],
                "weeks": [
                    {"title": f"Неделя {number + 1}", "topics": [topic]}
                    for number in range(parameters["weeks"])
                ],
            }
        return SimpleNamespace(
            output_parsed=kwargs["text_format"].model_validate(data),
            usage=SimpleNamespace(input_tokens=100, output_tokens=250),
        )


class SyntheticProviderConfig(AppConfig):
    name = "tests"
    label = "acceptance_provider"

    def ready(self):
        if not getattr(settings, "ACCEPTANCE_SYNTHETIC", False) or not str(
            settings.DATABASES["default"]["NAME"]
        ).startswith("jazsem_rc_"):
            raise ImproperlyConfigured(
                "Synthetic provider is restricted to isolated acceptance databases"
            )
        from apps.ai import delivery, provider

        provider.OpenAI = SyntheticOpenAI
        original_claim = delivery.claim

        def claim(*, job=None, source=None):
            lease = original_claim(job=job, source=source)
            if lease and job and mode(job.course_id).get("gate") == "before_provider":
                gate(job.course_id, "before_provider")
            return lease

        delivery.claim = claim
