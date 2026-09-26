from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from fakes import MARKET_DOWN, FakeMarketData, FixedClock
from trade_simulator.adapters.sqlite_repository import SqliteRepository
from trade_simulator.application.portfolio_view import PortfolioViewer
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


def test_nothing_is_recorded_when_prices_are_unavailable(repo):
    history = make(repo, FakeMarketData(error=MARKET_DOWN), FixedClock(NOW))

    history.record()

    assert history.points() == []
