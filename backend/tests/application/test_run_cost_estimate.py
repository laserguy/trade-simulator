from datetime import datetime, timezone
from decimal import Decimal

from trade_simulator.application.run_cost_estimate import estimate_modes
from trade_simulator.application.run_mode import RunMode
from trade_simulator.core.decision_log import DecisionRun, RunCost, RunStatus, RunTrigger
from trade_simulator.core.exchange_profile import US_PROFILE
from trade_simulator.core.model_pricing import ModelOption

LUNA = ModelOption("openai", "gpt-6-luna", "GPT-6 Luna", Decimal("0.10"), Decimal("0.50"))
NOW = datetime(2026, 9, 28, tzinfo=timezone.utc)


def run(input_tokens, output_tokens, searches, trigger=RunTrigger.MANUAL, status=RunStatus.COMPLETED):
    return DecisionRun("r", trigger, NOW, NOW, status, None, (), (), RunCost(input_tokens, output_tokens, searches), None)


def by_mode(estimates):
    return {e.mode: e for e in estimates.modes}


def test_rough_estimate_until_there_are_three_decision_runs():
    estimates = estimate_modes(LUNA, [run(40_000, 4_000, 2)], US_PROFILE, free_searches_per_month=1000)

    assert estimates.basis == "rough"
    # guess: 20k in x $0.10/M + 2k out x $0.50/M = $0.003 per run
    assert by_mode(estimates)[RunMode.MANUAL].ai_cost_per_run == Decimal("0.003")


def test_real_runs_are_averaged_ignoring_refreshes_and_failures():
    runs = [
        run(30_000, 2_000, 4),
        run(10_000, 2_000, 2),
        run(20_000, 2_000, 3),
        run(500_000, 50_000, 20, trigger=RunTrigger.REFRESH),
        run(0, 0, 0, status=RunStatus.FAILED),
    ]

    estimates = estimate_modes(LUNA, runs, US_PROFILE, free_searches_per_month=1000)

    assert estimates.basis == "your last 3 runs"
    assert by_mode(estimates)[RunMode.MANUAL].ai_cost_per_run == Decimal("0.003")
    assert by_mode(estimates)[RunMode.DAILY].searches_per_month == 63  # 21 runs x 3 searches


def test_daily_fits_the_free_allowance_and_15_minutes_does_not():
    estimates = estimate_modes(LUNA, [], US_PROFILE, free_searches_per_month=1000)
    daily, fifteen = by_mode(estimates)[RunMode.DAILY], by_mode(estimates)[RunMode.EVERY_15_MIN]

    assert daily.runs_per_month == 21
    assert daily.ai_cost_per_month == Decimal("0.063")
    assert daily.within_free_allowance is True

    assert fifteen.runs_per_month == 546  # 26 runs a day x 21 trading days
    assert fifteen.searches_per_month == 2730
    assert fifteen.within_free_allowance is False
    assert fifteen.allowance_lasts_trading_days == 7  # 1000 / (26 x 5) = 7.7


def test_unlimited_search_provider_always_fits():
    estimates = estimate_modes(LUNA, [], US_PROFILE, free_searches_per_month=None)

    assert by_mode(estimates)[RunMode.EVERY_15_MIN].within_free_allowance is True
