from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from trade_simulator.adapters.exchange_calendar import ExchangeCalendar
from trade_simulator.application.run_mode import RunMode
from trade_simulator.application.schedule import Schedule
from trade_simulator.core.exchange_profile import US_PROFILE

NY = ZoneInfo("America/New_York")


def ny(month, day, hour, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=NY)


@pytest.fixture(scope="module")
def schedule():
    return Schedule(ExchangeCalendar(US_PROFILE))


def test_manual_mode_has_no_scheduled_runs(schedule):
    assert schedule.next_run(RunMode.MANUAL, ny(9, 28, 10)) is None


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (ny(9, 26, 12), ny(9, 28, 9, 30)),  # Saturday -> Monday open
        (ny(9, 28, 8), ny(9, 28, 9, 30)),  # Monday before open -> today
        (ny(9, 28, 10), ny(9, 29, 9, 30)),  # already open today -> tomorrow
        (ny(11, 25, 17), ny(11, 27, 9, 30)),  # skips Thanksgiving
    ],
)
def test_daily_runs_at_the_next_market_open(schedule, now, expected):
    assert schedule.next_run(RunMode.DAILY, now) == expected


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (ny(9, 28, 10, 7), ny(9, 28, 10, 15)),  # next quarter hour
        (ny(9, 28, 10, 15), ny(9, 28, 10, 30)),  # strictly after now
        (ny(9, 28, 15, 50), ny(9, 29, 9, 30)),  # 16:00 is the close, not a run
        (ny(9, 26, 12), ny(9, 28, 9, 30)),  # weekend -> Monday open
        (ny(11, 27, 12, 50), ny(11, 30, 9, 30)),  # early close at 13:00
    ],
)
def test_every_15_minutes_runs_on_quarter_hours_while_open(schedule, now, expected):
    assert schedule.next_run(RunMode.EVERY_15_MIN, now) == expected


def test_daily_close_snapshot_is_at_the_next_close(schedule):
    assert schedule.next_close(ny(9, 28, 10)) == ny(9, 28, 16)
    assert schedule.next_close(ny(11, 27, 9)) == ny(11, 27, 13)
    assert schedule.next_close(ny(9, 26, 12)) == ny(9, 28, 16)
