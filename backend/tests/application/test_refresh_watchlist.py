import asyncio
from datetime import datetime, timezone

import pytest

from fakes import MARKET_DOWN, FakeAgent, FakeUniverse, FixedClock, proposal
from trade_simulator.adapters.sqlite_repository import SqliteRepository
from trade_simulator.application.activity import ActivityFeed
from trade_simulator.application.refresh_watchlist import WatchlistRefresher
from trade_simulator.application.run_guard import RunGuard
from trade_simulator.core.decision_log import Finding, RunStatus, RunTrigger, Watchlist, WatchlistEntry
from trade_simulator.core.errors import RunInProgressError
from trade_simulator.core.exchange_profile import US_PROFILE
from trade_simulator.core.run_budget import REFRESH_RUN_LIMITS

NOW = datetime(2026, 9, 26, 20, 0, tzinfo=timezone.utc)  # Saturday: market closed
OLD = Watchlist(entries=(WatchlistEntry("IBM", "Old pick"),), refreshed_at=NOW)


@pytest.fixture
def repo(tmp_path):
    repository = SqliteRepository(tmp_path / "sim.sqlite3")
    repository.initialize()
    return repository


def make_refresher(repo, agent, universe=None, guard=None, activity=None):
    return WatchlistRefresher(
        repository=repo,
        agent=agent,
        universe=universe or FakeUniverse(),
        profile=US_PROFILE,
        guard=guard or RunGuard(),
        clock=FixedClock(NOW),
        id_factory=lambda: "refresh-1",
        activity=activity or ActivityFeed(clock=FixedClock(NOW)),
    )


def test_live_feed_shows_the_refresh_result(repo):
    feed = ActivityFeed(clock=FixedClock(NOW))
    agent = FakeAgent(proposal=proposal([WatchlistEntry("AAPL", "ok"), WatchlistEntry("GME", "meme")]))

    refresh(make_refresher(repo, agent, activity=feed))

    texts = [e.text for e in feed.snapshot().events]
    assert texts[0].startswith("Started")
    assert "GME not added: not in the S&P 500" in texts
    assert texts[-1] == "Finished: 1 stocks on the watchlist"


def refresh(refresher):
    return asyncio.run(refresher.refresh())


def test_refresh_saves_new_watchlist_and_logs_run_even_when_market_closed(repo):
    overview = Finding("MARKET", "Tech leading this week")
    agent = FakeAgent(
        proposal=proposal(
            [WatchlistEntry("AAPL", "Earnings", ("https://a",)), WatchlistEntry("MSFT", "Cloud")],
            [overview],
        )
    )

    result = refresh(make_refresher(repo, agent))

    assert result.status is RunStatus.COMPLETED
    assert result.trigger is RunTrigger.REFRESH
    assert result.findings == (overview,)
    assert result.cost.searches == 12
    assert repo.load_watchlist() == Watchlist(
        entries=(WatchlistEntry("AAPL", "Earnings", ("https://a",)), WatchlistEntry("MSFT", "Cloud")),
        refreshed_at=NOW,
    )
    assert repo.get_run("refresh-1") == result


def test_agent_gets_stock_pool_limits_and_current_watchlist(repo):
    repo.save_watchlist(OLD)
    agent = FakeAgent(proposal=proposal([WatchlistEntry("AAPL", "x")]))

    refresh(make_refresher(repo, agent))

    [context] = agent.refresh_contexts
    assert context.stock_pool == frozenset({"AAPL", "MSFT", "NVDA"})
    assert context.limits == REFRESH_RUN_LIMITS
    assert context.current_watchlist == OLD


def test_picks_outside_the_stock_pool_are_dropped_with_a_warning(repo):
    agent = FakeAgent(proposal=proposal([WatchlistEntry("AAPL", "ok"), WatchlistEntry("GME", "meme")]))

    result = refresh(make_refresher(repo, agent))

    assert repo.load_watchlist().symbols == {"AAPL"}
    [warning] = result.findings
    assert warning.symbol == "GME"
    assert "S&P 500" in warning.warnings[0]


def test_extra_picks_beyond_20_are_dropped(repo):
    symbols = [f"S{i}" for i in range(25)]
    agent = FakeAgent(proposal=proposal([WatchlistEntry(s, "r") for s in symbols]))

    refresh(make_refresher(repo, agent, universe=FakeUniverse(symbols)))

    assert len(repo.load_watchlist().entries) == 20


def test_no_valid_picks_fails_and_keeps_old_watchlist(repo):
    repo.save_watchlist(OLD)
    agent = FakeAgent(proposal=proposal([WatchlistEntry("GME", "meme")]))

    result = refresh(make_refresher(repo, agent))

    assert result.status is RunStatus.FAILED
    assert repo.load_watchlist() == OLD


def test_agent_failure_fails_and_keeps_old_watchlist(repo):
    repo.save_watchlist(OLD)

    result = refresh(make_refresher(repo, FakeAgent(error=RuntimeError("model down"))))

    assert result.status is RunStatus.FAILED
    assert repo.load_watchlist() == OLD


def test_stock_pool_unavailable_fails_run(repo):
    result = refresh(make_refresher(repo, FakeAgent(), universe=FakeUniverse(error=MARKET_DOWN)))

    assert result.status is RunStatus.FAILED


def test_refresh_is_refused_while_another_run_is_active(repo):
    guard = RunGuard()
    guard.try_acquire()

    with pytest.raises(RunInProgressError):
        refresh(make_refresher(repo, FakeAgent(), guard=guard))
