"""Use case: the watchlist as table rows with price, today's change and holding (D30)."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from trade_simulator.application.ports import Quote, QuoteSource, Repository
from trade_simulator.core.errors import MarketDataError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WatchlistRow:
    symbol: str
    reason: str
    sources: tuple[str, ...]
    price: Decimal | None
    change_percent: Decimal | None
    held_quantity: int


@dataclass(frozen=True)
class WatchlistView:
    refreshed_at: datetime
    rows: tuple[WatchlistRow, ...]


class WatchlistViewer:
    def __init__(
        self,
        *,
        repository: Repository,
        quotes: QuoteSource,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        quote_ttl: timedelta = timedelta(seconds=60),
    ) -> None:
        self._repository = repository
        self._quotes = quotes
        self._clock = clock
        self._quote_ttl = quote_ttl
        self._cache: tuple[datetime, frozenset[str], dict[str, Quote]] | None = None

    def view(self) -> WatchlistView | None:
        watchlist = self._repository.load_watchlist()
        if watchlist is None:
            return None
        portfolio = self._repository.load_portfolio()
        quotes = self._get_quotes(watchlist.symbols)
        rows = []
        for entry in watchlist.entries:
            quote = quotes.get(entry.symbol)
            rows.append(
                WatchlistRow(
                    symbol=entry.symbol,
                    reason=entry.reason,
                    sources=entry.sources,
                    price=quote.price if quote else None,
                    change_percent=quote.change_percent if quote else None,
                    held_quantity=portfolio.quantity_of(entry.symbol) if portfolio else 0,
                )
            )
        return WatchlistView(refreshed_at=watchlist.refreshed_at, rows=tuple(rows))

    def _get_quotes(self, symbols: frozenset[str]) -> dict[str, Quote]:
        """Cached briefly: Finnhub's free tier allows 60 calls/min and the UI refreshes often."""
        now = self._clock()
        if self._cache and self._cache[1] == symbols and now - self._cache[0] < self._quote_ttl:
            return self._cache[2]
        try:
            quotes = self._quotes.get_quotes(sorted(symbols))
        except MarketDataError as exc:
            logger.warning("Quotes unavailable for watchlist: %s", exc)
            return {}
        self._cache = (now, symbols, quotes)
        return quotes
