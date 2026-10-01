"""Use case: one decision run. The agent proposes, the core checks, valid trades execute (D20)."""

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from trade_simulator.application.activity import NoActivity
from trade_simulator.application.portfolio_setup import load_or_create_portfolio
from trade_simulator.application.ports import (
    ActivityReporter,
    DecisionContext,
    MarketCalendar,
    MarketData,
    Repository,
    TradingAgents,
)
from trade_simulator.application.run_cost import cost_of
from trade_simulator.application.run_guard import RunGuard
from trade_simulator.application.trade_memory import open_position_buys, performance_since_start
from trade_simulator.core.decision_log import DecisionRun, RunStatus, RunTrigger
from trade_simulator.core.errors import AgentError, MarketClosedError, RunInProgressError, TradeSimulatorError
from trade_simulator.core.exchange_profile import ExchangeProfile
from trade_simulator.core.run_budget import DECISION_RUN_LIMITS
from trade_simulator.core.trading_rules import OrderResult, OrderStatus, TradingRules, execute_orders

logger = logging.getLogger(__name__)

ACTOR = "Simulator"
RULES_ACTOR = "Rules check"
TRIGGER_LABELS = {
    RunTrigger.MANUAL: "Run now",
    RunTrigger.DAILY: "daily run",
    RunTrigger.EVERY_15_MIN: "15-minute run",
    RunTrigger.REFRESH: "watchlist refresh",
}


def _rules_line(result: OrderResult) -> str:
    order = result.order
    action = f"{order.side.value.upper()} {order.quantity} {order.symbol}"
    if result.status is OrderStatus.EXECUTED:
        return f"{action}: executed at {result.price} + {result.fee} fee"
    return f"{action}: rejected ({result.rejection_reason.value})"


def _outcome_line(run: DecisionRun) -> str:
    if run.status is RunStatus.FAILED:
        return f"Failed: {run.failure_reason}"
    executed = sum(1 for r in run.order_results if r.status is OrderStatus.EXECUTED)
    return f"Finished: {executed} executed, {len(run.order_results) - executed} rejected"


class NoWatchlistError(TradeSimulatorError):
    def __init__(self) -> None:
        super().__init__("No watchlist yet: refresh the watchlist first")


class DecisionRunner:
    def __init__(
        self,
        *,
        repository: Repository,
        market_data: MarketData,
        calendar: MarketCalendar,
        agent: TradingAgents,
        profile: ExchangeProfile,
        guard: RunGuard,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        id_factory: Callable[[], str] = lambda: uuid4().hex,
        activity: ActivityReporter | None = None,
    ) -> None:
        self._repository = repository
        self._market_data = market_data
        self._calendar = calendar
        self._agent = agent
        self._profile = profile
        self._rules = TradingRules.for_exchange(profile)
        self._guard = guard
        self._clock = clock
        self._new_id = id_factory
        self._activity = activity or NoActivity()

    async def run(self, trigger: RunTrigger) -> DecisionRun:
        """Run once. Raises MarketClosedError / RunInProgressError for refused manual runs; logs everything else."""
        started_at = self._clock()
        if not self._guard.try_acquire():
            if trigger is RunTrigger.MANUAL:
                raise RunInProgressError()
            return self._log(started_at, trigger, RunStatus.SKIPPED, "Previous run still in progress")
        try:
            if not self._calendar.is_open(started_at):
                raise MarketClosedError(self._calendar.next_open(started_at))
            self._activity.begin("Decision run")
            self._activity.add(ACTOR, f"Started ({TRIGGER_LABELS[trigger]})")
            try:
                run = await self._decide_and_trade(started_at, trigger)
            except TradeSimulatorError as exc:
                logger.warning("Decision run failed: %s", exc, exc_info=True)
                run = self._log_failure(started_at, trigger, exc)
            except Exception as exc:
                logger.exception("Decision run crashed")
                run = self._log_failure(started_at, trigger, exc)
            self._activity.add(ACTOR, _outcome_line(run))
            return run
        finally:
            self._activity.end()
            self._guard.release()

    async def _decide_and_trade(self, started_at: datetime, trigger: RunTrigger) -> DecisionRun:
        portfolio = load_or_create_portfolio(self._repository, self._profile)
        watchlist = self._repository.load_watchlist()
        if watchlist is None:
            raise NoWatchlistError()

        # Execution uses these same prices: data is ~15 min delayed anyway (D7), and one fetch per run
        # keeps Finnhub calls within its free rate limit.
        # The benchmark is fetched with them, only for the agent's performance line (D42).
        tradable = watchlist.symbols | set(portfolio.positions)
        benchmark = self._profile.benchmark_symbol
        fetched = self._market_data.get_prices(sorted(tradable | {benchmark}))
        prices = {symbol: price for symbol, price in fetched.items() if symbol in tradable}

        decision = await self._agent.decide(
            DecisionContext(
                profile=self._profile,
                rules=self._rules,
                limits=DECISION_RUN_LIMITS,
                portfolio=portfolio,
                prices=prices,
                watchlist=watchlist,
                now=started_at,
                market_overview=self._repository.latest_market_overview(),
                holding_buys=open_position_buys(self._repository.executed_trades()),
                performance=performance_since_start(
                    portfolio, prices, self._profile, self._repository.load_benchmark_start(), fetched.get(benchmark)
                ),
            )
        )
        report = execute_orders(portfolio, decision.orders, prices, watchlist.symbols, self._rules)
        for result in report.results:
            self._activity.add(RULES_ACTOR, _rules_line(result))

        run = DecisionRun(
            id=self._new_id(),
            trigger=trigger,
            started_at=started_at,
            finished_at=self._clock(),
            status=RunStatus.COMPLETED,
            failure_reason=None,
            findings=decision.findings,
            order_results=report.results,
            cost=cost_of(decision.usage),
            trace_id=decision.trace_id,
        )
        self._repository.save_run(run, report.portfolio)
        return run

    def _log_failure(self, started_at: datetime, trigger: RunTrigger, exc: Exception) -> DecisionRun:
        trace_id = exc.trace_id if isinstance(exc, AgentError) else None
        usage = exc.usage if isinstance(exc, AgentError) else None
        return self._log(started_at, trigger, RunStatus.FAILED, str(exc) or type(exc).__name__, usage, trace_id)

    def _log(self, started_at, trigger, status, reason, usage=None, trace_id=None) -> DecisionRun:
        run = DecisionRun(
            id=self._new_id(),
            trigger=trigger,
            started_at=started_at,
            finished_at=self._clock(),
            status=status,
            failure_reason=reason,
            findings=(),
            order_results=(),
            cost=cost_of(usage),
            trace_id=trace_id,
        )
        self._repository.save_run(run, None)
        return run
