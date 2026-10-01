import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from fakes import FakeAgent, FakeMarketData, FixedClock, WeekdayCalendar
from trade_simulator.adapters.sqlite_repository import SqliteRepository
from trade_simulator.application.activity import ActivityFeed
from trade_simulator.application.ports import AgentUsage, ReviewProposal
from trade_simulator.application.review_strategy import (
    AutomaticReviewNotNeededError,
    StrategyReviewNotAllowedError,
    StrategyReviewRunner,
)
from trade_simulator.application.run_guard import RunGuard
from trade_simulator.core.decision_log import DecisionRun, RunCost, RunStatus, RunTrigger, Watchlist, WatchlistEntry
from trade_simulator.core.errors import AgentError, RunInProgressError
from trade_simulator.core.exchange_profile import US_PROFILE
from trade_simulator.core.order import Order, Side
from trade_simulator.core.strategy import SECTION_WORD_LIMIT, Strategy, StrategySection, StrategyVersion
from trade_simulator.core.strategy_review import (
    Followed,
    ReviewDecision,
    ReviewTrigger,
    StrategyReview,
    TargetsVerdict,
)
from trade_simulator.core.trading_rules import OrderResult, OrderStatus

V1_START = datetime(2026, 9, 14, 14, 0, tzinfo=timezone.utc)  # Monday
NOW = datetime(2026, 10, 2, 21, 0, tzinfo=timezone.utc)  # Friday 17:00 New York, minimums met
STRATEGY = Strategy("Earnings momentum.", "Start at 6%.", "Sell when the reason breaks.", "Keep 10-25% cash.", "Level with SPY.")
NEW_STRATEGY = Strategy("Earnings momentum.", "Start at 4%.", "Sell when the reason breaks.", "Keep 10-25% cash.", "Ahead of SPY.")
USAGE = AgentUsage(8000, 900, 0, "gpt-6-luna")


@pytest.fixture
def repo(tmp_path):
    repository = SqliteRepository(tmp_path / "sim.sqlite3")
    repository.initialize()
    repository.save_watchlist(Watchlist((WatchlistEntry("AAPL", "Earnings"),), V1_START))
    return repository


def proposal(decision=ReviewDecision.CHANGE, new_strategy=NEW_STRATEGY, **changes):
    fields = dict(
        decision=decision,
        reason="Sizing was too large for two correlated buys.",
        new_strategy=new_strategy,
        section_changes={StrategySection.POSITION_SIZE: "Two full buys fell together."},
        targets_verdict=TargetsVerdict.PARTLY_MET,
        targets_note="No forced sells, but behind SPY.",
        followed=Followed.YES,
        followed_note="Every order named its section.",
        usage=USAGE,
        trace_id="trace_review",
    )
    return ReviewProposal(**{**fields, **changes})


def make_runner(repo, agent, now=NOW, guard=None, activity=None, ids=None):
    ids = iter(ids or ["rev-new"])
    return StrategyReviewRunner(
        repository=repo,
        market_data=FakeMarketData({"AAPL": "210", "SPY": "505"}),
        calendar=WeekdayCalendar(),
        agent=agent,
        profile=US_PROFILE,
        guard=guard or RunGuard(),
        clock=FixedClock(now),
        id_factory=lambda: next(ids),
        activity=activity or ActivityFeed(clock=FixedClock(now)),
    )


def review(runner, trigger=ReviewTrigger.BUTTON):
    return asyncio.run(runner.review(trigger))


def with_v1_and_five_runs(repo):
    first = StrategyReview(
        id="rev-1", trigger=ReviewTrigger.BUTTON, started_at=V1_START, finished_at=V1_START, status=RunStatus.COMPLETED,
        failure_reason=None, reviewed_version=None, decision=ReviewDecision.FIRST, reason="Start", cost=RunCost(0, 0, 0),
        trace_id=None,
    )
    repo.save_strategy_review(first, StrategyVersion(1, STRATEGY, V1_START, None, "rev-1"))
    for day in range(5):
        started = V1_START + timedelta(days=1 + day, minutes=30)
        buy = Order("AAPL", Side.BUY, 1, f"Reason {day}", StrategySection.WHAT_I_LOOK_FOR.value)
        repo.save_run(
            DecisionRun(
                id=f"run-{day}", trigger=RunTrigger.DAILY, started_at=started, finished_at=started,
                status=RunStatus.COMPLETED, failure_reason=None, findings=(),
                order_results=(OrderResult(buy, OrderStatus.EXECUTED, Decimal("200"), Decimal("1")),),
                cost=RunCost(0, 0, 0), trace_id=None, strategy_version=1,
            ),
            None,
        )


def test_the_first_review_writes_version_1(repo):
    agent = FakeAgent(review=proposal(targets_verdict=None, followed=None, section_changes={}))

    result = review(make_runner(repo, agent))

    assert (result.status, result.decision, result.reviewed_version) == (RunStatus.COMPLETED, ReviewDecision.FIRST, None)
    current = repo.current_strategy()
    assert (current.number, current.strategy, current.started_at, current.review_id) == (1, NEW_STRATEGY, NOW, "rev-new")
    [context] = agent.review_contexts
    assert (context.current, context.scorecard, context.orders, context.versions) == (None, None, (), ())


def test_a_review_is_refused_before_the_minimums_are_met(repo):
    with_v1_and_five_runs(repo)
    agent = FakeAgent(review=proposal())

    with pytest.raises(StrategyReviewNotAllowedError):
        review(make_runner(repo, agent, now=V1_START + timedelta(days=4)))

    assert agent.review_contexts == []
    assert len(repo.strategy_reviews()) == 1


def test_an_automatic_review_only_writes_a_missing_strategy(repo):
    with_v1_and_five_runs(repo)

    with pytest.raises(AutomaticReviewNotNeededError):
        review(make_runner(repo, FakeAgent(review=proposal())), ReviewTrigger.AUTOMATIC)


def test_a_change_ends_v1_starts_v2_and_saves_the_scorecard_shown(repo):
    with_v1_and_five_runs(repo)
    agent = FakeAgent(review=proposal())

    result = review(make_runner(repo, agent))

    assert (result.decision, result.reviewed_version, result.status) == (ReviewDecision.CHANGE, 1, RunStatus.COMPLETED)
    assert (result.targets_verdict, result.followed) == (TargetsVerdict.PARTLY_MET, Followed.YES)
    assert result.section_changes == {StrategySection.POSITION_SIZE: "Two full buys fell together."}
    assert result.scorecard.trading_runs == 5
    assert (result.cost.input_tokens, result.trace_id) == (8000, "trace_review")
    v1, v2 = repo.strategy_versions()
    assert (v1.ended_at, v2.number, v2.strategy) == (NOW, 2, NEW_STRATEGY)
    assert repo.strategy_reviews()[-1] == result


def test_the_review_is_given_the_scorecard_orders_and_history(repo):
    with_v1_and_five_runs(repo)
    agent = FakeAgent(review=proposal())

    review(make_runner(repo, agent))

    [context] = agent.review_contexts
    assert context.current.number == 1
    assert context.scorecard.trades == 5
    assert [o.result.order.reason for o in context.orders] == [f"Reason {day}" for day in range(5)]
    assert [v.number for v in context.versions] == [1]
    assert [r.id for r in context.reviews] == ["rev-1"]
    assert context.prices == {"AAPL": Decimal("210")}


def test_a_keep_saves_the_review_and_leaves_the_strategy(repo):
    with_v1_and_five_runs(repo)

    result = review(make_runner(repo, FakeAgent(review=proposal(decision=ReviewDecision.KEEP, new_strategy=None))))

    assert result.decision is ReviewDecision.KEEP
    assert repo.current_strategy().number == 1
    assert len(repo.strategy_reviews()) == 2


def test_an_answer_that_fails_the_check_is_logged_and_changes_nothing(repo):
    with_v1_and_five_runs(repo)
    too_long = Strategy(**{**NEW_STRATEGY.__dict__, "targets": " ".join(["word"] * (SECTION_WORD_LIMIT + 5))})

    result = review(make_runner(repo, FakeAgent(review=proposal(new_strategy=too_long, followed=None))))

    assert result.status is RunStatus.FAILED
    assert result.failure_reason == (
        "The answer failed the check: no verdict on whether the strategy was followed; "
        f"My targets for this period has {SECTION_WORD_LIMIT + 5} words; the limit is {SECTION_WORD_LIMIT}"
    )
    assert (result.cost.input_tokens, result.trace_id) == (8000, "trace_review")
    assert repo.current_strategy().number == 1


def test_a_change_without_a_new_strategy_fails_the_check(repo):
    with_v1_and_five_runs(repo)

    result = review(make_runner(repo, FakeAgent(review=proposal(new_strategy=None))))

    assert result.failure_reason == "The answer failed the check: chose to change but wrote no new strategy"


def test_an_agent_failure_is_logged_with_its_trace_and_cost(repo):
    error = AgentError("Strategy review failed: timeout", trace_id="trace_x", usage=AgentUsage(500, 0, 0, "gpt-6-luna"))

    result = review(make_runner(repo, FakeAgent(error=error)))

    assert (result.status, result.failure_reason, result.trace_id) == (
        RunStatus.FAILED, "Strategy review failed: timeout", "trace_x"
    )
    assert result.cost.input_tokens == 500
    assert repo.current_strategy() is None
    assert repo.strategy_reviews() == [result]


def test_a_review_never_overlaps_another_run(repo):
    guard = RunGuard()
    guard.try_acquire()

    with pytest.raises(RunInProgressError):
        review(make_runner(repo, FakeAgent(review=proposal()), guard=guard))

    assert repo.strategy_reviews() == []


def test_the_live_feed_shows_the_review(repo):
    feed = ActivityFeed(clock=FixedClock(NOW))

    review(make_runner(repo, FakeAgent(review=proposal()), activity=feed))

    texts = [e.text for e in feed.snapshot().events]
    assert texts[0] == "Started: writing the first strategy"
    assert texts[-1] == "Finished: wrote strategy v1"
    assert feed.snapshot().active is False
