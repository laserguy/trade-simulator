"""Estimated cost of each run mode, for the Run mode cards (D35).

Only the AI model's cost is shown in money; that is what's billed. Web searches are compared with the
search provider's free monthly allowance (D34): past it, searches stop until the month resets.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from trade_simulator.application.run_mode import RunMode
from trade_simulator.core.decision_log import DecisionRun, RunStatus, RunTrigger
from trade_simulator.core.exchange_profile import ExchangeProfile
from trade_simulator.core.model_pricing import ModelOption
from trade_simulator.core.run_budget import DECISION_RUN_LIMITS

TRADING_DAYS_PER_MONTH = 21
MIN_RUNS_FOR_AVERAGE = 3
RUNS_TO_AVERAGE = 20
GUESS_INPUT_TOKENS = 20_000
GUESS_OUTPUT_TOKENS = 2_000


@dataclass(frozen=True)
class ModeEstimate:
    mode: RunMode
    runs_per_month: int | None  # None for Manual: depends on clicks
    ai_cost_per_run: Decimal
    ai_cost_per_month: Decimal | None
    searches_per_month: int | None
    within_free_allowance: bool
    allowance_lasts_trading_days: int | None  # set only when the allowance runs out


@dataclass(frozen=True)
class RunCostEstimates:
    basis: str  # "rough" or "your last N runs"
    modes: tuple[ModeEstimate, ...]


def estimate_modes(
    model: ModelOption,
    runs: Iterable[DecisionRun],
    profile: ExchangeProfile,
    free_searches_per_month: int | None,
) -> RunCostEstimates:
    measured = [
        r for r in runs
        if r.trigger is not RunTrigger.REFRESH and r.status is RunStatus.COMPLETED and r.cost.input_tokens > 0
    ][:RUNS_TO_AVERAGE]
    if len(measured) >= MIN_RUNS_FOR_AVERAGE:
        count = len(measured)
        input_tokens = sum(r.cost.input_tokens for r in measured) / count
        output_tokens = sum(r.cost.output_tokens for r in measured) / count
        searches = sum(r.cost.searches for r in measured) / count
        basis = f"your last {count} runs"
    else:
        input_tokens, output_tokens = GUESS_INPUT_TOKENS, GUESS_OUTPUT_TOKENS
        searches = DECISION_RUN_LIMITS.max_searches
        basis = "rough"

    per_run = model.estimate_cost(round(input_tokens), round(output_tokens))
    runs_per_day = {RunMode.DAILY: 1, RunMode.EVERY_15_MIN: _quarter_hours_per_session(profile)}

    modes = [ModeEstimate(RunMode.MANUAL, None, per_run, None, None, True, None)]
    for mode, per_day in runs_per_day.items():
        runs_per_month = per_day * TRADING_DAYS_PER_MONTH
        searches_per_month = round(runs_per_month * searches)
        searches_per_day = per_day * searches
        fits = free_searches_per_month is None or searches_per_month <= free_searches_per_month
        lasts = None if fits or not searches_per_day else int(free_searches_per_month // searches_per_day)
        modes.append(
            ModeEstimate(mode, runs_per_month, per_run, per_run * runs_per_month, searches_per_month, fits, lasts)
        )
    return RunCostEstimates(basis=basis, modes=tuple(modes))


def _quarter_hours_per_session(profile: ExchangeProfile) -> int:
    day = datetime(2000, 1, 1)
    session = datetime.combine(day, profile.regular_close) - datetime.combine(day, profile.regular_open)
    return int(session / timedelta(minutes=15))
