from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from fakes import MARKET_DOWN, FakeMarketData, FixedClock
from trade_simulator.adapters.sqlite_repository import SqliteRepository
from trade_simulator.application.portfolio_view import PortfolioViewer
from trade_simulator.core.exchange_profile import US_PROFILE
from trade_simulator.core.portfolio import Portfolio, Position

NOW = datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc)


@pytest.fixture
def repo(tmp_path):
    repository = SqliteRepository(tmp_path / "sim.sqlite3")
    repository.initialize()
    return repository


def make(repo, market, clock=None):
    return PortfolioViewer(repository=repo, market_data=market, profile=US_PROFILE, clock=clock or FixedClock(NOW))


def test_first_view_starts_benchmark_tracking_at_current_spy_price(repo):
    snapshot = make(repo, FakeMarketData({"SPY": "500"})).snapshot()

    assert snapshot.total_value == Decimal("10000")
    assert snapshot.return_percent == Decimal("0")
    assert snapshot.benchmark_symbol == "SPY"
    assert snapshot.benchmark_return_percent == Decimal("0")
    assert snapshot.tracking_since == NOW


def test_returns_compare_portfolio_with_benchmark(repo):
    make(repo, FakeMarketData({"SPY": "500"})).snapshot()
    repo.save_portfolio(Portfolio(Decimal("9000"), {"AAPL": Position("AAPL", 10, Decimal("100"))}))

    later = FixedClock(NOW + timedelta(days=30))
    snapshot = make(repo, FakeMarketData({"SPY": "525", "AAPL": "150"}), clock=later).snapshot()

    assert snapshot.total_value == Decimal("10500")
    assert snapshot.return_percent == Decimal("5")
    assert snapshot.benchmark_return_percent == Decimal("5")
    [aapl] = snapshot.positions
    assert aapl.market_value == Decimal("1500")
    assert aapl.unrealized_pnl == Decimal("500")
    assert round(aapl.weight_percent, 2) == Decimal("14.29")


def test_prices_are_cached_briefly_to_protect_rate_limit(repo):
    market = FakeMarketData({"SPY": "500"})
    viewer = make(repo, market)

    viewer.snapshot()
    viewer.snapshot()

    assert len(market.requested) == 1


def test_market_data_failure_still_shows_cash_and_holdings(repo):
    repo.save_portfolio(Portfolio(Decimal("9000"), {"AAPL": Position("AAPL", 10, Decimal("100"))}))

    snapshot = make(repo, FakeMarketData(error=MARKET_DOWN)).snapshot()

    assert snapshot.cash == Decimal("9000")
    assert snapshot.total_value is None
    assert snapshot.positions[0].price is None
    assert snapshot.benchmark_return_percent is None
