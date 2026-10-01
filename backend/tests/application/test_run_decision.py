import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from fakes import MARKET_DOWN, FakeAgent, FakeCalendar, FakeMarketData, FixedClock, decision
from trade_simulator.adapters.sqlite_repository import SqliteRepository
from trade_simulator.application.activity import ActivityFeed
from trade_simulator.application.run_decision import DecisionRunner
from trade_simulator.application.run_guard import RunGuard
from trade_simulator.core.decision_log import (
    DecisionRun,
    Finding,
    RunCost,
    RunStatus,
    RunTrigger,
    Watchlist,
    WatchlistEntry,
)
from trade_simulator.core.errors import AgentError, MarketClosedError, RunInProgressError
from trade_simulator.application.ports import AgentUsage, Performance
from trade_simulator.core.exchange_profile import US_PROFILE
from trade_simulator.core.order import Order, Side
from trade_simulator.core.portfolio import Portfolio, Position
from trade_simulator.core.run_budget import DECISION_RUN_LIMITS
from trade_simulator.core.trading_rules import OrderResult, OrderStatus, RejectionReason

NOW = datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc)
WATCHLIST = Watchlist(
    entries=(WatchlistEntry("AAPL", "Earnings"), WatchlistEntry("MSFT", "Cloud")),
    refreshed_at=NOW,
)


@pytest.fixture
def repo(tmp_path):
    repository = SqliteRepository(tmp_path / "sim.sqlite3")
    repository.initialize()
    repository.save_watchlist(WATCHLIST)
    return repository


def make_runner(repo, agent, market=None, calendar=None, guard=None, activity=None):
    return DecisionRunner(
        repository=repo,
        market_data=market or FakeMarketData({"AAPL": "200", "MSFT": "400"}),
        calendar=calendar or FakeCalendar(open_=True),
        agent=agent,
        profile=US_PROFILE,
        guard=guard or RunGuard(),
        clock=FixedClock(NOW),
        id_factory=lambda: "run-1",
        activity=activity or ActivityFeed(clock=FixedClock(NOW)),
    )


def test_live_feed_shows_the_run_and_each_rules_check(repo):
    feed = ActivityFeed(clock=FixedClock(NOW))
    agent = FakeAgent(decision([Order("AAPL", Side.BUY, 5, "x"), Order("AAPL", Side.BUY, 40, "y")]))

    run(make_runner(repo, agent, activity=feed))

    texts = [e.text for e in feed.snapshot().events]
    assert texts[0].startswith("Started")
    assert "BUY 5 AAPL: executed at 200 + 1 fee" in texts
    assert any(t.startswith("BUY 40 AAPL: rejected") for t in texts)
    assert texts[-1] == "Finished: 1 executed, 1 rejected"
    assert feed.snapshot().active is False


def test_live_feed_shows_a_failure(repo):
    feed = ActivityFeed(clock=FixedClock(NOW))

    run(make_runner(repo, FakeAgent(error=RuntimeError("boom")), activity=feed))

    assert feed.snapshot().events[-1].text == "Failed: boom"


def run(runner, trigger=RunTrigger.MANUAL):
    return asyncio.run(runner.run(trigger))


def test_completed_run_executes_valid_orders_and_logs_everything(repo):
    finding = Finding("AAPL", "Beat earnings", ("https://news/aapl",))
    agent = FakeAgent(decision([Order("AAPL", Side.BUY, 5, "Strong quarter")], [finding]))

    result = run(make_runner(repo, agent))

    assert result.status is RunStatus.COMPLETED
    assert result.order_results[0].status is OrderStatus.EXECUTED
    assert result.findings == (finding,)
    assert result.trace_id == "trace_1"
    assert result.cost.input_tokens == 100 and result.cost.searches == 2
    assert repo.get_run("run-1") == result
    assert repo.load_portfolio().quantity_of("AAPL") == 5
    assert repo.load_portfolio().cash == Decimal("8999")


def test_agent_sees_portfolio_prices_watchlist_and_limits(repo):
    agent = FakeAgent(decision())

    run(make_runner(repo, agent))

    [context] = agent.decision_contexts
    assert context.portfolio == Portfolio.starting(Decimal("10000"))
    assert context.prices == {"AAPL": Decimal("200"), "MSFT": Decimal("400")}
    assert context.watchlist == WATCHLIST
    assert context.limits == DECISION_RUN_LIMITS
    assert context.profile == US_PROFILE
    assert context.market_overview is None  # no refresh has written one yet


def test_agent_sees_the_latest_market_overview_from_a_refresh(repo):
    refresh = DecisionRun(
        id="refresh-1",
        trigger=RunTrigger.REFRESH,
        started_at=NOW,
        finished_at=NOW,
        status=RunStatus.COMPLETED,
        failure_reason=None,
        findings=(Finding("MARKET", "Chips weak on tariff news", ("https://m",)),),
        order_results=(),
        cost=RunCost(0, 0, 0),
        trace_id=None,
    )
    repo.save_run(refresh, None)
    agent = FakeAgent(decision())

    run(make_runner(repo, agent))

    [context] = agent.decision_contexts
    assert context.market_overview.summary == "Chips weak on tariff news"
    assert context.market_overview.as_of == NOW


def test_prices_cover_holdings_that_left_the_watchlist(repo):
    repo.save_portfolio(Portfolio(Decimal("5000"), {"TSLA": Position("TSLA", 2, Decimal("250"))}))
    market = FakeMarketData({"AAPL": "200", "MSFT": "400", "TSLA": "260"})

    run(make_runner(repo, FakeAgent(decision()), market=market))

    assert sorted(market.requested[0]) == ["AAPL", "MSFT", "SPY", "TSLA"]  # SPY for the performance line (D42)


def test_agent_sees_why_it_bought_its_holdings_and_how_it_is_doing(repo):
    repo.save_benchmark_start("SPY", Decimal("500"), NOW)
    market = FakeMarketData({"AAPL": "200", "MSFT": "400", "SPY": "510"})
    bought = OrderResult(Order("AAPL", Side.BUY, 5, "Strong quarter"), OrderStatus.EXECUTED, Decimal("200"), Decimal("1"))
    earlier = DecisionRun("run-0", RunTrigger.MANUAL, NOW, NOW, RunStatus.COMPLETED, None, (), (bought,), RunCost(0, 0, 0), None)
    repo.save_run(earlier, Portfolio(Decimal("8999"), {"AAPL": Position("AAPL", 5, Decimal("200"))}))
    agent = FakeAgent(decision())

    run(make_runner(repo, agent, market=market))

    [context] = agent.decision_contexts
    [buy] = context.holding_buys["AAPL"]
    assert (buy.quantity, buy.price, buy.reason) == (5, Decimal("200"), "Strong quarter")
    assert context.performance == Performance(NOW, Decimal("-0.01"), "SPY", Decimal("2"))
    assert "SPY" not in context.prices


def test_agent_gets_no_performance_before_benchmark_tracking_began(repo):
    agent = FakeAgent(decision())

    run(make_runner(repo, agent))

    [context] = agent.decision_contexts
    assert context.performance is None
    assert context.holding_buys == {}


def test_rule_breaking_order_is_rejected_and_logged(repo):
    agent = FakeAgent(decision([Order("AAPL", Side.BUY, 40, "All in")]))

    result = run(make_runner(repo, agent))

    assert result.status is RunStatus.COMPLETED
    assert result.order_results[0].rejection_reason is RejectionReason.EXCEEDS_POSITION_CAP
    assert repo.load_portfolio() == Portfolio.starting(Decimal("10000"))


def test_market_closed_refuses_to_run_and_logs_nothing(repo):
    with pytest.raises(MarketClosedError) as error:
        run(make_runner(repo, FakeAgent(decision()), calendar=FakeCalendar(open_=False)))

    assert error.value.next_open > NOW
    assert repo.list_runs() == []


def test_missing_watchlist_logs_failed_run(tmp_path):
    empty = SqliteRepository(tmp_path / "empty.sqlite3")
    empty.initialize()
    agent = FakeAgent(decision())

    result = run(make_runner(empty, agent))

    assert result.status is RunStatus.FAILED
    assert "watchlist" in result.failure_reason.lower()
    assert agent.decision_contexts == []


def test_agent_failure_logs_failed_run_and_keeps_portfolio(repo):
    error = AgentError("Model timed out", trace_id="trace_x", usage=AgentUsage(50, 0, 1))
    result = run(make_runner(repo, FakeAgent(error=error)))

    assert result.status is RunStatus.FAILED
    assert result.failure_reason == "Model timed out"
    assert result.trace_id == "trace_x"
    assert result.cost.searches == 1
    assert repo.get_run("run-1") == result
    assert repo.load_portfolio() == Portfolio.starting(Decimal("10000"))


def test_market_data_failure_logs_failed_run(repo):
    result = run(make_runner(repo, FakeAgent(decision()), market=FakeMarketData(error=MARKET_DOWN)))

    assert result.status is RunStatus.FAILED
    assert "Finnhub" in result.failure_reason


def test_manual_run_while_another_run_is_active_is_refused(repo):
    guard = RunGuard()
    assert guard.try_acquire()

    with pytest.raises(RunInProgressError):
        run(make_runner(repo, FakeAgent(decision()), guard=guard))


def test_scheduled_run_while_another_run_is_active_is_logged_as_skipped(repo):
    guard = RunGuard()
    assert guard.try_acquire()
    agent = FakeAgent(decision())

    result = run(make_runner(repo, agent, guard=guard), RunTrigger.EVERY_15_MIN)

    assert result.status is RunStatus.SKIPPED
    assert repo.get_run("run-1").status is RunStatus.SKIPPED
    assert agent.decision_contexts == []


def test_guard_is_released_after_a_failed_run(repo):
    guard = RunGuard()
    run(make_runner(repo, FakeAgent(error=RuntimeError("boom")), guard=guard))

    assert guard.try_acquire()
