from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from trade_simulator.adapters.sqlite_repository import SqliteRepository
from trade_simulator.core.decision_log import (
    DecisionRun,
    Finding,
    RunCost,
    RunStatus,
    RunTrigger,
    Watchlist,
    WatchlistEntry,
)
from trade_simulator.core.errors import StorageError
from trade_simulator.core.order import Order, Side
from trade_simulator.core.portfolio import Portfolio, Position
from trade_simulator.core.trading_rules import OrderResult, OrderStatus, RejectionReason

START = datetime(2026, 9, 28, 13, 30, tzinfo=timezone.utc)


@pytest.fixture
def repo(tmp_path):
    repository = SqliteRepository(tmp_path / "sim.sqlite3")
    repository.initialize()
    return repository


def make_run(run_id="run-1", started_at=START, status=RunStatus.COMPLETED):
    buy = Order("AAPL", Side.BUY, 5, reason="Beat earnings")
    too_big = Order("MSFT", Side.BUY, 50, reason="Momentum")
    return DecisionRun(
        id=run_id,
        trigger=RunTrigger.MANUAL,
        started_at=started_at,
        finished_at=started_at + timedelta(seconds=45),
        status=status,
        failure_reason=None,
        findings=(
            Finding(
                symbol="AAPL",
                summary="Earnings beat expectations",
                sources=("https://example.com/aapl",),
                warnings=(),
            ),
        ),
        order_results=(
            OrderResult(buy, OrderStatus.EXECUTED, price=Decimal("200.15"), fee=Decimal("1")),
            OrderResult(too_big, OrderStatus.REJECTED, rejection_reason=RejectionReason.EXCEEDS_POSITION_CAP),
        ),
        cost=RunCost(input_tokens=1200, output_tokens=300, searches=2),
        trace_id="trace_abc",
    )


PORTFOLIO = Portfolio(
    cash=Decimal("8998.25"),
    positions={"AAPL": Position("AAPL", 5, Decimal("200.15"))},
)


def test_fresh_database_has_no_portfolio(repo):
    assert repo.load_portfolio() is None


def test_portfolio_round_trips_with_exact_decimals(repo):
    repo.save_portfolio(PORTFOLIO)

    assert repo.load_portfolio() == PORTFOLIO


def test_saving_a_run_stores_run_and_new_portfolio_together(repo):
    repo.save_portfolio(Portfolio.starting(Decimal("10000")))
    run = make_run()

    repo.save_run(run, PORTFOLIO)

    assert repo.get_run("run-1") == run
    assert repo.load_portfolio() == PORTFOLIO


def test_failed_run_is_logged_without_touching_portfolio(repo):
    repo.save_portfolio(PORTFOLIO)
    failed = DecisionRun(
        id="run-2",
        trigger=RunTrigger.EVERY_15_MIN,
        started_at=START,
        finished_at=START,
        status=RunStatus.FAILED,
        failure_reason="Finnhub unavailable",
        findings=(),
        order_results=(),
        cost=RunCost(0, 0, 0),
        trace_id=None,
    )

    repo.save_run(failed, None)

    assert repo.get_run("run-2") == failed
    assert repo.load_portfolio() == PORTFOLIO


def test_run_save_is_all_or_nothing(repo):
    repo.save_portfolio(Portfolio.starting(Decimal("10000")))
    repo.save_run(make_run("run-1"), Portfolio.starting(Decimal("10000")))

    # Same run id again: the run insert fails, so the new portfolio must not be saved either.
    with pytest.raises(StorageError):
        repo.save_run(make_run("run-1"), PORTFOLIO)

    assert repo.load_portfolio() == Portfolio.starting(Decimal("10000"))


def test_unknown_run_is_none(repo):
    assert repo.get_run("nope") is None


def test_list_runs_returns_newest_first_with_limit(repo):
    for i in range(3):
        repo.save_run(make_run(f"run-{i}", START + timedelta(minutes=15 * i)), None)

    runs = repo.list_runs(limit=2)

    assert [r.id for r in runs] == ["run-2", "run-1"]


def refresh_run(run_id, started_at, overview, status=RunStatus.COMPLETED):
    return DecisionRun(
        id=run_id,
        trigger=RunTrigger.REFRESH,
        started_at=started_at,
        finished_at=started_at + timedelta(minutes=3),
        status=status,
        failure_reason=None,
        findings=(Finding("MARKET", overview, ("https://example.com/market",)),),
        order_results=(),
        cost=RunCost(0, 0, 0),
        trace_id=None,
    )


def test_no_market_overview_before_any_refresh(repo):
    assert repo.latest_market_overview() is None


def test_latest_market_overview_comes_from_the_newest_completed_refresh(repo):
    repo.save_run(refresh_run("r1", START, "Old overview"), None)
    repo.save_run(refresh_run("r2", START + timedelta(days=1), "New overview"), None)
    repo.save_run(refresh_run("r3", START + timedelta(days=2), "Broken", status=RunStatus.FAILED), None)
    repo.save_run(make_run("d1", started_at=START + timedelta(days=3)), None)

    overview = repo.latest_market_overview()

    assert overview.summary == "New overview"
    assert overview.sources == ("https://example.com/market",)
    assert overview.as_of == START + timedelta(days=1)


def test_watchlist_round_trips_and_is_replaced_on_save(repo):
    first = Watchlist(entries=(WatchlistEntry("AAPL", "Earnings", ("https://a",)),), refreshed_at=START)
    second = Watchlist(
        entries=(WatchlistEntry("MSFT", "Cloud"), WatchlistEntry("NVDA", "AI demand")),
        refreshed_at=START + timedelta(days=1),
    )

    assert repo.load_watchlist() is None
    repo.save_watchlist(first)
    repo.save_watchlist(second)

    assert repo.load_watchlist() == second


def test_run_cost_keeps_the_model_used(repo):
    run = make_run()
    run = DecisionRun(**{**run.__dict__, "cost": RunCost(10, 2, 1, model="gpt-6-luna")})

    repo.save_run(run, None)

    assert repo.get_run("run-1").cost.model == "gpt-6-luna"


def test_settings_are_saved_and_cleared(repo):
    assert repo.load_settings() == {}

    repo.save_setting("model_id", "gpt-6-luna")
    repo.save_setting("openai_api_key", "sk-1")
    repo.save_setting("openai_api_key", None)

    assert repo.load_settings() == {"model_id": "gpt-6-luna"}


def test_benchmark_start_is_saved_once(repo):
    assert repo.load_benchmark_start() is None

    repo.save_benchmark_start("SPY", Decimal("500.25"), START)

    start = repo.load_benchmark_start()
    assert (start.symbol, start.price, start.started_at) == ("SPY", Decimal("500.25"), START)


def test_older_database_gains_the_model_column(tmp_path):
    import sqlite3

    path = tmp_path / "old.sqlite3"
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE runs (id TEXT PRIMARY KEY, trigger TEXT NOT NULL, started_at TEXT NOT NULL,
           finished_at TEXT, status TEXT NOT NULL, failure_reason TEXT, input_tokens INTEGER NOT NULL,
           output_tokens INTEGER NOT NULL, searches INTEGER NOT NULL, trace_id TEXT)"""
    )
    conn.commit()
    conn.close()

    repository = SqliteRepository(path)
    repository.initialize()
    repository.save_run(make_run(), None)

    assert repository.get_run("run-1").cost.model is None


def test_daily_bars_are_upserted_per_exchange_symbol_and_day(repo):
    from datetime import date

    from trade_simulator.application.ports import DailyBar

    first = DailyBar(date(2026, 9, 25), Decimal("1"), Decimal("2"), Decimal("0.5"), Decimal("1.5"), Decimal("1.4"), 10)
    revised = DailyBar(date(2026, 9, 25), Decimal("1"), Decimal("2"), Decimal("0.5"), Decimal("1.6"), Decimal("1.5"), 11)

    repo.save_daily_bars("US", "NVDA", [first], source="tiingo")
    repo.save_daily_bars("US", "NVDA", [revised], source="tiingo")

    assert repo.load_daily_bars("US", "NVDA", date(2026, 1, 1)) == [revised]
    assert repo.load_daily_bars("JP", "NVDA", date(2026, 1, 1)) == []


def test_price_sync_round_trips(repo):
    from datetime import date

    from trade_simulator.application.ports import PriceSync

    sync = PriceSync("US", "NVDA", date(2025, 8, 24), date(2026, 9, 25), START)
    repo.save_price_sync(sync)

    assert repo.load_price_sync("US", "NVDA") == sync
    assert repo.load_price_sync("US", "MSFT") is None


def test_executed_trades_for_a_symbol_come_from_the_decision_log(repo):
    repo.save_run(make_run(), None)

    [trade] = repo.executed_trades("AAPL")

    assert (trade.side, trade.quantity, trade.price) == (Side.BUY, 5, Decimal("200.15"))
    assert trade.at == START
    assert repo.executed_trades("MSFT") == []  # the MSFT order was rejected


def test_data_survives_reopening_the_database(tmp_path):
    path = tmp_path / "sim.sqlite3"
    first = SqliteRepository(path)
    first.initialize()
    first.save_portfolio(PORTFOLIO)

    reopened = SqliteRepository(path)
    reopened.initialize()

    assert reopened.load_portfolio() == PORTFOLIO
