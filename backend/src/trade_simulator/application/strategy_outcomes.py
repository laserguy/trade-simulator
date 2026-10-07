"""What happened after a strategy version's trades, and what its runs did each day (D43).

Computed by code for the strategy review, so the agent can judge sell timing, missed buys and holds.
"""

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from trade_simulator.application.ports import MarketCalendar, ValueSnapshot
from trade_simulator.core.decision_log import OVERALL, DecisionRun, RunStatus
from trade_simulator.core.order import Side
from trade_simulator.core.strategy_review import OrderOutcome, StockMove, TradingDay
from trade_simulator.core.trading_rules import OrderStatus

HUNDRED = Decimal(100)


def order_outcomes(
    *,
    runs: Sequence[DecisionRun],
    snapshots: Sequence[ValueSnapshot],
    prices: Mapping[str, Decimal],
    benchmark_now: Decimal | None,
    calendar: MarketCalendar,
    now: datetime,
) -> tuple[OrderOutcome, ...]:
    """Each executed order in completed runs, with its stock's move and the benchmark's up to `now`."""
    return tuple(
        OrderOutcome(
            at=run.started_at,
            side=result.order.side,
            quantity=result.order.quantity,
            symbol=result.order.symbol,
            price=result.price,
            price_now=prices.get(result.order.symbol),
            trading_days=_closes_between(calendar, run.started_at, now),
            benchmark_percent=_benchmark_move(snapshots, run.started_at, benchmark_now),
        )
        for run in runs
        if run.status is RunStatus.COMPLETED
        for result in run.order_results
        if result.status is OrderStatus.EXECUTED
    )


def unbought_moves(
    *,
    watchlist: Iterable[str],
    runs: Sequence[DecisionRun],
    held: Iterable[str],
    start_prices: Mapping[str, Decimal],
    prices: Mapping[str, Decimal],
) -> tuple[StockMove, ...]:
    """Watchlist stocks neither held nor bought in these runs, biggest rise first; unavailable ones last."""
    bought = {
        result.order.symbol
        for run in runs
        for result in run.order_results
        if result.status is OrderStatus.EXECUTED and result.order.side is Side.BUY
    }
    skipped = bought | set(held)
    moves = [
        StockMove(symbol, _change(start_prices.get(symbol), prices.get(symbol)))
        for symbol in watchlist
        if symbol not in skipped
    ]
    return tuple(sorted(moves, key=lambda m: (m.percent is None, -(m.percent or 0), m.symbol)))


def trading_days(runs: Sequence[DecisionRun], timezone: str) -> tuple[TradingDay, ...]:
    """One entry per exchange day with completed runs, oldest first. Failed and skipped runs are left out:
    they are technical problems, not decisions."""
    zone = ZoneInfo(timezone)
    by_day: dict = {}
    for run in sorted(runs, key=lambda r: r.started_at):
        if run.status is RunStatus.COMPLETED:
            by_day.setdefault(run.started_at.astimezone(zone).date(), []).append(run)
    return tuple(_day(day, day_runs) for day, day_runs in by_day.items())


def last_close(calendar: MarketCalendar, moment: datetime) -> datetime:
    """The latest market close at or before `moment`."""
    close = calendar.next_close(moment - timedelta(days=10))
    while (following := calendar.next_close(close)) <= moment:
        close = following
    return close


def _day(day, runs: list[DecisionRun]) -> TradingDay:
    executed = [o for r in runs for o in r.order_results if o.status is OrderStatus.EXECUTED]
    summaries = [f.summary for r in runs for f in r.findings if f.symbol == OVERALL]
    return TradingDay(
        day=day,
        runs=len(runs),
        buys=sum(1 for o in executed if o.order.side is Side.BUY),
        sells=sum(1 for o in executed if o.order.side is Side.SELL),
        rejected=sum(1 for r in runs for o in r.order_results if o.status is OrderStatus.REJECTED),
        held=sum(1 for r in runs if not any(o.status is OrderStatus.EXECUTED for o in r.order_results)),
        last_summary=summaries[-1] if summaries else "",
    )


def _closes_between(calendar: MarketCalendar, start: datetime, end: datetime) -> int:
    count, close = 0, calendar.next_close(start)
    while close <= end:
        count, close = count + 1, calendar.next_close(close)
    return count


def _benchmark_move(snapshots: Sequence[ValueSnapshot], at: datetime, now_price: Decimal | None) -> Decimal | None:
    """From the first value point at or after the run (recorded right after it), else the last one before."""
    after = [s for s in snapshots if s.at >= at]
    before = [s for s in snapshots if s.at < at]
    point = after[0] if after else (before[-1] if before else None)
    return _change(point.benchmark_price if point else None, now_price)


def _change(start: Decimal | None, end: Decimal | None) -> Decimal | None:
    if start is None or end is None or not start:
        return None
    return (end - start) / start * HUNDRED
