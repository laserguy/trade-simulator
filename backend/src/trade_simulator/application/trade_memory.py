"""What the Trading Agent is told about its own past at the start of a run (D42)."""

from collections.abc import Iterable, Mapping
from decimal import Decimal

from trade_simulator.application.ports import BenchmarkStart, ExecutedTrade, Performance
from trade_simulator.core.exchange_profile import ExchangeProfile
from trade_simulator.core.order import Side
from trade_simulator.core.portfolio import Portfolio

HUNDRED = Decimal(100)


def open_position_buys(trades: Iterable[ExecutedTrade]) -> dict[str, tuple[ExecutedTrade, ...]]:
    """The buys behind each stock still held. `trades` are oldest first; selling a stock completely
    closes the position, so earlier buys no longer count."""
    held: dict[str, int] = {}
    buys: dict[str, list[ExecutedTrade]] = {}
    for trade in trades:
        if trade.side is Side.BUY:
            held[trade.symbol] = held.get(trade.symbol, 0) + trade.quantity
            buys.setdefault(trade.symbol, []).append(trade)
        else:
            held[trade.symbol] = held.get(trade.symbol, 0) - trade.quantity
            if held[trade.symbol] <= 0:
                held.pop(trade.symbol)
                buys.pop(trade.symbol, None)
    return {symbol: tuple(symbol_buys) for symbol, symbol_buys in buys.items()}


def performance_since_start(
    portfolio: Portfolio,
    prices: Mapping[str, Decimal],
    profile: ExchangeProfile,
    start: BenchmarkStart | None,
    benchmark_price: Decimal | None,
) -> Performance | None:
    """None until benchmark tracking has begun, or when a needed price is missing."""
    if start is None or benchmark_price is None or any(symbol not in prices for symbol in portfolio.positions):
        return None
    capital = profile.starting_capital
    return Performance(
        since=start.started_at,
        portfolio_percent=(portfolio.total_value(prices) - capital) / capital * HUNDRED,
        benchmark_symbol=start.symbol,
        benchmark_percent=(benchmark_price - start.price) / start.price * HUNDRED,
    )
