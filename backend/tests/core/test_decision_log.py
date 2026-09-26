from datetime import datetime, timezone

import pytest

from trade_simulator.core.decision_log import Watchlist, WatchlistEntry
from trade_simulator.core.errors import DomainError

NOW = datetime(2026, 9, 28, 13, 30, tzinfo=timezone.utc)


def test_watchlist_exposes_its_symbols():
    watchlist = Watchlist(
        entries=(WatchlistEntry("aapl", "Strong earnings"), WatchlistEntry("MSFT", "Cloud growth")),
        refreshed_at=NOW,
    )

    assert watchlist.symbols == frozenset({"AAPL", "MSFT"})


def test_watchlist_rejects_duplicate_symbols():
    with pytest.raises(DomainError):
        Watchlist(
            entries=(WatchlistEntry("AAPL", "a"), WatchlistEntry("aapl", "b")),
            refreshed_at=NOW,
        )


def test_watchlist_rejects_more_than_20_stocks():
    entries = tuple(WatchlistEntry(f"S{i}", "reason") for i in range(21))

    with pytest.raises(DomainError):
        Watchlist(entries=entries, refreshed_at=NOW)
