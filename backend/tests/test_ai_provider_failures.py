from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from httpx2 import Request, Response
from openai import APIConnectionError, APIStatusError

from apps.ai.errors import GenerationFailure
from apps.ai.jobs import create_job
from apps.ai.models import AIBudgetDay, AIUsageLog
from apps.ai.provider import OpenAIProvider
from apps.ai.tasks import generate_course
from tests.test_ai_recovery import configured, source


def setup_provider(settings):
    configured(settings)
    settings.AI_DAILY_BUDGET_USD = "1"


@pytest.mark.parametrize("operation", ["generate_course", "regenerate_topic"])
@pytest.mark.parametrize(
    "status, provider_code, expected",
    [
        (429, "credit_balance_exhausted", "AI_CREDITS_EXHAUSTED"),
        (429, "insufficient_quota", "AI_PROVIDER_QUOTA_EXHAUSTED"),
        (429, "organization_spend_limit_exceeded", "AI_SPEND_LIMIT_REACHED"),
        (429, "project_spend_limit_exceeded", "AI_SPEND_LIMIT_REACHED"),
        (429, "organization_usage_limit_exceeded", "AI_PROVIDER_QUOTA_EXHAUSTED"),
        (429, "rate_limit_exceeded", "AI_RATE_LIMITED"),
        (429, "slow_down", "AI_RATE_LIMITED"),
        (401, "invalid_api_key", "AI_AUTH_FAILED"),
        (403, None, "AI_ACCESS_DENIED"),
        (404, "model_not_found", "AI_MODEL_UNAVAILABLE"),
        (400, None, "AI_REQUEST_REJECTED"),
    ],
)
def test_explicit_rejections_have_safe_codes_and_release_only_their_reservation(
    db, settings, operation, status, provider_code, expected
):
    setup_provider(settings)
    from django.utils import timezone

    previous = Decimal("0.1")
    AIBudgetDay.objects.create(day=timezone.now().date(), reserved_usd=previous)
    request = Request("POST", "https://api.openai.com/v1/responses")
    error = APIStatusError(
        "private provider error must not be shown",
        response=Response(status, request=request),
        body={"code": provider_code},
    )
    with patch("apps.ai.provider.OpenAI") as client:
        client.return_value.responses.parse.side_effect = error
        with pytest.raises(GenerationFailure) as caught:
            provider = OpenAIProvider()
            if operation == "generate_course":
                provider.generate_course([], {})
            else:
                provider.regenerate_topic([], {}, "Revise")
    assert caught.value.code == expected
    assert "private" not in str(caught.value)
    assert AIBudgetDay.objects.get().reserved_usd == previous
    assert client.return_value.responses.parse.call_count == 1


@pytest.mark.parametrize("status", [408, 500, 503])
def test_uncertain_server_failures_keep_reservation(db, settings, status):
    setup_provider(settings)
    request = Request("POST", "https://api.openai.com/v1/responses")
    error = APIStatusError("failure", response=Response(status, request=request), body={})
    with patch("apps.ai.provider.OpenAI") as client:
        client.return_value.responses.parse.side_effect = error
        with pytest.raises(APIStatusError):
            OpenAIProvider().generate_course([], {})
    assert AIBudgetDay.objects.get().reserved_usd > 0


def test_network_loss_keeps_reservation(db, settings):
    setup_provider(settings)
    error = APIConnectionError(request=Request("POST", "https://api.openai.com/v1/responses"))
    with patch("apps.ai.provider.OpenAI") as client:
        client.return_value.responses.parse.side_effect = error
        with pytest.raises(APIConnectionError):
            OpenAIProvider().generate_course([], {})
    assert AIBudgetDay.objects.get().reserved_usd > 0


def test_incomplete_output_accounts_usage_and_explains_token_limit(db, settings):
    setup_provider(settings)
    with patch("apps.ai.provider.OpenAI") as client:
        client.return_value.responses.parse.return_value = SimpleNamespace(
            output_parsed=None,
            usage=SimpleNamespace(input_tokens=10, output_tokens=20),
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        )
        with pytest.raises(GenerationFailure) as caught:
            OpenAIProvider().generate_course([], {})
    assert caught.value.code == "AI_OUTPUT_LIMIT"
    assert caught.value.usage.input_tokens == 10
    assert AIBudgetDay.objects.get().reserved_usd == Decimal("0.000030")


def test_local_budget_failure_is_not_an_uncertain_paid_call(world, settings):
    setup_provider(settings)
    settings.AI_DAILY_BUDGET_USD = "0"
    document = source(world)
    job = create_job(
        world["teacher"], world["course"], {"weeks": 1}, "budget", sources=[document.pk]
    )
    with patch("apps.ai.provider.OpenAI") as client:
        generate_course(str(job.pk))
    client.assert_not_called()
    job.refresh_from_db()
    usage = AIUsageLog.objects.get(job=job)
    assert job.error == "AI_BUDGET_EXHAUSTED"
    assert usage.status == "REJECTED" and usage.estimated_cost == 0


def test_worker_reports_credit_exhaustion_without_replay(world, settings):
    setup_provider(settings)
    document = source(world)
    job = create_job(
        world["teacher"], world["course"], {"weeks": 1}, "credits", sources=[document.pk]
    )
    error = APIStatusError(
        "private",
        response=Response(429, request=Request("POST", "https://api.openai.com/v1/responses")),
        body={"code": "credit_balance_exhausted"},
    )
    with patch("apps.ai.provider.OpenAI") as client:
        client.return_value.responses.parse.side_effect = error
        generate_course(str(job.pk))
        generate_course(str(job.pk))
    job.refresh_from_db()
    usage = AIUsageLog.objects.get(job=job)
    assert job.status == "FAILED" and job.error == "AI_CREDITS_EXHAUSTED"
    assert usage.status == "REJECTED" and usage.estimated_cost == 0
    assert AIBudgetDay.objects.get().reserved_usd == 0
    assert client.return_value.responses.parse.call_count == 1
