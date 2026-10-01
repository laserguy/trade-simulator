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
from trade_simulator.core.strategy import DEVIATION, Strategy, StrategySection, StrategyVersion
from trade_simulator.core.strategy_review import (
    ClosedTrade,
    Followed,
    HoldingResult,
    ReviewDecision,
    ReviewTrigger,
    Scorecard,
    StrategyReview,
    TargetsVerdict,
)
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
                price=Decimal("200.15"),
                change_percent=Decimal("-1.4"),
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


def test_older_database_gains_the_finding_price_columns(tmp_path):
    import sqlite3

    path = tmp_path / "old.sqlite3"
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE findings (run_id TEXT NOT NULL, seq INTEGER NOT NULL, symbol TEXT NOT NULL,
           summary TEXT NOT NULL, sources TEXT NOT NULL, warnings TEXT NOT NULL, PRIMARY KEY (run_id, seq))"""
    )
    conn.execute("INSERT INTO findings VALUES ('old-run', 0, 'AAPL', 'Old finding', '[]', '[]')")
    conn.commit()
    conn.close()

    repository = SqliteRepository(path)
    repository.initialize()
    repository.save_run(make_run(), None)

    [finding] = repository.get_run("run-1").findings
    assert (finding.price, finding.change_percent) == (Decimal("200.15"), Decimal("-1.4"))


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


def test_executed_trades_for_all_symbols_carry_run_and_symbol(repo):
    repo.save_run(make_run("run-1", START), None)
    repo.save_run(make_run("run-2", START + timedelta(hours=1)), None)

    trades = repo.executed_trades()

    assert [(t.run_id, t.symbol, t.at) for t in trades] == [
        ("run-1", "AAPL", START),
        ("run-2", "AAPL", START + timedelta(hours=1)),
    ]


def test_executed_trades_carry_the_reason_the_agent_gave(repo):
    repo.save_run(make_run(), None)

    [trade] = repo.executed_trades("AAPL")

    assert trade.reason == "Beat earnings"


# --- strategies (D43) ---

STRATEGY = Strategy(
    what_i_look_for="Large companies with rising earnings estimates.",
    position_size="Start at 6%.",
    when_i_sell="Sell when the reason breaks.",
    cash_and_pace="Keep 10-25% in cash.",
    targets="Level with SPY or ahead.",
)

SCORECARD = Scorecard(
    period_start=START,
    period_end=START + timedelta(days=14),
    portfolio_percent=Decimal("-0.9"),
    benchmark_percent=Decimal("0.6"),
    trading_runs=14,
    trades=7,
    fees=Decimal("7"),
    closed_trades=(ClosedTrade("NVDA", Decimal("84.10")), ClosedTrade("AMD", Decimal("-41"))),
    holdings=(HoldingResult("AAPL", Decimal("3.2")),),
    average_cash_percent=Decimal("39"),
    followed_orders=5,
    deviations=2,
)


def make_review(review_id, started_at, decision=ReviewDecision.FIRST, status=RunStatus.COMPLETED, **changes):
    fields = dict(
        id=review_id,
        trigger=ReviewTrigger.BUTTON,
        started_at=started_at,
        finished_at=started_at + timedelta(seconds=20),
        status=status,
        failure_reason=None,
        reviewed_version=None,
        decision=decision,
        reason="No history yet; starting with earnings momentum.",
        cost=RunCost(8000, 1100, 0, model="gpt-6-luna"),
        trace_id="trace_review",
    )
    return StrategyReview(**{**fields, **changes})


def make_version(number, started_at, review_id, strategy=STRATEGY):
    return StrategyVersion(number=number, strategy=strategy, started_at=started_at, ended_at=None, review_id=review_id)


def test_no_strategy_before_the_first_review(repo):
    assert repo.current_strategy() is None
    assert repo.strategy_versions() == []
    assert repo.strategy_reviews() == []


def test_first_review_saves_the_review_and_version_1_together(repo):
    review = make_review("rev-1", START)
    version = make_version(1, START, "rev-1")

    repo.save_strategy_review(review, version)

    assert repo.strategy_reviews() == [review]
    assert repo.current_strategy() == version


def test_a_change_ends_the_current_version_and_starts_the_next(repo):
    repo.save_strategy_review(make_review("rev-1", START), make_version(1, START, "rev-1"))
    later = START + timedelta(days=14)
    changed = Strategy(**{**STRATEGY.__dict__, "position_size": "Start at 4%."})
    review = make_review(
        "rev-2",
        later,
        decision=ReviewDecision.CHANGE,
        reviewed_version=1,
        targets_verdict=TargetsVerdict.PARTLY_MET,
        targets_note="No forced sells, but 1.5 points behind SPY.",
        followed=Followed.PARTLY,
        followed_note="Bought NVDA ahead of earnings.",
        section_changes={StrategySection.POSITION_SIZE: "Two full buys fell together."},
        scorecard=SCORECARD,
    )

    repo.save_strategy_review(review, make_version(2, later, "rev-2", changed))

    first, second = repo.strategy_versions()
    assert (first.number, first.ended_at) == (1, later)
    assert repo.current_strategy() == second
    assert second.strategy.position_size == "Start at 4%."
    assert repo.strategy_reviews()[-1] == review


def test_keep_and_failed_reviews_leave_the_strategy_unchanged(repo):
    repo.save_strategy_review(make_review("rev-1", START), make_version(1, START, "rev-1"))
    kept = make_review("rev-2", START + timedelta(days=14), decision=ReviewDecision.KEEP, reviewed_version=1)
    failed = make_review(
        "rev-3", START + timedelta(days=28), decision=None, status=RunStatus.FAILED,
        failure_reason="Answer missed the When I sell section", reason="",
    )

    repo.save_strategy_review(kept, None)
    repo.save_strategy_review(failed, None)

    assert [r.id for r in repo.strategy_reviews()] == ["rev-1", "rev-2", "rev-3"]
    assert repo.current_strategy() == make_version(1, START, "rev-1")


def test_strategy_review_save_is_all_or_nothing(repo):
    repo.save_strategy_review(make_review("rev-1", START), make_version(1, START, "rev-1"))

    # Version 1 already exists: the version insert fails, so the review must not be saved either.
    with pytest.raises(StorageError):
        repo.save_strategy_review(make_review("rev-2", START + timedelta(days=14)), make_version(1, START, "rev-2"))

    assert [r.id for r in repo.strategy_reviews()] == ["rev-1"]
    assert repo.current_strategy().ended_at is None


def test_a_run_records_its_strategy_version_and_each_order_its_section(repo):
    run = make_run()
    buy = Order("AAPL", Side.BUY, 5, reason="Beat earnings", follows=StrategySection.WHAT_I_LOOK_FOR.value)
    sell = Order("MSFT", Side.SELL, 1, reason="Tariff news", follows=DEVIATION)
    run = DecisionRun(
        **{
            **run.__dict__,
            "strategy_version": 3,
            "order_results": (
                OrderResult(buy, OrderStatus.EXECUTED, price=Decimal("200.15"), fee=Decimal("1")),
                OrderResult(sell, OrderStatus.REJECTED, rejection_reason=RejectionReason.INSUFFICIENT_SHARES),
            ),
        }
    )

    repo.save_run(run, None)

    saved = repo.get_run("run-1")
    assert saved.strategy_version == 3
    assert [r.order.follows for r in saved.order_results] == ["what_i_look_for", "deviation"]


def test_runs_from_before_strategies_have_no_version(repo):
    repo.save_run(make_run(), None)

    saved = repo.get_run("run-1")
    assert saved.strategy_version is None
    assert {r.order.follows for r in saved.order_results} == {None}


def test_older_database_gains_the_strategy_columns(tmp_path):
    import sqlite3

    path = tmp_path / "old.sqlite3"
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE order_results (run_id TEXT NOT NULL, seq INTEGER NOT NULL, symbol TEXT NOT NULL,
           side TEXT NOT NULL, quantity INTEGER NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL,
           price TEXT, fee TEXT, rejection_reason TEXT, PRIMARY KEY (run_id, seq))"""
    )
    conn.commit()
    conn.close()

    repository = SqliteRepository(path)
    repository.initialize()
    repository.save_run(make_run(), None)

    assert repository.get_run("run-1").strategy_version is None


def test_data_survives_reopening_the_database(tmp_path):
    path = tmp_path / "sim.sqlite3"
    first = SqliteRepository(path)
    first.initialize()
    first.save_portfolio(PORTFOLIO)

    reopened = SqliteRepository(path)
    reopened.initialize()

    assert reopened.load_portfolio() == PORTFOLIO
