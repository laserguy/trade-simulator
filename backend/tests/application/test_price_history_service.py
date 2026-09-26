from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from fakes import MARKET_DOWN, FixedClock
from trade_simulator.adapters.sqlite_repository import SqliteRepository
from trade_simulator.application.ports import DailyBar
from trade_simulator.application.price_history import PriceHistoryService
from trade_simulator.core.exchange_profile import US_PROFILE

NOW = datetime(2026, 9, 28, 22, 0, tzinfo=timezone.utc)  # Monday evening, after the close


def bar(day, close):
    price = Decimal(str(close))
    return DailyBar(day, price, price, price, price, price, 100)


class FakeSource:
    name = "fake"
    max_requests_per_hour = 50

    def __init__(self, bars=None, error=None):
        self.bars = bars or {}
        self.error = error
        self.calls = []

    def daily_bars(self, symbol, since):
        self.calls.append((symbol, since))
        if self.error:
            raise self.error
        return [b for b in self.bars.get(symbol, []) if b.day >= since]


@pytest.fixture
def repo(tmp_path):
    repository = SqliteRepository(tmp_path / "sim.sqlite3")
    repository.initialize()
    return repository


def make(repo, source, clock=None):
    return PriceHistoryService(repository=repo, source=source, profile=US_PROFILE, clock=clock or FixedClock(NOW))


def fresh_bars():
    return {"NVDA": [bar(date(2026, 9, 1) + timedelta(days=i), 150 + i) for i in range(28)]}


def test_first_request_fetches_about_a_year_and_caches_it(repo):
    source = FakeSource(fresh_bars())

    bars = make(repo, source).history("NVDA", days=30)

    assert source.calls == [("NVDA", date(2025, 8, 24))]  # 400 days back
    assert bars[-1].adj_close == Decimal("177")
    assert repo.load_daily_bars("US", "NVDA", date(2026, 1, 1)) == fresh_bars()["NVDA"]


def test_second_request_soon_after_uses_the_cache(repo):
    source = FakeSource(fresh_bars())
    make(repo, source).history("NVDA", days=30)

    make(repo, source, FixedClock(NOW + timedelta(hours=2))).history("NVDA", days=30)

    assert len(source.calls) == 1


def test_next_day_only_the_missing_days_are_fetched(repo):
    source = FakeSource(fresh_bars())
    make(repo, source).history("NVDA", days=30)
    source.bars["NVDA"].append(bar(date(2026, 9, 29), 190))

    bars = make(repo, source, FixedClock(NOW + timedelta(days=1))).history("NVDA", days=30)

    assert source.calls[1] == ("NVDA", date(2026, 9, 29))  # day after the last stored bar
    assert bars[-1].adj_close == Decimal("190")


def test_period_limits_the_bars_returned(repo):
    bars = make(repo, FakeSource(fresh_bars())).history("NVDA", days=7)

    assert [b.day for b in bars] == [date(2026, 9, 21) + timedelta(days=i) for i in range(8)]


def test_provider_failure_falls_back_to_cached_bars(repo):
    make(repo, FakeSource(fresh_bars())).history("NVDA", days=30)

    bars = make(repo, FakeSource(error=MARKET_DOWN), FixedClock(NOW + timedelta(days=1))).history("NVDA", days=30)

    assert len(bars) == 28


def test_hourly_request_limit_is_respected(repo):
    source = FakeSource()
    source.max_requests_per_hour = 2
    service = make(repo, source)

    for symbol in ("A", "B", "C"):
        service.history(symbol, days=30)

    assert [c[0] for c in source.calls] == ["A", "B"]


def test_trends_come_from_the_cache_only(repo):
    source = FakeSource(fresh_bars())
    service = make(repo, source)

    assert service.cached_trends(["NVDA"], days=30) == {"NVDA": []}
    service.history("NVDA", days=30)

    trend = service.cached_trends(["NVDA"], days=30)["NVDA"]
    assert trend[0] == Decimal("150") and trend[-1] == Decimal("177")
    assert len(source.calls) == 1


def test_missing_symbols_lists_what_needs_fetching(repo):
    service = make(repo, FakeSource(fresh_bars()))
    service.history("NVDA", days=30)

    assert service.stale_symbols(["NVDA", "MSFT"]) == ["MSFT"]

