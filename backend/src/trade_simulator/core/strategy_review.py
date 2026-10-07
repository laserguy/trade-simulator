"""A strategy review and the scorecard it judges (D43)."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from trade_simulator.core.decision_log import RunCost, RunStatus
from trade_simulator.core.order import Side
from trade_simulator.core.strategy import StrategySection


@dataclass(frozen=True)
class ReviewMinimums:
    """How long a version must run before it may be reviewed (D43)."""

    trading_days: int
    trading_runs: int


STRATEGY_REVIEW_MINIMUMS = ReviewMinimums(trading_days=10, trading_runs=5)


class ReviewTrigger(Enum):
    BUTTON = "button"
    SCHEDULED = "scheduled"
    AUTOMATIC = "automatic"  # a trading run found no strategy


class ReviewDecision(Enum):
    FIRST = "first"
    KEEP = "keep"
    CHANGE = "change"


class TargetsVerdict(Enum):
    MET = "met"
    PARTLY_MET = "partly_met"
    MISSED = "missed"


class Followed(Enum):
    YES = "yes"
    PARTLY = "partly"
    NO = "no"


@dataclass(frozen=True)
class ClosedTrade:
    symbol: str
    gain: Decimal  # money gained (negative for a loss), fees included


@dataclass(frozen=True)
class HoldingResult:
    symbol: str
    gain_percent: Decimal  # on cost


@dataclass(frozen=True)
class OrderOutcome:
    """What a stock did after an executed order, up to the review (D43). For a sell, the move since selling."""

    at: datetime  # when its run started
    side: Side
    quantity: int
    symbol: str
    price: Decimal  # the executed price
    price_now: Decimal | None  # None when no price was available
    trading_days: int  # closes between the order and the review
    benchmark_percent: Decimal | None  # the benchmark over the same span; None when unknown

    @property
    def change_percent(self) -> Decimal | None:
        return None if self.price_now is None else (self.price_now - self.price) / self.price * 100


@dataclass(frozen=True)
class StockMove:
    """A watchlist stock not bought in the period, and how it moved over the period (D43)."""

    symbol: str
    percent: Decimal | None  # None when a price was unavailable


@dataclass(frozen=True)
class TradingDay:
    """One trading day of the period: what its completed runs did, and the day's last summary (D43).
    Failed runs are left out: they are technical problems, not decisions."""

    day: date
    runs: int
    buys: int
    sells: int
    rejected: int
    held: int  # runs that executed nothing
    last_summary: str  # the day's last run's summary; empty if it had none


@dataclass(frozen=True)
class Scorecard:
    """A strategy version's results over its period, computed by code, never by the agent."""

    period_start: datetime
    period_end: datetime
    portfolio_percent: Decimal
    benchmark_percent: Decimal
    trading_runs: int
    trades: int
    fees: Decimal
    closed_trades: tuple[ClosedTrade, ...]
    holdings: tuple[HoldingResult, ...]
    average_cash_percent: Decimal
    followed_orders: int
    deviations: int
    # Added for the review only (not shown on the Strategy tab); empty on older saved scorecards.
    order_outcomes: tuple[OrderOutcome, ...] = ()
    unbought: tuple[StockMove, ...] = ()
    days: tuple[TradingDay, ...] = ()


@dataclass(frozen=True)
class StrategyReview:
    """One review, whatever its outcome. A failed review keeps the reason and leaves the strategy as it was."""

    id: str
    trigger: ReviewTrigger
    started_at: datetime
    finished_at: datetime | None
    status: RunStatus
    failure_reason: str | None
    reviewed_version: int | None  # None for the first review
    decision: ReviewDecision | None  # None when the review failed
    reason: str
    cost: RunCost
    trace_id: str | None
    targets_verdict: TargetsVerdict | None = None
    targets_note: str = ""
    followed: Followed | None = None
    followed_note: str = ""
    section_changes: Mapping[StrategySection, str] = field(default_factory=dict)  # why each section changed
    scorecard: Scorecard | None = None  # as shown to the agent
