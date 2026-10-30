"""Provider selection without exposing credentials in status or diagnostics."""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.conf import settings


@dataclass(frozen=True)
class ProviderConfiguration:
    name: str
    model: str
    api_key: str = field(repr=False)
    input_price: str
    output_price: str

    @property
    def limits_enabled(self):
        return self.name != "gemini" or settings.GEMINI_APP_LIMITS_ENABLED

    @property
    def configured(self):
        try:
            prices = [Decimal(self.input_price), Decimal(self.output_price)]
            return bool(self.api_key and self.model) and all(
                price.is_finite() and price >= 0 for price in prices
            )
        except (InvalidOperation, TypeError, ValueError):
            return False


def provider_configuration():
    name = settings.AI_PROVIDER
    if name == "openai":
        return ProviderConfiguration(
            name,
            settings.OPENAI_MODEL,
            settings.OPENAI_API_KEY,
            settings.AI_INPUT_PRICE,
            settings.AI_OUTPUT_PRICE,
        )
    if name == "gemini":
        return ProviderConfiguration(
            name,
            settings.GEMINI_MODEL,
            settings.GEMINI_API_KEY,
            settings.GEMINI_INPUT_PRICE,
            settings.GEMINI_OUTPUT_PRICE,
        )
    return ProviderConfiguration(name, "", "", "", "")


def source_size_exceeded(chars, *, multiplier=1):
    return (
        provider_configuration().limits_enabled
        and chars > settings.AI_MAX_SOURCE_CHARS * multiplier
    )
