import json
from typing import Protocol

from django.conf import settings
from openai import APIStatusError, OpenAI

from .budget import release_budget, reserve_budget, settle_budget
from .errors import GenerationFailure, rejected_request
from .prompts import COURSE_SYSTEM, TOPIC_SYSTEM
from .schema import CourseDraft, TopicDraft


class AIProvider(Protocol):
    def generate_course(self, chunks: list[dict], parameters: dict): ...
    def regenerate_topic(self, chunks: list[dict], topic: dict, instruction: str): ...
    def generate_lecture(self, chunks: list[dict], parameters: dict): ...


class OpenAIProvider:
    def generate_lecture(self, chunks, parameters):
        from .lectures import LECTURE_SYSTEM, lecture_output_type

        if not settings.OPENAI_API_KEY or not settings.OPENAI_MODEL:
            raise GenerationFailure("AI_NOT_CONFIGURED")
        output = lecture_output_type(parameters)
        payload = {"settings": parameters, "sources": chunks}
        limit = settings.AI_LECTURE_OUTPUT_TOKENS
        reservation = reserve_budget(payload, output.model_json_schema(), limit)
        return self._parse(
            reservation,
            model=settings.OPENAI_MODEL,
            store=False,
            max_output_tokens=limit,
            reasoning={"effort": settings.OPENAI_REASONING_EFFORT},
            text_format=output,
            input=[
                {"role": "system", "content": LECTURE_SYSTEM},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )

    def _parse(self, reservation, **request):
        try:
            response = OpenAI(
                api_key=settings.OPENAI_API_KEY, timeout=None, max_retries=0
            ).responses.parse(**request)
        except APIStatusError as error:
            failure = rejected_request(error)
            if failure is None:
                raise
            release_budget(reservation)
            raise failure from None
        # Even a truncated/refused response may have confirmed billable usage.
        usage = getattr(response, "usage", None)
        if usage is not None:
            settle_budget(reservation, usage)
        if response.output_parsed is None:
            details = getattr(response, "incomplete_details", None)
            code = (
                "AI_OUTPUT_LIMIT"
                if getattr(details, "reason", None) == "max_output_tokens"
                else "AI_OUTPUT_INCOMPLETE"
            )
            raise GenerationFailure(code, usage=usage)
        return response.output_parsed, usage

    def regenerate_topic(self, chunks, topic, instruction):
        if not settings.OPENAI_API_KEY or not settings.OPENAI_MODEL:
            raise GenerationFailure("AI_NOT_CONFIGURED", "AI provider is not configured")
        payload = {"sources": chunks, "topic": topic, "instruction": instruction}
        reservation = reserve_budget(
            payload, TopicDraft.model_json_schema(), settings.AI_REGENERATE_OUTPUT_TOKENS
        )
        return self._parse(
            reservation,
            model=settings.OPENAI_MODEL,
            store=False,
            max_output_tokens=settings.AI_REGENERATE_OUTPUT_TOKENS,
            reasoning={"effort": settings.OPENAI_REASONING_EFFORT},
            text_format=TopicDraft,
            input=[
                {
                    "role": "system",
                    "content": TOPIC_SYSTEM,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"sources": chunks, "topic": topic, "instruction": instruction},
                        ensure_ascii=False,
                    ),
                },
            ],
        )

    def generate_course(self, chunks, parameters):
        if not settings.OPENAI_API_KEY or not settings.OPENAI_MODEL:
            raise GenerationFailure("AI_NOT_CONFIGURED", "AI provider is not configured")
        reservation = reserve_budget(
            {"settings": parameters, "sources": chunks},
            CourseDraft.model_json_schema(),
            settings.AI_MAX_OUTPUT_TOKENS,
        )
        return self._parse(
            reservation,
            model=settings.OPENAI_MODEL,
            store=False,
            max_output_tokens=settings.AI_MAX_OUTPUT_TOKENS,
            reasoning={"effort": settings.OPENAI_REASONING_EFFORT},
            input=[
                {
                    "role": "system",
                    "content": COURSE_SYSTEM,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"settings": parameters, "sources": chunks}, ensure_ascii=False
                    ),
                },
            ],
            text_format=CourseDraft,
        )
