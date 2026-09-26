from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from trade_simulator.adapters.exchange_calendar import ExchangeCalendar
from trade_simulator.application.run_mode import RunMode
from trade_simulator.application.schedule import Schedule
from trade_simulator.application.scheduler import Scheduler
from trade_simulator.core.decision_log import RunTrigger
from trade_simulator.core.exchange_profile import US_PROFILE

NY = ZoneInfo("America/New_York")


def ny(month, day, hour, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=NY)


class ModeStub:
    def __init__(self, mode):
        self.mode = mode

    def get(self):
        return self.mode


@pytest.fixture(scope="module")
def schedule():
    return Schedule(ExchangeCalendar(US_PROFILE))


def test_daily_mode_triggers_once_at_the_open(schedule):
    scheduler = Scheduler(schedule, ModeStub(RunMode.DAILY), now=ny(9, 28, 9))

    assert scheduler.due(ny(9, 28, 9, 29)).run is None
    assert scheduler.due(ny(9, 28, 9, 30)).run is RunTrigger.DAILY
    assert scheduler.due(ny(9, 28, 9, 31)).run is None


def test_15_minute_mode_triggers_every_quarter_hour(schedule):
    scheduler = Scheduler(schedule, ModeStub(RunMode.EVERY_15_MIN), now=ny(9, 28, 10, 1))

    triggers = [scheduler.due(ny(9, 28, 10, 1) + timedelta(minutes=m)).run for m in range(0, 31)]

    assert triggers.count(RunTrigger.EVERY_15_MIN) == 2  # 10:15 and 10:30


def test_manual_mode_never_triggers(schedule):
    scheduler = Scheduler(schedule, ModeStub(RunMode.MANUAL), now=ny(9, 28, 9))

    assert scheduler.due(ny(9, 28, 12)).run is None


def test_switching_mode_takes_effect_from_the_next_slot(schedule):
    mode = ModeStub(RunMode.MANUAL)
    scheduler = Scheduler(schedule, mode, now=ny(9, 28, 10, 1))
    mode.mode = RunMode.EVERY_15_MIN

    assert scheduler.due(ny(9, 28, 10, 5)).run is None
    assert scheduler.due(ny(9, 28, 10, 15)).run is RunTrigger.EVERY_15_MIN


def test_value_snapshot_is_due_once_at_each_close_in_every_mode(schedule):
    scheduler = Scheduler(schedule, ModeStub(RunMode.MANUAL), now=ny(9, 28, 15))

    assert scheduler.due(ny(9, 28, 15, 59)).snapshot is False
    assert scheduler.due(ny(9, 28, 16)).snapshot is True
    assert scheduler.due(ny(9, 28, 16, 1)).snapshot is False


def test_a_missed_slot_after_sleep_runs_once_not_many_times(schedule):
    scheduler = Scheduler(schedule, ModeStub(RunMode.EVERY_15_MIN), now=ny(9, 28, 10, 1))

    # The computer slept for an hour: one catch-up run, not four.
    assert scheduler.due(ny(9, 28, 11, 5)).run is RunTrigger.EVERY_15_MIN
    assert scheduler.due(ny(9, 28, 11, 6)).run is None
