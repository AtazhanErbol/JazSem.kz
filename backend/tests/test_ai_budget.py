from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.ai.budget import reserve_budget, settle_budget
from apps.ai.models import AIBudgetDay
from apps.ai.provider import OpenAIProvider


def test_disabled_ai_never_calls_provider(db, settings):
    settings.AI_ENABLED = False
    settings.OPENAI_API_KEY = "test-only-not-a-real-key"
    settings.OPENAI_MODEL = "gpt-5-nano"
    with patch("apps.ai.provider.OpenAI") as provider:
        with pytest.raises(ValueError, match="disabled"):
            OpenAIProvider().generate_course([], {})
        provider.return_value.responses.parse.assert_not_called()


def test_global_budget_reserves_and_stops_calls(db, settings):
    settings.AI_ENABLED = True
    settings.AI_INPUT_PRICE = "0.05"
    settings.AI_OUTPUT_PRICE = "0.40"
    settings.AI_DAILY_BUDGET_USD = "0.004"
    reservation = reserve_budget({"sources": "hello"}, {}, 8000)
    with pytest.raises(ValueError, match="exhausted"):
        reserve_budget({"sources": "hello"}, {}, 8000)
    settle_budget(reservation, SimpleNamespace(input_tokens=100, output_tokens=100))
    assert AIBudgetDay.objects.get().reserved_usd == Decimal("0.000045")
    reserve_budget({"sources": "hello"}, {}, 8000)


def test_unknown_prices_fail_closed(db, settings):
    settings.AI_ENABLED = True
    settings.AI_INPUT_PRICE = ""
    with pytest.raises(ValueError, match="prices"):
        reserve_budget({}, {}, 100)
