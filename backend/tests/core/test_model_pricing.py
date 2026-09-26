from datetime import date
from decimal import Decimal

from trade_simulator.core.model_pricing import ModelCatalogue, ModelOption

LUNA = ModelOption("openai", "gpt-6-luna", "GPT-6 Luna", Decimal("0.10"), Decimal("0.50"))
SONNET = ModelOption("anthropic", "claude-sonnet-5", "Claude Sonnet 5", Decimal("2"), Decimal("10"))
CATALOGUE = ModelCatalogue(as_of=date(2026, 9, 26), options=(LUNA, SONNET))


def test_estimated_cost_uses_per_million_prices():
    # 1M input at $0.10 + 200k output at $0.50/M = $0.20
    assert LUNA.estimate_cost(1_000_000, 200_000) == Decimal("0.20")


def test_catalogue_filters_by_provider():
    assert CATALOGUE.for_providers({"anthropic"}) == (SONNET,)
    assert CATALOGUE.for_providers(set()) == ()


def test_catalogue_finds_model_by_id():
    assert CATALOGUE.find("claude-sonnet-5") == SONNET
    assert CATALOGUE.find("nope") is None
