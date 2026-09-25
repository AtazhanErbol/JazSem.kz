import json
from decimal import ROUND_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import AIBudgetDay


def reserve_budget(payload, schema, output_limit):
    if not settings.AI_ENABLED:
        raise ValueError("AI is disabled; enable AI_ENABLED explicitly")
    if not settings.AI_INPUT_PRICE or not settings.AI_OUTPUT_PRICE:
        raise ValueError("Configure model prices before enabling AI")
    # UTF-8 bytes are a conservative token upper bound for byte-level tokenizers.
    # Include schema, payload and a margin for fixed instructions/API framing.
    input_bound = (
        len(json.dumps(payload, ensure_ascii=False).encode())
        + len(json.dumps(schema).encode())
        + 8000
    )
    cost = (
        (
            Decimal(input_bound) * Decimal(settings.AI_INPUT_PRICE)
            + Decimal(output_limit) * Decimal(settings.AI_OUTPUT_PRICE)
        )
        / 1000000
    ).quantize(Decimal(".000001"), rounding=ROUND_UP)
    day = timezone.now().date()
    with transaction.atomic():
        AIBudgetDay.objects.get_or_create(day=day)
        account = AIBudgetDay.objects.select_for_update().get(day=day)
        if account.reserved_usd + cost > Decimal(settings.AI_DAILY_BUDGET_USD):
            raise ValueError("Daily application AI budget exhausted")
        account.reserved_usd += cost
        account.save()
    return day, cost


def settle_budget(reservation, usage):
    day, reserved = reservation
    actual = (
        Decimal(usage.input_tokens) * Decimal(settings.AI_INPUT_PRICE)
        + Decimal(usage.output_tokens) * Decimal(settings.AI_OUTPUT_PRICE)
    ) / 1000000
    with transaction.atomic():
        account = AIBudgetDay.objects.select_for_update().get(day=day)
        account.reserved_usd = max(Decimal(0), account.reserved_usd - reserved + actual)
        account.save()
    # Uncertain/failed calls retain reservations until the next UTC day.
