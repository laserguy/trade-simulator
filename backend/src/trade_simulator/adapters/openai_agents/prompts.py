"""Loads agent instructions from prompts/*.md (D25) and fills in exchange- and rule-specific values.

Placeholders use `$name`. Values come from the exchange profile and core rules, so prompts never
hard-code numbers that the code enforces (D24).
"""

from pathlib import Path
from string import Template

from trade_simulator.core.decision_log import MAX_WATCHLIST_SIZE
from trade_simulator.core.errors import ConfigError
from trade_simulator.core.exchange_profile import ExchangeProfile
from trade_simulator.core.run_budget import DECISION_RUN_LIMITS, REFRESH_RUN_LIMITS
from trade_simulator.core.strategy import SECTION_WORD_LIMIT
from trade_simulator.core.strategy_review import STRATEGY_REVIEW_MINIMUMS
from trade_simulator.core.trading_rules import TradingRules


class PromptLibrary:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def render(self, name: str, profile: ExchangeProfile) -> str:
        path = self._directory / f"{name}.md"
        try:
            template = Template(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ConfigError(f"Prompt file missing: {path}") from exc
        try:
            return template.substitute(_values(profile))
        except (KeyError, ValueError) as exc:
            raise ConfigError(f"Prompt {path.name} has an unknown or malformed placeholder: {exc}") from exc


def _values(profile: ExchangeProfile) -> dict[str, str]:
    rules = TradingRules.for_exchange(profile)
    return {
        "exchange_name": profile.name,
        "currency": profile.currency,
        "stock_pool": profile.stock_pool,
        "fee": f"{rules.fee_per_trade} {profile.currency}",
        "max_position_percent": f"{rules.max_position_fraction * 100:.0f}%",
        "decision_max_research_calls": str(DECISION_RUN_LIMITS.max_research_calls),
        "decision_max_searches": str(DECISION_RUN_LIMITS.max_searches),
        "refresh_max_searches": str(REFRESH_RUN_LIMITS.max_searches),
        "watchlist_max": str(MAX_WATCHLIST_SIZE),
        "section_word_limit": str(SECTION_WORD_LIMIT),
        "review_min_days": str(STRATEGY_REVIEW_MINIMUMS.trading_days),
        "review_min_runs": str(STRATEGY_REVIEW_MINIMUMS.trading_runs),
    }
