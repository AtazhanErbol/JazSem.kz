import io
import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest

from apps.ai.configuration import provider_configuration
from apps.ai.errors import GenerationFailure
from apps.ai.gemini import GeminiProvider
from apps.ai.jobs import create_job
from apps.ai.models import AIBudgetDay, AICourseDraft, AIUsageLog
from apps.ai.schema import validate_citations
from apps.ai.tasks import generate_course
from tests.test_ai_recovery import source
from tests.test_auth_ai import draft_data


def configure(settings):
    settings.AI_PROVIDER = "gemini"
    settings.AI_ENABLED = True
    settings.GEMINI_API_KEY = "gemini-test-only-never-sent"
    settings.GEMINI_MODEL = "gemini-3.1-flash-lite"
    settings.GEMINI_THINKING_LEVEL = "minimal"
    settings.GEMINI_APP_LIMITS_ENABLED = True
    settings.GEMINI_INPUT_PRICE = "0.25"
    settings.GEMINI_OUTPUT_PRICE = "1.50"
    settings.AI_DAILY_BUDGET_USD = "1"


def response(data, finish="STOP", **extra):
    return io.BytesIO(
        json.dumps(
            {
                "candidates": [
                    {
                        "finishReason": finish,
                        "content": {
                            "parts": [
                                {"text": "Never expose reasoning", "thought": True},
                                {"text": json.dumps(data, ensure_ascii=False)},
                            ]
                        },
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 100,
                    "candidatesTokenCount": 200,
                    "thoughtsTokenCount": 50,
                },
                **extra,
            }
        ).encode()
    )


def test_gemini_structured_course_preserves_sources_and_counts_thinking(db, settings):
    configure(settings)
    chunks = [{"id": "source-id", "text": "Мәтін. Текст."}]
    data = draft_data(SimpleNamespace(pk="source-id"))
    with patch("apps.ai.gemini.urlopen", return_value=response(data)) as send:
        draft, usage = GeminiProvider().generate_course(chunks, {"weeks": 1, "language": "kk"})
    validate_citations(draft, {"source-id"})
    assert usage.input_tokens == 100 and usage.output_tokens == 250
    assert AIBudgetDay.objects.get().reserved_usd == Decimal("0.000400")
    request = send.call_args.args[0]
    assert "gemini-3.1-flash-lite:generateContent" in request.full_url
    assert settings.GEMINI_API_KEY not in request.full_url
    assert send.call_args.kwargs["timeout"] is None
    assert send.call_count == 1
    payload = json.loads(request.data)
    prompt = json.loads(payload["contents"][0]["parts"][0]["text"])
    assert prompt["sources"] == chunks
    assert prompt["settings"]["language"] == "kk"
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
    assert payload["generationConfig"]["responseJsonSchema"]["type"] == "object"
    assert payload["generationConfig"]["maxOutputTokens"] == settings.AI_MAX_OUTPUT_TOKENS
    assert payload["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "minimal"}
    assert "untrusted" in payload["systemInstruction"]["parts"][0]["text"]


def test_gemini_topic_regeneration_uses_topic_schema_and_budget(db, settings):
    configure(settings)
    topic = draft_data(SimpleNamespace(pk="source-id"))["weeks"][0]["topics"][0]
    topic["title"] = "Жаңартылған тақырып"
    with patch("apps.ai.gemini.urlopen", return_value=response(topic)) as send:
        updated, _ = GeminiProvider().regenerate_topic([], topic, "Уточни объяснение")
    assert updated.title == "Жаңартылған тақырып"
    payload = json.loads(send.call_args.args[0].data)
    assert payload["generationConfig"]["maxOutputTokens"] == settings.AI_REGENERATE_OUTPUT_TOKENS
    assert "weeks" not in payload["generationConfig"]["responseJsonSchema"]["properties"]
    assert "Уточни объяснение" in payload["contents"][0]["parts"][0]["text"]


@pytest.mark.parametrize(
    "status, reason, expected",
    [
        (400, "API_KEY_INVALID", "AI_AUTH_FAILED"),
        (400, "API_KEY_EXPIRED", "AI_AUTH_FAILED"),
        (400, None, "AI_REQUEST_REJECTED"),
        (401, None, "AI_AUTH_FAILED"),
        (403, "SERVICE_DISABLED", "AI_SERVICE_DISABLED"),
        (403, "BILLING_DISABLED", "AI_BILLING_REQUIRED"),
        (403, None, "AI_ACCESS_DENIED"),
        (404, None, "AI_MODEL_UNAVAILABLE"),
        (429, None, "AI_PROVIDER_QUOTA_EXHAUSTED"),
    ],
)
def test_gemini_rejections_are_safe_and_refund_reservation(db, settings, status, reason, expected):
    configure(settings)
    body = {"error": {"message": "Private error", "details": [{"reason": reason}]}}
    error = HTTPError(
        "https://generativelanguage.googleapis.com",
        status,
        "Error",
        {},
        io.BytesIO(json.dumps(body).encode()),
    )
    with patch("apps.ai.gemini.urlopen", side_effect=error):
        with pytest.raises(GenerationFailure) as caught:
            GeminiProvider().generate_course([], {})
    assert caught.value.code == expected
    assert "Private" not in str(caught.value)
    assert AIBudgetDay.objects.get().reserved_usd == 0


@pytest.mark.parametrize("status", [408, 500, 503])
def test_gemini_uncertain_http_failure_retains_budget(db, settings, status):
    configure(settings)
    error = HTTPError(
        "https://generativelanguage.googleapis.com", status, "Error", {}, io.BytesIO(b"{}")
    )
    with patch("apps.ai.gemini.urlopen", side_effect=error):
        with pytest.raises(HTTPError):
            GeminiProvider().generate_course([], {})
    assert AIBudgetDay.objects.get().reserved_usd > 0


def test_gemini_network_failure_retains_budget(db, settings):
    configure(settings)
    with patch("apps.ai.gemini.urlopen", side_effect=URLError("Private transport detail")):
        with pytest.raises(URLError):
            GeminiProvider().generate_course([], {})
    assert AIBudgetDay.objects.get().reserved_usd > 0


@pytest.mark.parametrize(
    "finish, code", [("MAX_TOKENS", "AI_OUTPUT_LIMIT"), ("SAFETY", "AI_CONTENT_BLOCKED")]
)
def test_incomplete_gemini_output_accounts_confirmed_usage(db, settings, finish, code):
    configure(settings)
    with patch("apps.ai.gemini.urlopen", return_value=response({}, finish)):
        with pytest.raises(GenerationFailure) as caught:
            GeminiProvider().generate_course([], {})
    assert caught.value.code == code and caught.value.usage.output_tokens == 250
    assert AIBudgetDay.objects.get().reserved_usd == Decimal("0.000400")


def test_gemini_invalid_json_is_not_a_valid_draft(db, settings):
    configure(settings)
    with patch("apps.ai.gemini.urlopen", return_value=response({"wrong": "schema"})):
        with pytest.raises(GenerationFailure) as caught:
            GeminiProvider().generate_course([], {})
    assert caught.value.code == "OUTPUT_VALIDATION_FAILED"


def test_gemini_relaxes_wire_schema_but_still_checks_nested_bounds(db, settings):
    configure(settings)
    data = draft_data(SimpleNamespace(pk="source-id"))
    data["weeks"] = data["weeks"] * 17
    with patch("apps.ai.gemini.urlopen", return_value=response(data)) as send:
        with pytest.raises(GenerationFailure) as caught:
            GeminiProvider().generate_course([], {})
    schema = json.loads(send.call_args.args[0].data)["generationConfig"]["responseJsonSchema"]
    assert "maxItems" not in json.dumps(schema)
    assert schema["properties"]["weeks"]["minItems"] == 1
    assert caught.value.code == "OUTPUT_VALIDATION_FAILED"
    assert caught.value.usage.output_tokens == 250


def test_unknown_provider_is_reported_as_unconfigured(world, settings, client_for):
    settings.AI_PROVIDER = "unknown"
    with patch("apps.ai.views.worker_available", return_value=True):
        result = client_for(world["teacher"]).get("/api/v1/ai-status/")
    assert result.status_code == 200
    assert not result.data["configured"]


def test_worker_selects_gemini_records_its_model_and_does_not_publish(world, settings):
    configure(settings)
    document = source(world)
    chunk = document.chunks.get()
    job = create_job(
        world["teacher"],
        world["course"],
        {"weeks": 1, "assignments": True, "tests": False},
        "gemini",
        sources=[document.pk],
    )
    with (
        patch("apps.ai.gemini.urlopen", return_value=response(draft_data(chunk))) as send,
        patch("apps.ai.tasks.OpenAIProvider") as openai,
    ):
        generate_course(str(job.pk))
        generate_course(str(job.pk))
    openai.assert_not_called()
    assert send.call_count == 1
    job.refresh_from_db()
    assert job.status == "COMPLETED"
    draft = AICourseDraft.objects.get(job=job)
    assert draft.imported_version_id is None
    assert AIUsageLog.objects.get(job=job).model == "gemini-3.1-flash-lite"
    world["course"].refresh_from_db()
    assert world["course"].current_version_id == world["version"].pk


def test_gemini_api_status_uses_selected_model_and_hides_both_keys(world, settings, client_for):
    configure(settings)
    settings.OPENAI_API_KEY = "openai-sentinel-never-return"
    with patch("apps.ai.views.worker_available", return_value=True):
        result = client_for(world["teacher"]).get("/api/v1/ai-status/")
    assert result.status_code == 200
    assert result.data["configured"] and result.data["model"] == settings.GEMINI_MODEL
    assert settings.GEMINI_API_KEY not in str(result.data)
    assert settings.OPENAI_API_KEY not in str(result.data)
    assert settings.GEMINI_API_KEY not in repr(provider_configuration())


@pytest.mark.parametrize(
    "key, model", [("", "gemini-3.1-flash-lite"), ("fake", "../../other-host")]
)
def test_invalid_gemini_configuration_never_calls_network(db, settings, key, model):
    configure(settings)
    settings.GEMINI_API_KEY, settings.GEMINI_MODEL = key, model
    with patch("apps.ai.gemini.urlopen") as send:
        with pytest.raises(GenerationFailure):
            GeminiProvider().generate_course([], {})
    send.assert_not_called()


def test_zero_price_free_tier_is_valid(db, settings):
    configure(settings)
    settings.GEMINI_INPUT_PRICE = settings.GEMINI_OUTPUT_PRICE = "0"
    assert provider_configuration().configured
    data = draft_data(SimpleNamespace(pk="source-id"))
    with patch("apps.ai.gemini.urlopen", return_value=response(data)):
        GeminiProvider().generate_course([], {})
    assert AIBudgetDay.objects.get().reserved_usd == 0


@pytest.mark.parametrize("operation", ["course", "topic"])
def test_unlimited_gemini_uses_model_output_ceiling_and_records_cost(db, settings, operation):
    configure(settings)
    settings.GEMINI_APP_LIMITS_ENABLED = False
    settings.AI_DAILY_BUDGET_USD = "0"
    data = draft_data(SimpleNamespace(pk="source-id"))
    with patch(
        "apps.ai.gemini.urlopen",
        return_value=response(data if operation == "course" else data["weeks"][0]["topics"][0]),
    ) as send:
        if operation == "course":
            GeminiProvider().generate_course([], {})
        else:
            GeminiProvider().regenerate_topic([], {}, "Revise")
    assert "maxOutputTokens" not in json.loads(send.call_args.args[0].data)["generationConfig"]
    assert send.call_args.kwargs["timeout"] is None
    assert AIBudgetDay.objects.get().reserved_usd == Decimal("0.000400")


def test_unlimited_gemini_processes_sources_and_generates_past_daily_limits(world, settings):
    from apps.ai.tasks import extract_document

    configure(settings)
    settings.GEMINI_APP_LIMITS_ENABLED = False
    settings.AI_MAX_SOURCE_CHARS = 2
    settings.AI_MAX_DAILY_JOBS = 1
    settings.AI_DAILY_BUDGET_USD = "0"
    document = source(world, "QUEUED")
    extract_document(str(document.pk))
    document.refresh_from_db()
    assert document.processing_status == "COMPLETED"
    chunk = document.chunks.get()
    assert len(chunk.content) > settings.AI_MAX_SOURCE_CHARS * 5
    for index in range(2):
        job = create_job(
            world["teacher"],
            world["course"],
            {"weeks": 1, "assignments": True, "tests": False},
            f"unlimited-{index}",
            sources=[document.pk],
        )
        with patch("apps.ai.gemini.urlopen", return_value=response(draft_data(chunk))) as send:
            generate_course(str(job.pk))
        send.assert_called_once()
        job.refresh_from_db()
        assert job.status == "COMPLETED"
        assert AIUsageLog.objects.get(job=job).input_tokens == 100


def test_unlimited_gemini_status_does_not_show_old_budget(world, settings, client_for):
    configure(settings)
    settings.GEMINI_APP_LIMITS_ENABLED = False
    with patch("apps.ai.views.worker_available", return_value=True):
        result = client_for(world["teacher"]).get("/api/v1/ai-status/")
    assert result.status_code == 200
    assert result.data["daily_budget"] == "unlimited"
    assert result.data["model"] == "gemini-3.1-flash-lite"


def test_disabling_gemini_limits_does_not_disable_openai_limits(world, settings):
    from rest_framework.exceptions import Throttled, ValidationError

    from apps.ai.budget import reserve_budget
    from apps.ai.jobs import snapshot

    configure(settings)
    settings.GEMINI_APP_LIMITS_ENABLED = False
    settings.AI_PROVIDER = "openai"
    settings.AI_INPUT_PRICE = settings.AI_OUTPUT_PRICE = "1"
    settings.AI_DAILY_BUDGET_USD = "0"
    settings.AI_MAX_SOURCE_CHARS = 2
    document = source(world)
    with pytest.raises(GenerationFailure) as caught:
        reserve_budget({}, {}, 100)
    assert caught.value.code == "AI_BUDGET_EXHAUSTED"
    with pytest.raises(ValidationError):
        snapshot(world["course"], [document.pk])
    settings.AI_MAX_DAILY_JOBS = 0
    with pytest.raises(Throttled):
        create_job(world["teacher"], world["course"], {}, "limited", sources=[document.pk])


@pytest.mark.parametrize("limited, expected", [(True, 429), (False, 202)])
def test_gemini_hourly_request_limit_follows_application_setting(
    world, settings, client_for, limited, expected
):
    from rest_framework.throttling import ScopedRateThrottle

    from apps.ai.models import AIJob

    configure(settings)
    settings.GEMINI_APP_LIMITS_ENABLED = limited
    document = source(world)
    client = client_for(world["teacher"])
    params = {
        "course": str(world["course"].pk),
        "weeks": 1,
        "language": "ru",
        "sources": [str(document.pk)],
    }
    with (
        patch("apps.ai.views.require_worker"),
        patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"ai": "1/hour"}),
    ):
        first = client.post("/api/v1/ai-jobs/", params, format="json")
        assert first.status_code == 202
        AIJob.objects.filter(pk=first.data["id"]).update(status="FAILED")
        assert client.post("/api/v1/ai-jobs/", params, format="json").status_code == expected
