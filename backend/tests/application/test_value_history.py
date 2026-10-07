from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from fakes import MARKET_DOWN, FakeMarketData, FixedClock
from trade_simulator.adapters.sqlite_repository import SqliteRepository
from trade_simulator.application.portfolio_view import PortfolioViewer
from trade_simulator.application.ports import ValueSnapshot
from trade_simulator.application.value_history import ValueHistory
from trade_simulator.core.exchange_profile import US_PROFILE
from trade_simulator.core.portfolio import Portfolio, Position

NOW = datetime(2026, 9, 28, 20, 0, tzinfo=timezone.utc)


@pytest.fixture
def repo(tmp_path):
    repository = SqliteRepository(tmp_path / "sim.sqlite3")
    repository.initialize()
    return repository


def make(repo, market, clock):
    viewer = PortfolioViewer(repository=repo, market_data=market, profile=US_PROFILE, clock=clock, price_ttl=timedelta(0))
    return ValueHistory(repository=repo, viewer=viewer, profile=US_PROFILE, clock=clock)


def test_records_value_and_benchmark_as_comparable_dollar_lines(repo):
    clock = FixedClock(NOW)
    history = make(repo, FakeMarketData({"SPY": "500"}), clock)
    history.record()

    repo.save_portfolio(Portfolio(Decimal("9000"), {"AAPL": Position("AAPL", 10, Decimal("100"))}))
    clock.now = NOW + timedelta(days=1)
    make(repo, FakeMarketData({"SPY": "525", "AAPL": "150"}), clock).record()

    points = history.points()
    assert [(p.total_value, p.benchmark_value) for p in points] == [
        (Decimal("10000"), Decimal("10000")),
        (Decimal("10500"), Decimal("10500")),  # SPY +5% on the same $10,000 start
    ]
    assert points[1].at == NOW + timedelta(days=1)


def test_each_point_keeps_the_cash_held_then(repo):
    repo.save_portfolio(Portfolio(Decimal("9000"), {"AAPL": Position("AAPL", 10, Decimal("100"))}))

    make(repo, FakeMarketData({"SPY": "500", "AAPL": "100"}), FixedClock(NOW)).record()

    [snapshot] = repo.load_value_snapshots()
    assert snapshot.cash == Decimal("9000")


def test_nothing_is_recorded_when_prices_are_unavailable(repo):
    history = make(repo, FakeMarketData(error=MARKET_DOWN), FixedClock(NOW))

    history.record()

    assert history.points() == []


def test_now_is_the_live_point_and_is_not_saved(repo):
    clock = FixedClock(NOW)
    make(repo, FakeMarketData({"SPY": "500"}), clock).record()
    repo.save_portfolio(Portfolio(Decimal("9000"), {"AAPL": Position("AAPL", 10, Decimal("100"))}))
    clock.now = NOW + timedelta(days=1)
    history = make(repo, FakeMarketData({"SPY": "510", "AAPL": "120"}), clock)

    now = history.now()

    assert now is not None
    assert (now.at, now.total_value, now.benchmark_value) == (NOW + timedelta(days=1), Decimal("10200"), Decimal("10200"))
    assert len(history.points()) == 1


def test_no_now_point_when_prices_are_unavailable(repo):
    make(repo, FakeMarketData({"SPY": "500"}), FixedClock(NOW)).record()

    assert make(repo, FakeMarketData(error=MARKET_DOWN), FixedClock(NOW)).now() is None


def saved(repo, *moments):
    repo.save_benchmark_start("SPY", Decimal("500"), moments[0])
    for i, at in enumerate(moments):
        repo.save_value_snapshot(ValueSnapshot(at, Decimal(10000 + i), Decimal("500")))


def test_points_can_be_limited_to_recent_days(repo):
    saved(repo, NOW - timedelta(days=10), NOW - timedelta(days=3), NOW)

    points = make(repo, FakeMarketData({"SPY": "500"}), FixedClock(NOW)).points(days=7)

    assert [p.at for p in points] == [NOW - timedelta(days=3), NOW]


def test_daily_points_keep_the_last_point_of_each_exchange_day(repo):
    # 20:00 UTC on Sep 28 is 4 PM in New York; 02:00 UTC on Sep 29 is still Sep 28 there.
    morning = datetime(2026, 9, 28, 14, 0, tzinfo=timezone.utc)
    close = datetime(2026, 9, 28, 20, 0, tzinfo=timezone.utc)
    late = datetime(2026, 9, 29, 2, 0, tzinfo=timezone.utc)
    next_day = datetime(2026, 9, 29, 15, 0, tzinfo=timezone.utc)
    saved(repo, morning, close, late, next_day)

    points = make(repo, FakeMarketData({"SPY": "500"}), FixedClock(next_day)).points(daily=True)

    assert [p.at for p in points] == [late, next_day]


def test_no_now_point_before_tracking_starts(repo):
    # The first snapshot sets the benchmark start, so with no prices nothing is tracked yet.
    assert make(repo, FakeMarketData(error=MARKET_DOWN), FixedClock(NOW)).now() is None
