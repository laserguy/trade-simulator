"""Use case: rebuild the watchlist on request (D4, D14). Allowed any time, even when the market is closed (D21)."""

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from trade_simulator.application.activity import NoActivity
from trade_simulator.application.ports import (
    ActivityReporter,
    RefreshContext,
    Repository,
    StockUniverse,
    TradingAgents,
)
from trade_simulator.application.run_cost import cost_of
from trade_simulator.application.run_guard import RunGuard
from trade_simulator.core.decision_log import (
    MAX_WATCHLIST_SIZE,
    DecisionRun,
    Finding,
    RunStatus,
    RunTrigger,
    Watchlist,
)
from trade_simulator.core.errors import AgentError, RunInProgressError, TradeSimulatorError
from trade_simulator.core.exchange_profile import ExchangeProfile
from trade_simulator.core.run_budget import REFRESH_RUN_LIMITS

logger = logging.getLogger(__name__)
ACTOR = "Simulator"


class NoValidPicksError(TradeSimulatorError):
    def __init__(self, stock_pool: str) -> None:
        super().__init__(f"The agent picked no valid {stock_pool} stocks; the previous watchlist is kept")


class WatchlistRefresher:
    def __init__(
        self,
        *,
        repository: Repository,
        agent: TradingAgents,
        universe: StockUniverse,
        profile: ExchangeProfile,
        guard: RunGuard,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        id_factory: Callable[[], str] = lambda: uuid4().hex,
        activity: ActivityReporter | None = None,
    ) -> None:
        self._repository = repository
        self._agent = agent
        self._universe = universe
        self._profile = profile
        self._guard = guard
        self._clock = clock
        self._new_id = id_factory
        self._activity = activity or NoActivity()

    async def refresh(self) -> DecisionRun:
        if not self._guard.try_acquire():
            raise RunInProgressError()
        started_at = self._clock()
        self._activity.begin("Watchlist refresh")
        self._activity.add(ACTOR, f"Started: choosing stocks from the {self._profile.stock_pool}")
        try:
            run = await self._refresh(started_at)
            self._activity.add(ACTOR, f"Finished: {len(self._repository.load_watchlist().entries)} stocks on the watchlist")
            return run
        except Exception as exc:
            logger.warning("Watchlist refresh failed: %s", exc, exc_info=True)
            run = self._log_failure(started_at, exc)
            self._activity.add(ACTOR, f"Failed: {run.failure_reason}")
            return run
        finally:
            self._activity.end()
            self._guard.release()

    async def _refresh(self, started_at: datetime) -> DecisionRun:
        stock_pool = self._universe.symbols()
        proposal = await self._agent.build_watchlist(
            RefreshContext(
                profile=self._profile,
                limits=REFRESH_RUN_LIMITS,
                stock_pool=stock_pool,
                current_watchlist=self._repository.load_watchlist(),
                now=started_at,
            )
        )

        kept, warnings = [], []
        for entry in proposal.entries:
            if entry.symbol not in stock_pool:
                warnings.append(self._dropped(entry.symbol, f"not in the {self._profile.stock_pool}"))
            elif any(e.symbol == entry.symbol for e in kept):
                continue
            elif len(kept) >= MAX_WATCHLIST_SIZE:
                warnings.append(self._dropped(entry.symbol, f"watchlist limit of {MAX_WATCHLIST_SIZE} reached"))
            else:
                kept.append(entry)
        if not kept:
            raise NoValidPicksError(self._profile.stock_pool)

        self._repository.save_watchlist(Watchlist(entries=tuple(kept), refreshed_at=started_at))
        run = DecisionRun(
            id=self._new_id(),
            trigger=RunTrigger.REFRESH,
            started_at=started_at,
            finished_at=self._clock(),
            status=RunStatus.COMPLETED,
            failure_reason=None,
            findings=proposal.findings + tuple(warnings),
            order_results=(),
            cost=cost_of(proposal.usage),
            trace_id=proposal.trace_id,
        )
        self._repository.save_run(run, None)
        return run

    def _log_failure(self, started_at: datetime, exc: Exception) -> DecisionRun:
        is_agent_error = isinstance(exc, AgentError)
        run = DecisionRun(
            id=self._new_id(),
            trigger=RunTrigger.REFRESH,
            started_at=started_at,
            finished_at=self._clock(),
            status=RunStatus.FAILED,
            failure_reason=str(exc) or type(exc).__name__,
            findings=(),
            order_results=(),
            cost=cost_of(exc.usage if is_agent_error else None),
            trace_id=exc.trace_id if is_agent_error else None,
        )
        self._repository.save_run(run, None)
        return run

    def _dropped(self, symbol: str, reason: str) -> Finding:
        self._activity.add(ACTOR, f"{symbol} not added: {reason}")
        return Finding(symbol=symbol, summary="Pick not added to the watchlist", warnings=(f"{reason[0].upper()}{reason[1:]}; dropped",))
