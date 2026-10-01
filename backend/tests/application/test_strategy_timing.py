from datetime import date, datetime, timedelta

from fakes import NEW_YORK, WeekdayCalendar
from trade_simulator.application.strategy_timing import review_timing
from trade_simulator.core.decision_log import DecisionRun, RunCost, RunStatus, RunTrigger
from trade_simulator.core.strategy import Strategy, StrategyVersion
from trade_simulator.core.strategy_review import ReviewDecision, ReviewMinimums, ReviewTrigger, StrategyReview

MINIMUMS = ReviewMinimums(trading_days=10, trading_runs=5)
STRATEGY = Strategy("Look for", "Size", "Sell", "Cash", "Targets")


def ny(day, hour, minute=0):
    return datetime(2026, 9, day, hour, minute, tzinfo=NEW_YORK) if day > 9 else datetime(2026, 10, day, hour, minute, tzinfo=NEW_YORK)


V1 = StrategyVersion(number=1, strategy=STRATEGY, started_at=ny(14, 10), ended_at=None, review_id="rev-1")


def run(started_at, version=1, status=RunStatus.COMPLETED):
    return DecisionRun(
        id=f"run-{started_at.isoformat()}",
        trigger=RunTrigger.DAILY,
        started_at=started_at,
        finished_at=started_at,
        status=status,
        failure_reason=None,
        findings=(),
        order_results=(),
        cost=RunCost(0, 0, 0),
        trace_id=None,
        strategy_version=version,
    )


FIVE_RUNS = [run(ny(day, 10, 30)) for day in (14, 15, 16, 17, 18)]


def review(started_at, decision=ReviewDecision.KEEP, status=RunStatus.COMPLETED, reviewed_version=1):
    return StrategyReview(
        id=f"rev-{started_at.isoformat()}",
        trigger=ReviewTrigger.SCHEDULED,
        started_at=started_at,
        finished_at=started_at,
        status=status,
        failure_reason=None if status is RunStatus.COMPLETED else "Answer missed a section",
        reviewed_version=reviewed_version,
        decision=decision if status is RunStatus.COMPLETED else None,
        reason="",
        cost=RunCost(0, 0, 0),
        trace_id=None,
    )


def timing(now, current=V1, runs=FIVE_RUNS, reviews=(), holidays=()):
    return review_timing(
        current=current,
        reviews=list(reviews),
        runs=list(runs),
        calendar=WeekdayCalendar(holidays),
        now=now,
        minimums=MINIMUMS,
    )


def test_without_a_strategy_the_first_review_may_run_any_time():
    result = timing(ny(14, 3), current=None, runs=[])

    assert (result.first, result.can_review, result.due, result.next_scheduled) == (True, True, False, None)


def test_a_new_version_waits_for_ten_trading_days():
    result = timing(ny(24, 17))  # Thursday of the second week: 9 closes since Monday 14th, 10:00

    assert (result.trading_days, result.trading_runs) == (9, 5)
    assert result.can_review is False
    assert result.days_met_at == ny(25, 16)
    assert result.next_scheduled == ny(25, 16, 15)  # Friday after the close
    assert result.due is False


def test_once_both_minimums_are_met_the_friday_review_is_due():
    result = timing(ny(25, 16, 20))

    assert (result.can_review, result.due) == (True, True)


def test_days_alone_are_not_enough_without_five_runs():
    result = timing(ny(25, 16, 20), runs=FIVE_RUNS[:4])

    assert (result.trading_runs, result.can_review, result.due) == (4, False, False)


def test_only_completed_runs_of_this_version_count():
    runs = [*FIVE_RUNS[:4], run(ny(21, 9, 45), status=RunStatus.FAILED), run(ny(22, 9, 45), version=2)]

    assert timing(ny(25, 16, 20), runs=runs).trading_runs == 4


def test_a_failed_scheduled_review_is_not_retried_automatically():
    failed = review(ny(25, 16, 16), status=RunStatus.FAILED)

    result = timing(ny(25, 16, 30), reviews=[failed])

    assert (result.can_review, result.due) == (True, False)  # the button still works


def test_a_missed_friday_review_catches_up_when_the_app_next_runs():
    result = timing(ny(28, 10))  # Monday morning; the app was off on Friday

    assert result.due is True


def test_a_keep_starts_a_new_full_period():
    kept = review(ny(25, 16, 15))
    runs = [*FIVE_RUNS, run(ny(28, 9, 45))]

    result = timing(ny(28, 17), runs=runs, reviews=[kept])

    assert (result.trading_days, result.trading_runs, result.can_review) == (1, 1, False)


def test_reviews_of_older_versions_do_not_reset_the_period():
    older = review(ny(16, 12), reviewed_version=None, decision=ReviewDecision.FIRST)

    assert timing(ny(25, 16, 20), reviews=[older]).can_review is True


def test_holidays_do_not_count_as_trading_days():
    result = timing(ny(25, 17), holidays={date(2026, 9, 25)})

    assert result.days_met_at == ny(28, 16)
    assert result.next_scheduled == ny(2, 16, 15)  # the next Friday


def test_when_friday_is_a_holiday_the_weeks_last_close_is_the_slot():
    early = StrategyVersion(number=1, strategy=STRATEGY, started_at=ny(10, 10), ended_at=None, review_id="rev-1")
    runs = [run(ny(day, 10, 30)) for day in (10, 11, 14, 15, 16)]

    result = timing(ny(24, 12), current=early, runs=runs, holidays={date(2026, 9, 25)})

    assert result.days_met_at == ny(23, 16)
    assert result.next_scheduled == ny(24, 16, 15)  # Thursday, the last close of that week
