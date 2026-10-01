"""A strategy review and the scorecard it judges (D43)."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from trade_simulator.core.decision_log import RunCost, RunStatus
from trade_simulator.core.strategy import StrategySection


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
