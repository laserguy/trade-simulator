"""Use case: the Trading Agent writes or reviews its own strategy (D43).

The code computes the scorecard, the agent judges it, and the code checks the answer before saving.
A failed review is logged and leaves the strategy as it was.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from trade_simulator.application.activity import NoActivity
from trade_simulator.application.portfolio_setup import load_or_create_portfolio
from trade_simulator.application.ports import (
    ActivityReporter,
    MarketCalendar,
    MarketData,
    Repository,
    ReviewContext,
    ReviewedOrder,
    ReviewProposal,
    TradingAgents,
)
from trade_simulator.application.run_cost import cost_of
from trade_simulator.application.run_guard import RunGuard
from trade_simulator.application.strategy_scorecard import build_scorecard
from trade_simulator.application.strategy_timing import ReviewTiming, review_timing
from trade_simulator.core.decision_log import RunStatus
from trade_simulator.core.errors import AgentError, RunInProgressError, TradeSimulatorError
from trade_simulator.core.exchange_profile import ExchangeProfile
from trade_simulator.core.strategy import StrategyVersion, strategy_problems
from trade_simulator.core.strategy_review import ReviewDecision, ReviewTrigger, Scorecard, StrategyReview
from trade_simulator.core.trading_rules import TradingRules

logger = logging.getLogger(__name__)
ACTOR = "Simulator"


class StrategyReviewNotAllowedError(TradeSimulatorError):
    """A review was asked for before the current version's minimum period was over (D43)."""

    def __init__(self, timing: ReviewTiming) -> None:
        m = timing.minimums
        super().__init__(
            f"Too early to review: {timing.trading_days} of {m.trading_days} trading days and "
            f"{timing.trading_runs} of {m.trading_runs} trading runs done"
        )
        self.timing = timing


class AutomaticReviewNotNeededError(TradeSimulatorError):
    def __init__(self) -> None:
        super().__init__("A strategy already exists; automatic reviews only write a missing one")


class StrategyReviewRunner:
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
        self._guard = guard
        self._clock = clock
        self._new_id = id_factory
        self._activity = activity or NoActivity()

    def timing(self) -> ReviewTiming:
        current = self._repository.current_strategy()
        return review_timing(
            current=current,
            reviews=self._repository.strategy_reviews(),
            runs=self._repository.runs_following(current.number) if current else [],
            calendar=self._calendar,
            now=self._clock(),
        )

    async def review(self, trigger: ReviewTrigger) -> StrategyReview:
        """Review once. Raises for refused reviews (busy, too early); logs everything else, failures included."""
        if not self._guard.try_acquire():
            raise RunInProgressError()
        try:
            self._check_allowed(trigger)
            current = self._repository.current_strategy()
            started_at = self._clock()
            self._activity.begin("Strategy review")
            try:
                self._activity.add(
                    ACTOR, f"Started: reviewing strategy v{current.number}" if current else "Started: writing the first strategy"
                )
                try:
                    review = await self._review(started_at, trigger, current)
                except Exception as exc:
                    logger.warning("Strategy review failed: %s", exc, exc_info=True)
                    review = self._failed(started_at, trigger, current, str(exc) or type(exc).__name__, exc)
                self._activity.add(ACTOR, _outcome_line(review, current))
                return review
            finally:
                self._activity.end()
        finally:
            self._guard.release()

    def _check_allowed(self, trigger: ReviewTrigger) -> None:
        timing = self.timing()
        if trigger is ReviewTrigger.AUTOMATIC and not timing.first:
            raise AutomaticReviewNotNeededError()
        if not timing.can_review:
            raise StrategyReviewNotAllowedError(timing)

    async def _review(self, started_at: datetime, trigger: ReviewTrigger, current: StrategyVersion | None) -> StrategyReview:
        context = self._context(started_at, current)
        proposal = await self._agent.review_strategy(context)
        problems = review_problems(proposal, first=current is None)
        if problems:
            reason = "The answer failed the check: " + "; ".join(problems)
            return self._failed(started_at, trigger, current, reason, proposal=proposal, scorecard=context.scorecard)

        finished_at = self._clock()
        review = StrategyReview(
            id=self._new_id(),
            trigger=trigger,
            started_at=started_at,
            finished_at=finished_at,
            status=RunStatus.COMPLETED,
            failure_reason=None,
            reviewed_version=current.number if current else None,
            decision=ReviewDecision.FIRST if current is None else proposal.decision,
            reason=proposal.reason,
            cost=cost_of(proposal.usage),
            trace_id=proposal.trace_id,
            targets_verdict=proposal.targets_verdict,
            targets_note=proposal.targets_note,
            followed=proposal.followed,
            followed_note=proposal.followed_note,
            section_changes=dict(proposal.section_changes) if current else {},
            scorecard=context.scorecard,
        )
        new_version = None
        if review.decision is not ReviewDecision.KEEP:
            number = current.number + 1 if current else 1
            new_version = StrategyVersion(number, proposal.new_strategy, finished_at, None, review.id)
        self._repository.save_strategy_review(review, new_version)
        return review

    def _context(self, now: datetime, current: StrategyVersion | None) -> ReviewContext:
        portfolio = load_or_create_portfolio(self._repository, self._profile)
        watchlist = self._repository.load_watchlist()
        symbols = set(portfolio.positions) | (watchlist.symbols if watchlist else set())
        prices = self._market_data.get_prices(sorted(symbols)) if symbols else {}
        runs = self._repository.runs_following(current.number) if current else []
        scorecard = None
        if current:
            scorecard = build_scorecard(
                version=current,
                runs=runs,
                trades=self._repository.executed_trades(),
                snapshots=self._repository.load_value_snapshots(),
                portfolio=portfolio,
                prices=prices,
                now=now,
            )
        return ReviewContext(
            profile=self._profile,
            rules=TradingRules.for_exchange(self._profile),
            now=now,
            portfolio=portfolio,
            prices=prices,
            watchlist=watchlist,
            market_overview=self._repository.latest_market_overview(),
            current=current,
            scorecard=scorecard,
            orders=tuple(ReviewedOrder(run.started_at, result) for run in runs for result in run.order_results),
            versions=tuple(self._repository.strategy_versions()),
            reviews=tuple(r for r in self._repository.strategy_reviews() if r.status is RunStatus.COMPLETED),
        )

    def _failed(
        self,
        started_at: datetime,
        trigger: ReviewTrigger,
        current: StrategyVersion | None,
        reason: str,
        exc: Exception | None = None,
        proposal: ReviewProposal | None = None,
        scorecard: Scorecard | None = None,
    ) -> StrategyReview:
        usage = proposal.usage if proposal else (exc.usage if isinstance(exc, AgentError) else None)
        trace_id = proposal.trace_id if proposal else (exc.trace_id if isinstance(exc, AgentError) else None)
        review = StrategyReview(
            id=self._new_id(),
            trigger=trigger,
            started_at=started_at,
            finished_at=self._clock(),
            status=RunStatus.FAILED,
            failure_reason=reason,
            reviewed_version=current.number if current else None,
            decision=None,
            reason="",
            cost=cost_of(usage),
            trace_id=trace_id,
            scorecard=scorecard,
        )
        self._repository.save_strategy_review(review, None)
        return review


def review_problems(proposal: ReviewProposal, *, first: bool) -> list[str]:
    """Why an answer can't be saved (D43): a missing reason, verdict or strategy, or a strategy over its limits."""
    problems = []
    if not proposal.reason.strip():
        problems.append("no reason given")
    writes_strategy = first or proposal.decision is ReviewDecision.CHANGE
    if not first:
        if proposal.targets_verdict is None:
            problems.append("no verdict on the targets")
        if proposal.followed is None:
            problems.append("no verdict on whether the strategy was followed")
    if writes_strategy and proposal.new_strategy is None:
        problems.append("wrote no strategy" if first else "chose to change but wrote no new strategy")
    elif writes_strategy:
        problems += strategy_problems(proposal.new_strategy)
    return problems


def _outcome_line(review: StrategyReview, current: StrategyVersion | None) -> str:
    if review.status is RunStatus.FAILED:
        return f"Failed: {review.failure_reason}"
    if review.decision is ReviewDecision.KEEP:
        return f"Finished: kept strategy v{current.number}"
    return f"Finished: wrote strategy v{current.number + 1 if current else 1}"
