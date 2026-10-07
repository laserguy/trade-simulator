"""Use case: record portfolio value over time and compare it with the benchmark (D23, D33)."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from trade_simulator.application.portfolio_view import PortfolioViewer
from trade_simulator.application.ports import Repository, ValueSnapshot
from trade_simulator.core.exchange_profile import ExchangeProfile

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ValuePoint:
    """One chart point. `benchmark_value` is what the starting capital would be worth in the benchmark,
    so both lines are in the same currency and start at the same place."""

    at: datetime
    total_value: Decimal
    benchmark_value: Decimal


class ValueHistory:
    def __init__(
        self,
        *,
        repository: Repository,
        viewer: PortfolioViewer,
        profile: ExchangeProfile,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._repository = repository
        self._viewer = viewer
        self._profile = profile
        self._clock = clock

    def record(self) -> None:
        """Save a point now. Skipped (not an error) when prices are unavailable."""
        snapshot = self._viewer.snapshot()
        if snapshot.total_value is None or snapshot.benchmark_price is None:
            logger.info("Value history point skipped: prices unavailable")
            return
        self._repository.save_value_snapshot(
            ValueSnapshot(self._clock(), snapshot.total_value, snapshot.benchmark_price, snapshot.cash)
        )

    def now(self) -> ValuePoint | None:
        """The live point that ends the chart (D32): same prices as the Home numbers, never saved.
        None when prices are unavailable or tracking hasn't started."""
        snapshot = self._viewer.snapshot()
        start = self._repository.load_benchmark_start()
        if snapshot.total_value is None or snapshot.benchmark_price is None or start is None:
            return None
        capital = self._profile.starting_capital
        return ValuePoint(self._clock(), snapshot.total_value, capital * snapshot.benchmark_price / start.price)

    def since(self, days: int | None) -> datetime | None:
        """Start of a chart period of `days` days back from now (None = all history)."""
        return None if days is None else self._clock() - timedelta(days=days)

    def points(self, days: int | None = None, daily: bool = False) -> list[ValuePoint]:
        """Saved points, optionally only the last `days` days, and with `daily` only the last point
        of each day in the exchange's timezone, so long periods stay readable (D32)."""
        start = self._repository.load_benchmark_start()
        if start is None:
            return []
        since = self.since(days)
        snapshots = [s for s in self._repository.load_value_snapshots() if since is None or s.at >= since]
        if daily:
            zone = ZoneInfo(self._profile.timezone)
            last_of_day = {s.at.astimezone(zone).date(): s for s in snapshots}
            snapshots = list(last_of_day.values())
        capital = self._profile.starting_capital
        return [ValuePoint(s.at, s.total_value, capital * s.benchmark_price / start.price) for s in snapshots]
