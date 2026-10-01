"""Interfaces the use cases depend on, and the data passed through them. Adapters implement them (D17)."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from trade_simulator.core.decision_log import DecisionRun, Finding, Watchlist, WatchlistEntry
from trade_simulator.core.exchange_profile import ExchangeProfile
from trade_simulator.core.order import Order, Side
from trade_simulator.core.portfolio import Portfolio
from trade_simulator.core.run_budget import RunLimits
from trade_simulator.core.strategy import StrategyVersion
from trade_simulator.core.strategy_review import StrategyReview
from trade_simulator.core.trading_rules import TradingRules


class Repository(Protocol):
    def load_portfolio(self) -> Portfolio | None: ...

    def save_portfolio(self, portfolio: Portfolio) -> None: ...

    def save_run(self, run: DecisionRun, portfolio: Portfolio | None) -> None:
        """Save the run and, if given, the resulting portfolio in one all-or-nothing step (D19)."""
        ...

    def get_run(self, run_id: str) -> DecisionRun | None: ...

    def list_runs(self, limit: int = 50) -> list[DecisionRun]: ...

    def load_watchlist(self) -> Watchlist | None: ...

    def save_watchlist(self, watchlist: Watchlist) -> None: ...

    def load_benchmark_start(self) -> "BenchmarkStart | None": ...

    def save_benchmark_start(self, symbol: str, price: Decimal, started_at: datetime) -> None: ...

    def save_value_snapshot(self, snapshot: "ValueSnapshot") -> None: ...

    def load_value_snapshots(self) -> "list[ValueSnapshot]": ...

    def save_daily_bars(self, exchange: str, symbol: str, bars: "list[DailyBar]", source: str) -> None: ...

    def load_daily_bars(self, exchange: str, symbol: str, since: date) -> "list[DailyBar]": ...

    def save_price_sync(self, sync: "PriceSync") -> None: ...

    def load_price_sync(self, exchange: str, symbol: str) -> "PriceSync | None": ...

    def executed_trades(self, symbol: str | None = None) -> "list[ExecutedTrade]":
        """Executed trades, oldest run first; all symbols when `symbol` is None."""
        ...

    def latest_market_overview(self) -> "MarketOverview | None":
        """The market overview of the newest completed watchlist refresh (D40)."""
        ...

    def save_strategy_review(self, review: StrategyReview, new_version: StrategyVersion | None) -> None:
        """Save a review and, if it wrote one, the new version (ending the current one) all-or-nothing (D43)."""
        ...

    def current_strategy(self) -> StrategyVersion | None: ...

    def strategy_versions(self) -> list[StrategyVersion]:
        """Every version, oldest first."""
        ...

    def strategy_reviews(self) -> list[StrategyReview]:
        """Every review, failed ones included, oldest first."""
        ...


class MarketData(Protocol):
    def get_prices(self, symbols: Iterable[str]) -> dict[str, Decimal]:
        """Current price per symbol. Symbols without a price are left out, never guessed."""
        ...


class MarketCalendar(Protocol):
    def is_open(self, moment: datetime) -> bool: ...

    def next_open(self, moment: datetime) -> datetime:
        """The next market open after `moment`, in the exchange's timezone."""
        ...

    def next_close(self, moment: datetime) -> datetime:
        """The next market close after `moment` (early closes included), in the exchange's timezone."""
        ...


class StockUniverse(Protocol):
    def symbols(self) -> frozenset[str]:
        """All symbols the agent may put on the watchlist (D4: the S&P 500 for the US)."""
        ...


@dataclass(frozen=True)
class AgentUsage:
    input_tokens: int
    output_tokens: int
    searches: int
    model: str | None = None


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: Decimal
    change_percent: Decimal
    previous_close: Decimal


class QuoteSource(Protocol):
    def get_quotes(self, symbols: Iterable[str]) -> dict[str, Quote]:
        """Price and today's change per symbol; unknown symbols are left out."""
        ...


@dataclass(frozen=True)
class DailyBar:
    """One trading day's prices (D36). `adj_close` accounts for splits and dividends."""

    day: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adj_close: Decimal
    volume: int


class PriceHistorySource(Protocol):
    """Any provider of daily price history (D36, D38). The UI never names it."""

    name: str  # stored with cached rows; never shown to the user
    max_requests_per_hour: int | None

    def daily_bars(self, symbol: str, since: date) -> list[DailyBar]:
        """Bars from `since` (inclusive), oldest first. Unknown symbols give an empty list."""
        ...


@dataclass(frozen=True)
class PriceSync:
    """What price history is cached for a symbol, and when the provider was last asked."""

    exchange: str
    symbol: str
    first_day: date | None
    last_day: date | None
    last_checked_at: datetime


@dataclass(frozen=True)
class ExecutedTrade:
    at: datetime  # when the run started
    side: "Side"
    quantity: int
    price: Decimal
    run_id: str
    symbol: str
    reason: str = ""  # the agent's reason for the order


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    content: str


class WebSearch(Protocol):
    """Any web search provider (D10, D34). The UI never names it; it only uses its declared allowance."""

    free_searches_per_month: int | None  # None = no limit

    def search(self, query: str) -> list[SearchResult]: ...


class ActivityReporter(Protocol):
    """Receives live, human-readable steps of the run in progress (D28)."""

    def begin(self, label: str) -> None: ...

    def add(self, actor: str, text: str) -> None: ...

    def end(self) -> None: ...


@dataclass(frozen=True)
class ValueSnapshot:
    """Portfolio value and benchmark price at one moment, for the value chart (D33)."""

    at: datetime
    total_value: Decimal
    benchmark_price: Decimal


@dataclass(frozen=True)
class BenchmarkStart:
    """The benchmark's price when tracking began, so returns can be compared (D23)."""

    symbol: str
    price: Decimal
    started_at: datetime


class SettingsStore(Protocol):
    def load_settings(self) -> dict[str, str]: ...

    def save_setting(self, key: str, value: str | None) -> None:
        """Save a setting; None removes it."""
        ...


@dataclass(frozen=True)
class MarketOverview:
    """The market overview a watchlist refresh wrote, passed on to decision runs (D40)."""

    summary: str
    sources: tuple[str, ...]
    as_of: datetime


@dataclass(frozen=True)
class Performance:
    """Return of the portfolio and of the benchmark since tracking began, in percent (D23, D42)."""

    since: datetime
    portfolio_percent: Decimal
    benchmark_symbol: str
    benchmark_percent: Decimal


@dataclass(frozen=True)
class DecisionContext:
    profile: ExchangeProfile
    rules: TradingRules
    limits: RunLimits
    portfolio: Portfolio
    prices: Mapping[str, Decimal]
    watchlist: Watchlist
    now: datetime
    market_overview: MarketOverview | None = None
    # The agent's own past (D42): the buys behind each current holding, and how the portfolio is doing.
    holding_buys: Mapping[str, tuple[ExecutedTrade, ...]] = field(default_factory=dict)
    performance: Performance | None = None


@dataclass(frozen=True)
class AgentDecision:
    orders: tuple[Order, ...]
    findings: tuple[Finding, ...]
    usage: AgentUsage
    trace_id: str | None


@dataclass(frozen=True)
class RefreshContext:
    profile: ExchangeProfile
    limits: RunLimits
    stock_pool: frozenset[str]
    current_watchlist: Watchlist | None
    now: datetime


@dataclass(frozen=True)
class WatchlistProposal:
    entries: tuple[WatchlistEntry, ...]
    findings: tuple[Finding, ...]
    usage: AgentUsage
    trace_id: str | None


class TradingAgents(Protocol):
    """The Trading Agent plus its Research Agent (D12). Proposes only; never touches the portfolio (D20).

    Implementations raise AgentError on failure.
    """

    async def decide(self, context: DecisionContext) -> AgentDecision: ...

    async def build_watchlist(self, context: RefreshContext) -> WatchlistProposal: ...
