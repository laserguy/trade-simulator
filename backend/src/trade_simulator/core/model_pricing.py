"""LLM model options with prices, so the user can choose by cost (D9)."""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

MILLION = Decimal(1_000_000)


@dataclass(frozen=True)
class ModelOption:
    provider: str
    model_id: str
    label: str
    input_usd_per_million: Decimal
    output_usd_per_million: Decimal
    note: str = ""

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        return (
            input_tokens * self.input_usd_per_million + output_tokens * self.output_usd_per_million
        ) / MILLION


@dataclass(frozen=True)
class ModelCatalogue:
    """Prices change; `as_of` records when they were copied from the providers' pricing pages."""

    as_of: date
    options: tuple[ModelOption, ...]

    def for_providers(self, providers: Collection[str]) -> tuple[ModelOption, ...]:
        return tuple(option for option in self.options if option.provider in providers)

    def find(self, model_id: str) -> ModelOption | None:
        return next((option for option in self.options if option.model_id == model_id), None)
