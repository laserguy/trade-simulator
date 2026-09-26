"""Use case: record portfolio value over time and compare it with the benchmark (D23, D33)."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

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
        self._repository.save_value_snapshot(ValueSnapshot(self._clock(), snapshot.total_value, snapshot.benchmark_price))

    def points(self) -> list[ValuePoint]:
        start = self._repository.load_benchmark_start()
        if start is None:
            return []
        capital = self._profile.starting_capital
        return [
            ValuePoint(s.at, s.total_value, capital * s.benchmark_price / start.price)
            for s in self._repository.load_value_snapshots()
        ]
