"""What each run records (D22) and the agent-built watchlist (D4)."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from trade_simulator.core.errors import DomainError
from trade_simulator.core.trading_rules import OrderResult

MAX_WATCHLIST_SIZE = 20


class RunTrigger(Enum):
    MANUAL = "manual"
    DAILY = "daily"
    EVERY_15_MIN = "every_15_min"
    REFRESH = "refresh"


class RunStatus(Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class Finding:
    """Research Agent's summary for one stock, with sources and anomaly warnings (D11)."""

    symbol: str
    summary: str
    sources: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    # The stock's quote when the agent looked it up; None when it wasn't quoted (or for OVERALL and MARKET).
    price: Decimal | None = None
    change_percent: Decimal | None = None


@dataclass(frozen=True)
class RunCost:
    input_tokens: int
    output_tokens: int
    searches: int
    model: str | None = None  # which LLM the tokens were spent on, for the cost estimate


@dataclass(frozen=True)
class DecisionRun:
    id: str
    trigger: RunTrigger
    started_at: datetime
    finished_at: datetime | None
    status: RunStatus
    failure_reason: str | None
    findings: tuple[Finding, ...]
    order_results: tuple[OrderResult, ...]
    cost: RunCost
    trace_id: str | None
    strategy_version: int | None = None  # the strategy the run followed (D43); None before strategies


@dataclass(frozen=True)
class WatchlistEntry:
    symbol: str
    reason: str
    sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.strip().upper())


@dataclass(frozen=True)
class Watchlist:
    entries: tuple[WatchlistEntry, ...]
    refreshed_at: datetime

    def __post_init__(self) -> None:
        symbols = [entry.symbol for entry in self.entries]
        if len(symbols) != len(set(symbols)):
            raise DomainError("Watchlist contains duplicate symbols")
        if len(symbols) > MAX_WATCHLIST_SIZE:
            raise DomainError(f"Watchlist can hold at most {MAX_WATCHLIST_SIZE} stocks")

    @property
    def symbols(self) -> frozenset[str]:
        return frozenset(entry.symbol for entry in self.entries)
