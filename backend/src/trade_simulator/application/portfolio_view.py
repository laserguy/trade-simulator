"""Use case: the portfolio at current prices, compared with the exchange's benchmark index (D23)."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from trade_simulator.application.portfolio_setup import load_or_create_portfolio
from trade_simulator.application.ports import MarketData, Repository
from trade_simulator.core.errors import MarketDataError
from trade_simulator.core.exchange_profile import ExchangeProfile

logger = logging.getLogger(__name__)
HUNDRED = Decimal(100)


@dataclass(frozen=True)
class PositionView:
    symbol: str
    quantity: int
    average_cost: Decimal
    price: Decimal | None
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    weight_percent: Decimal | None


@dataclass(frozen=True)
class PortfolioSnapshot:
    currency: str
    cash: Decimal
    positions: tuple[PositionView, ...]
    total_value: Decimal | None  # None when a price is missing
    starting_capital: Decimal
    return_percent: Decimal | None
    benchmark_symbol: str
    benchmark_price: Decimal | None
    benchmark_return_percent: Decimal | None
    tracking_since: datetime | None


class PortfolioViewer:
    def __init__(
        self,
        *,
        repository: Repository,
        market_data: MarketData,
        profile: ExchangeProfile,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        price_ttl: timedelta = timedelta(seconds=60),
    ) -> None:
        self._repository = repository
        self._market_data = market_data
        self._profile = profile
        self._clock = clock
        self._price_ttl = price_ttl
        self._cache: tuple[datetime, frozenset[str], dict[str, Decimal]] | None = None

    def snapshot(self) -> PortfolioSnapshot:
        portfolio = load_or_create_portfolio(self._repository, self._profile)
        benchmark = self._profile.benchmark_symbol
        prices = self._prices(frozenset(portfolio.positions) | {benchmark})

        positions = tuple(
            _position_view(symbol, p.quantity, p.average_cost, prices.get(symbol))
            for symbol, p in sorted(portfolio.positions.items())
        )
        values = [p.market_value for p in positions]
        total = None if None in values else portfolio.cash + sum(values, Decimal("0"))
        if total:
            positions = tuple(_with_weight(p, total) for p in positions)

        start = self._repository.load_benchmark_start()
        if start is None and benchmark in prices:
            self._repository.save_benchmark_start(benchmark, prices[benchmark], self._clock())
            start = self._repository.load_benchmark_start()

        capital = self._profile.starting_capital
        return PortfolioSnapshot(
            currency=self._profile.currency,
            cash=portfolio.cash,
            positions=positions,
            total_value=total,
            starting_capital=capital,
            return_percent=_change_percent(capital, total),
            benchmark_symbol=benchmark,
            benchmark_price=prices.get(benchmark),
            benchmark_return_percent=_change_percent(start.price, prices.get(benchmark)) if start else None,
            tracking_since=start.started_at if start else None,
        )

    def _prices(self, symbols: frozenset[str]) -> dict[str, Decimal]:
        """Prices are cached briefly: the UI refreshes often, Finnhub's free tier allows 60 calls/min."""
        now = self._clock()
        if self._cache and self._cache[1] == symbols and now - self._cache[0] < self._price_ttl:
            return self._cache[2]
        try:
            prices = self._market_data.get_prices(sorted(symbols))
        except MarketDataError as exc:
            logger.warning("Prices unavailable for portfolio view: %s", exc)
            return {}
        self._cache = (now, symbols, prices)
        return prices


def _position_view(symbol: str, quantity: int, average_cost: Decimal, price: Decimal | None) -> PositionView:
    if price is None:
        return PositionView(symbol, quantity, average_cost, None, None, None, None)
    value = quantity * price
    return PositionView(symbol, quantity, average_cost, price, value, value - quantity * average_cost, None)


def _with_weight(position: PositionView, total: Decimal) -> PositionView:
    return PositionView(
        position.symbol,
        position.quantity,
        position.average_cost,
        position.price,
        position.market_value,
        position.unrealized_pnl,
        position.market_value / total * HUNDRED,
    )


def _change_percent(start: Decimal, now: Decimal | None) -> Decimal | None:
    if now is None or not start:
        return None
    return (now - start) / start * HUNDRED
