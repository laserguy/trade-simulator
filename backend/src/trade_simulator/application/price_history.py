"""Use case: daily price history for charts (D36, D37), cached locally and topped up at most twice a day.

The provider is whatever `PriceHistorySource` is configured (D38). If it fails or its hourly limit is
reached, cached bars are served instead.
"""

import logging
from collections import deque
from collections.abc import Callable, Iterable
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from trade_simulator.application.ports import DailyBar, PriceHistorySource, PriceSync, Repository
from trade_simulator.core.errors import MarketDataError
from trade_simulator.core.exchange_profile import ExchangeProfile

logger = logging.getLogger(__name__)

FIRST_FETCH_DAYS = 400  # a year of charts plus margin
RECHECK_AFTER = timedelta(hours=12)


class PriceHistoryService:
    def __init__(
        self,
        *,
        repository: Repository,
        source: PriceHistorySource,
        profile: ExchangeProfile,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._repository = repository
        self._source = source
        self._exchange = profile.code
        self._timezone = ZoneInfo(profile.timezone)
        self._clock = clock
        self._recent_requests: deque[datetime] = deque()

    def history(self, symbol: str, days: int) -> list[DailyBar]:
        """Bars for the last `days` calendar days, fetching missing ones from the provider if due."""
        self._refresh_if_due(symbol)
        return self._repository.load_daily_bars(self._exchange, symbol, self._today() - timedelta(days=days))

    def cached_trends(self, symbols: Iterable[str], days: int) -> dict[str, list[Decimal]]:
        """Adjusted closes from the cache only: never calls the provider, so the page stays fast."""
        since = self._today() - timedelta(days=days)
        return {s: [b.adj_close for b in self._repository.load_daily_bars(self._exchange, s, since)] for s in symbols}

    def stale_symbols(self, symbols: Iterable[str]) -> list[str]:
        return [s for s in symbols if self._is_due(self._repository.load_price_sync(self._exchange, s))]

    def refresh(self, symbols: Iterable[str]) -> None:
        """Top up several symbols, e.g. in the background after the watchlist changes."""
        for symbol in symbols:
            self._refresh_if_due(symbol)

    def _refresh_if_due(self, symbol: str) -> None:
        sync = self._repository.load_price_sync(self._exchange, symbol)
        if not self._is_due(sync) or not self._may_request():
            return
        since = sync.last_day + timedelta(days=1) if sync and sync.last_day else self._today() - timedelta(days=FIRST_FETCH_DAYS)
        try:
            bars = self._source.daily_bars(symbol, since)
        except MarketDataError as exc:
            logger.warning("Price history unavailable for %s: %s", symbol, exc)
            return
        if bars:
            self._repository.save_daily_bars(self._exchange, symbol, bars, self._source.name)
        days = [b.day for b in bars]
        self._repository.save_price_sync(
            PriceSync(
                exchange=self._exchange,
                symbol=symbol,
                first_day=min([d for d in (sync.first_day if sync else None, *days) if d], default=None),
                last_day=max([d for d in (sync.last_day if sync else None, *days) if d], default=None),
                last_checked_at=self._clock(),
            )
        )

    def _is_due(self, sync: PriceSync | None) -> bool:
        return sync is None or self._clock() - sync.last_checked_at >= RECHECK_AFTER

    def _may_request(self) -> bool:
        """Stay within the provider's declared hourly limit."""
        limit = self._source.max_requests_per_hour
        now = self._clock()
        while self._recent_requests and now - self._recent_requests[0] >= timedelta(hours=1):
            self._recent_requests.popleft()
        if limit is not None and len(self._recent_requests) >= limit:
            return False
        self._recent_requests.append(now)
        return True

    def _today(self) -> date:
        return self._clock().astimezone(self._timezone).date()
