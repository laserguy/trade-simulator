"""When a strategy review may run, and when the weekly scheduled one is due (D43)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from trade_simulator.application.ports import MarketCalendar
from trade_simulator.core.decision_log import DecisionRun, RunStatus
from trade_simulator.core.strategy import StrategyVersion
from trade_simulator.core.strategy_review import STRATEGY_REVIEW_MINIMUMS, ReviewMinimums, StrategyReview

# The scheduled review runs this long after the week's last close, once the day's close is recorded (D33).
SCHEDULED_REVIEW_DELAY = timedelta(minutes=15)
_TICK = timedelta(microseconds=1)


@dataclass(frozen=True)
class ReviewTiming:
    first: bool  # no strategy yet: the first one may be written at any time
    can_review: bool  # the button is enabled
    due: bool  # the scheduler should start a review now
    trading_days: int  # done in the current period, at most the minimum
    trading_runs: int
    minimums: ReviewMinimums
    days_met_at: datetime | None  # the close at which the day minimum is (or will be) met
    next_scheduled: datetime | None


def review_timing(
    *,
    current: StrategyVersion | None,
    reviews: Sequence[StrategyReview],
    runs: Sequence[DecisionRun],
    calendar: MarketCalendar,
    now: datetime,
    minimums: ReviewMinimums = STRATEGY_REVIEW_MINIMUMS,
) -> ReviewTiming:
    """`runs` may include any runs; only completed ones following the current version count."""
    if current is None:
        return ReviewTiming(True, True, False, 0, 0, minimums, None, None)

    start = _period_start(current, reviews)
    closes = _closes_after(calendar, start, minimums.trading_days)
    counted = sorted(
        (r.started_at for r in runs
         if r.strategy_version == current.number and r.status is RunStatus.COMPLETED and r.started_at >= start)
    )
    days_done = sum(1 for close in closes if close <= now)
    days_met_at = closes[-1] if closes else start
    runs_met_at = counted[minimums.trading_runs - 1] if len(counted) >= minimums.trading_runs else None
    can_review = days_done >= minimums.trading_days and runs_met_at is not None

    met_at = max(days_met_at, runs_met_at) if can_review else days_met_at
    last_slot = _last_slot_since(calendar, met_at, now) if can_review else None
    return ReviewTiming(
        first=False,
        can_review=can_review,
        due=last_slot is not None and not any(review.started_at >= last_slot for review in reviews),
        trading_days=days_done,
        trading_runs=min(len(counted), minimums.trading_runs),
        minimums=minimums,
        days_met_at=days_met_at,
        next_scheduled=_slot_on_or_after(calendar, max(met_at, now)),
    )


def _period_start(current: StrategyVersion, reviews: Sequence[StrategyReview]) -> datetime:
    """A version's period starts when it was written, and again after each completed review that kept it.
    Failed reviews don't count."""
    kept = [
        review.started_at
        for review in reviews
        if review.reviewed_version == current.number and review.status is RunStatus.COMPLETED
    ]
    return max([current.started_at, *kept])


def _closes_after(calendar: MarketCalendar, start: datetime, count: int) -> list[datetime]:
    closes, moment = [], start
    for _ in range(count):
        moment = calendar.next_close(moment)
        closes.append(moment)
    return closes


def _slot_on_or_after(calendar: MarketCalendar, moment: datetime) -> datetime:
    """The first weekly review slot (the week's last close, plus the delay) at or after `moment`."""
    close = calendar.next_close(moment - SCHEDULED_REVIEW_DELAY - _TICK)
    while not _is_last_close_of_week(calendar, close):
        close = calendar.next_close(close)
    return close + SCHEDULED_REVIEW_DELAY


def _last_slot_since(calendar: MarketCalendar, since: datetime, now: datetime) -> datetime | None:
    """The latest slot between `since` and `now`, or None if there was none."""
    latest, slot = None, _slot_on_or_after(calendar, since)
    while slot <= now:
        latest, slot = slot, _slot_on_or_after(calendar, slot + _TICK)
    return latest


def _is_last_close_of_week(calendar: MarketCalendar, close: datetime) -> bool:
    return calendar.next_close(close).isocalendar()[:2] != close.isocalendar()[:2]
