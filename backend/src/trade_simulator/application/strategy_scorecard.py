"""A strategy version's results, computed by code so the agent can't tell itself a better story (D43)."""

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal

from trade_simulator.application.ports import ExecutedTrade, ValueSnapshot
from trade_simulator.core.decision_log import DecisionRun, RunStatus
from trade_simulator.core.order import Side
from trade_simulator.core.portfolio import Portfolio
from trade_simulator.core.strategy import DEVIATION, StrategyVersion
from trade_simulator.core.strategy_review import ClosedTrade, HoldingResult, Scorecard
from trade_simulator.core.trading_rules import OrderResult, OrderStatus

HUNDRED = Decimal(100)
ZERO = Decimal(0)


def build_scorecard(
    *,
    version: StrategyVersion,
    runs: Sequence[DecisionRun],
    trades: Sequence[ExecutedTrade],
    snapshots: Sequence[ValueSnapshot],
    portfolio: Portfolio,
    prices: Mapping[str, Decimal],
    now: datetime,
) -> Scorecard:
    """`runs` are the runs that followed `version`; `trades` and `snapshots` are all of them, oldest first."""
    completed = [run for run in runs if run.status is RunStatus.COMPLETED]
    executed = [result for run in completed for result in run.order_results if result.status is OrderStatus.EXECUTED]
    start, end = _period_ends(snapshots, version.started_at, now)
    return Scorecard(
        period_start=version.started_at,
        period_end=now,
        portfolio_percent=_change(start.total_value, end.total_value) if start and end else ZERO,
        benchmark_percent=_change(start.benchmark_price, end.benchmark_price) if start and end else ZERO,
        trading_runs=len(completed),
        trades=len(executed),
        fees=sum((result.fee or ZERO for result in executed), ZERO),
        closed_trades=_closed_trades(completed, trades),
        holdings=_holdings(portfolio, prices),
        average_cash_percent=_average_cash(snapshots, version.started_at, now, portfolio, prices),
        followed_orders=sum(1 for result in executed if result.order.follows not in (None, DEVIATION)),
        deviations=sum(1 for result in executed if result.order.follows == DEVIATION),
    )


def _period_ends(
    snapshots: Sequence[ValueSnapshot], start: datetime, now: datetime
) -> tuple[ValueSnapshot | None, ValueSnapshot | None]:
    """The last point at or before the start (else the first after it), and the last point up to now."""
    before = [s for s in snapshots if s.at <= start]
    up_to_now = [s for s in snapshots if s.at <= now]
    first = before[-1] if before else next(iter(up_to_now), None)
    return first, (up_to_now[-1] if up_to_now else None)


def _closed_trades(runs: Iterable[DecisionRun], trades: Sequence[ExecutedTrade]) -> tuple[ClosedTrade, ...]:
    """Each sell in these runs, with its gain over the average cost at the time, after the fee."""
    cost_before_sale = _average_cost_before_each_sale(trades)
    return tuple(
        ClosedTrade(result.order.symbol, _gain(result, cost_before_sale[(run.id, result.order.symbol)]))
        for run in runs
        for result in run.order_results
        if result.status is OrderStatus.EXECUTED and result.order.side is Side.SELL
    )


def _average_cost_before_each_sale(trades: Sequence[ExecutedTrade]) -> dict[tuple[str, str], Decimal]:
    """Replays every trade (sells come before buys within a run, D6) to find the cost basis of each sale."""
    held: dict[str, tuple[int, Decimal]] = {}  # symbol -> (quantity, average cost)
    costs: dict[tuple[str, str], Decimal] = {}
    for trade in trades:
        quantity, average = held.get(trade.symbol, (0, ZERO))
        if trade.side is Side.BUY:
            total = quantity + trade.quantity
            held[trade.symbol] = (total, (quantity * average + trade.quantity * trade.price) / total)
        else:
            costs[(trade.run_id, trade.symbol)] = average
            held[trade.symbol] = (quantity - trade.quantity, average)
    return costs


def _gain(result: OrderResult, average_cost: Decimal) -> Decimal:
    return result.order.quantity * (result.price - average_cost) - (result.fee or ZERO)


def _holdings(portfolio: Portfolio, prices: Mapping[str, Decimal]) -> tuple[HoldingResult, ...]:
    return tuple(
        HoldingResult(symbol, _change(position.average_cost, prices[symbol]))
        for symbol, position in sorted(portfolio.positions.items())
        if symbol in prices
    )


def _average_cash(
    snapshots: Sequence[ValueSnapshot],
    start: datetime,
    now: datetime,
    portfolio: Portfolio,
    prices: Mapping[str, Decimal],
) -> Decimal:
    """Average share of the portfolio held in cash at the value points of the period; now, if none recorded it."""
    shares = [s.cash / s.total_value * HUNDRED for s in snapshots if start <= s.at <= now and s.cash is not None]
    if shares:
        return sum(shares, ZERO) / len(shares)
    if any(symbol not in prices for symbol in portfolio.positions):
        return ZERO
    return portfolio.cash / portfolio.total_value(prices) * HUNDRED


def _change(start: Decimal, end: Decimal) -> Decimal:
    return (end - start) / start * HUNDRED if start else ZERO
