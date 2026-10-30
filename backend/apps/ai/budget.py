import json
from decimal import ROUND_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .configuration import provider_configuration
from .errors import GenerationFailure
from .models import AIBudgetDay


def reserve_budget(payload, schema, output_limit):
    if not settings.AI_ENABLED:
        raise GenerationFailure("AI_DISABLED", "AI is disabled; enable AI_ENABLED explicitly")
    config = provider_configuration()
    if not config.input_price or not config.output_price:
        raise GenerationFailure("AI_NOT_CONFIGURED", "Configure model prices before enabling AI")
    # UTF-8 bytes are a conservative token upper bound for byte-level tokenizers.
    # Include schema, payload and a margin for fixed instructions/API framing.
    input_bound = (
        len(json.dumps(payload, ensure_ascii=False).encode())
        + len(json.dumps(schema).encode())
        + 8000
    )
    cost = (
        (
            Decimal(input_bound) * Decimal(config.input_price)
            + Decimal(output_limit) * Decimal(config.output_price)
        )
        / 1000000
    ).quantize(Decimal(".000001"), rounding=ROUND_UP)
    day = timezone.now().date()
    with transaction.atomic():
        AIBudgetDay.objects.get_or_create(day=day)
        account = AIBudgetDay.objects.select_for_update().get(day=day)
        if config.limits_enabled and account.reserved_usd + cost > Decimal(
            settings.AI_DAILY_BUDGET_USD
        ):
            raise GenerationFailure("AI_BUDGET_EXHAUSTED", "Daily application AI budget exhausted")
        account.reserved_usd += cost
        account.save()
    return day, cost


def release_budget(reservation):
    """Refund this reservation only when an explicit rejection proves no run."""
    day, reserved = reservation
    with transaction.atomic():
        account = AIBudgetDay.objects.select_for_update().get(day=day)
        account.reserved_usd = max(Decimal(0), account.reserved_usd - reserved)
        account.save()


def settle_budget(reservation, usage):
    day, reserved = reservation
    config = provider_configuration()
    actual = (
        Decimal(usage.input_tokens) * Decimal(config.input_price)
        + Decimal(usage.output_tokens) * Decimal(config.output_price)
    ) / 1000000
    with transaction.atomic():
        account = AIBudgetDay.objects.select_for_update().get(day=day)
        account.reserved_usd = max(Decimal(0), account.reserved_usd - reserved + actual)
        account.save()
    # Uncertain/failed calls retain reservations until the next UTC day.
