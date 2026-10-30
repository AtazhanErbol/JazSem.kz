"""Gemini REST adapter; keys stay in headers and no automatic replay is used."""

import json
import re
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from django.conf import settings

from .budget import release_budget, reserve_budget, settle_budget
from .configuration import provider_configuration
from .errors import GenerationFailure
from .prompts import COURSE_SYSTEM, TOPIC_SYSTEM
from .schema import CourseDraft, TopicDraft


def response_schema(output_type):
    # Nested maxItems bounds expand Gemini's decoding grammar beyond its state
    # limit. Keep the shape in the API schema; enforce all bounds with Pydantic
    # after generation, before any draft can be stored or imported.
    def simplify(value):
        if isinstance(value, dict):
            return {key: simplify(item) for key, item in value.items() if key != "maxItems"}
        if isinstance(value, list):
            return [simplify(item) for item in value]
        return value

    return simplify(output_type.model_json_schema())


def rejection_code(error):
    if error.code not in {400, 401, 403, 404, 422, 429}:
        return None
    try:
        details = json.loads(error.read(65536)).get("error", {})
        reasons = {item.get("reason") for item in details.get("details", [])}
    except (ValueError, AttributeError, TypeError):
        reasons = set()
    if reasons & {"API_KEY_INVALID", "API_KEY_EXPIRED", "API_KEY_REVOKED"}:
        return "AI_AUTH_FAILED"
    if "SERVICE_DISABLED" in reasons:
        return "AI_SERVICE_DISABLED"
    if reasons & {"BILLING_DISABLED", "BILLING_NOT_ACTIVE"}:
        return "AI_BILLING_REQUIRED"
    return {
        400: "AI_REQUEST_REJECTED",
        401: "AI_AUTH_FAILED",
        403: "AI_ACCESS_DENIED",
        404: "AI_MODEL_UNAVAILABLE",
        422: "AI_REQUEST_REJECTED",
        429: "AI_PROVIDER_QUOTA_EXHAUSTED",
    }[error.code]


class GeminiProvider:
    def generate_lecture(self, chunks, parameters):
        from .lectures import LECTURE_SYSTEM, lecture_output_type

        return self._parse(
            {"settings": parameters, "sources": chunks},
            lecture_output_type(parameters),
            settings.AI_LECTURE_OUTPUT_TOKENS,
            LECTURE_SYSTEM,
        )

    def _parse(self, payload, output_type, output_limit, system):
        config = provider_configuration()
        if config.name != "gemini" or not config.configured:
            raise GenerationFailure("AI_NOT_CONFIGURED", "Gemini provider is not configured")
        # Model names must never turn the fixed provider URL into an arbitrary URL.
        if not re.fullmatch(r"[a-zA-Z0-9._-]+", config.model):
            raise GenerationFailure("AI_NOT_CONFIGURED", "Invalid Gemini model name")
        if settings.GEMINI_THINKING_LEVEL not in {"minimal", "low", "medium", "high"}:
            raise GenerationFailure("AI_NOT_CONFIGURED", "Invalid Gemini thinking level")
        schema = response_schema(output_type)
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [
                {"role": "user", "parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}
            ],
            "generationConfig": {
                "candidateCount": 1,
                "maxOutputTokens": output_limit,
                "thinkingConfig": {"thinkingLevel": settings.GEMINI_THINKING_LEVEL},
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
            },
        }
        if not config.limits_enabled:
            # Omitting this field uses Google's model output limit. Keep the
            # configured value only as an estimate for pending usage accounting.
            body["generationConfig"].pop("maxOutputTokens")
        request = Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{config.model}:generateContent",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"x-goog-api-key": config.api_key, "Content-Type": "application/json"},
            method="POST",
        )
        reservation = reserve_budget(payload, schema, output_limit)
        try:
            with urlopen(request, timeout=None) as response:
                result = json.load(response)
        except HTTPError as error:
            code = rejection_code(error)
            if code is None:
                raise
            release_budget(reservation)
            raise GenerationFailure(code) from None

        metadata = result.get("usageMetadata")
        usage = None
        if metadata is not None:
            usage = SimpleNamespace(
                input_tokens=int(metadata.get("promptTokenCount", 0)),
                output_tokens=int(metadata.get("candidatesTokenCount", 0))
                + int(metadata.get("thoughtsTokenCount", 0)),
            )
            settle_budget(reservation, usage)
        candidates = result.get("candidates", [])
        if len(candidates) != 1:
            code = (
                "AI_CONTENT_BLOCKED"
                if result.get("promptFeedback", {}).get("blockReason")
                else "AI_OUTPUT_INCOMPLETE"
            )
            raise GenerationFailure(code, usage=usage)
        candidate = candidates[0]
        finish = candidate.get("finishReason")
        if finish != "STOP":
            code = "AI_OUTPUT_LIMIT" if finish == "MAX_TOKENS" else "AI_OUTPUT_INCOMPLETE"
            if finish in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}:
                code = "AI_CONTENT_BLOCKED"
            raise GenerationFailure(code, usage=usage)
        text = "".join(
            part.get("text", "")
            for part in candidate.get("content", {}).get("parts", [])
            if not part.get("thought", False)
        )
        try:
            draft = output_type.model_validate_json(text)
        except ValueError:
            raise GenerationFailure("OUTPUT_VALIDATION_FAILED", usage=usage) from None
        return draft, usage

    def generate_course(self, chunks, parameters):
        return self._parse(
            {"settings": parameters, "sources": chunks},
            CourseDraft,
            settings.AI_MAX_OUTPUT_TOKENS,
            COURSE_SYSTEM,
        )

    def regenerate_topic(self, chunks, topic, instruction):
        return self._parse(
            {"sources": chunks, "topic": topic, "instruction": instruction},
            TopicDraft,
            settings.AI_REGENERATE_OUTPUT_TOKENS,
            TOPIC_SYSTEM,
        )
