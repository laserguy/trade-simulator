"""When scheduled runs happen (D3), only while the market is open (D21)."""

from datetime import datetime, timedelta

from trade_simulator.application.ports import MarketCalendar
from trade_simulator.application.run_mode import RunMode

QUARTER_HOUR = timedelta(minutes=15)


class Schedule:
    def __init__(self, calendar: MarketCalendar) -> None:
        self._calendar = calendar

    def next_run(self, mode: RunMode, after: datetime) -> datetime | None:
        """The next scheduled run strictly after `after`, or None in Manual mode."""
        if mode is RunMode.DAILY:
            return self._calendar.next_open(after)
        if mode is RunMode.EVERY_15_MIN:
            candidate = _next_quarter_hour(after)
            return candidate if self._calendar.is_open(candidate) else self._calendar.next_open(candidate)
        return None

    def next_close(self, after: datetime) -> datetime:
        """The next market close strictly after `after`: when the daily value point is recorded (D33)."""
        return self._calendar.next_close(after)


def _next_quarter_hour(moment: datetime) -> datetime:
    floored = moment.replace(minute=moment.minute - moment.minute % 15, second=0, microsecond=0)
    return floored + QUARTER_HOUR
