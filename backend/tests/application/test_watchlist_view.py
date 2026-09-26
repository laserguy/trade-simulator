from datetime import datetime, timezone
from decimal import Decimal

import pytest

from fakes import MARKET_DOWN, FixedClock
from trade_simulator.adapters.sqlite_repository import SqliteRepository
from trade_simulator.application.ports import Quote
from trade_simulator.application.watchlist_view import WatchlistViewer
from trade_simulator.core.decision_log import Watchlist, WatchlistEntry
from trade_simulator.core.portfolio import Portfolio, Position

NOW = datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc)


class FakeQuotes:
    def __init__(self, quotes=None, error=None):
        self.quotes = quotes or {}
        self.error = error
        self.calls = 0

    def get_quotes(self, symbols):
        self.calls += 1
        if self.error:
            raise self.error
        return {s: self.quotes[s] for s in symbols if s in self.quotes}


@pytest.fixture
def repo(tmp_path):
    repository = SqliteRepository(tmp_path / "sim.sqlite3")
    repository.initialize()
    repository.save_watchlist(
        Watchlist((WatchlistEntry("AAPL", "Earnings", ("https://a",)), WatchlistEntry("MSFT", "Cloud")), NOW)
    )
    repository.save_portfolio(Portfolio(Decimal("9000"), {"AAPL": Position("AAPL", 5, Decimal("190"))}))
    return repository


def test_rows_show_price_change_holding_and_reason(repo):
    quotes = FakeQuotes({"AAPL": Quote("AAPL", Decimal("200"), Decimal("1.5"), Decimal("197"))})

    view = WatchlistViewer(repository=repo, quotes=quotes, clock=FixedClock(NOW)).view()

    aapl, msft = view.rows
    assert (aapl.symbol, aapl.price, aapl.change_percent, aapl.held_quantity) == ("AAPL", Decimal("200"), Decimal("1.5"), 5)
    assert aapl.reason == "Earnings" and aapl.sources == ("https://a",)
    assert (msft.price, msft.held_quantity) == (None, 0)
    assert view.refreshed_at == NOW


def test_no_watchlist_gives_none(tmp_path):
    empty = SqliteRepository(tmp_path / "e.sqlite3")
    empty.initialize()

    assert WatchlistViewer(repository=empty, quotes=FakeQuotes(), clock=FixedClock(NOW)).view() is None


def test_quotes_are_cached_briefly(repo):
    quotes = FakeQuotes()
    viewer = WatchlistViewer(repository=repo, quotes=quotes, clock=FixedClock(NOW))

    viewer.view()
    viewer.view()

    assert quotes.calls == 1


def test_price_failure_still_lists_the_stocks(repo):
    view = WatchlistViewer(repository=repo, quotes=FakeQuotes(error=MARKET_DOWN), clock=FixedClock(NOW)).view()

    assert [r.symbol for r in view.rows] == ["AAPL", "MSFT"]
    assert view.rows[0].price is None
