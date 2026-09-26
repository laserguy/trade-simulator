from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from trade_simulator.adapters.exchange_calendar import ExchangeCalendar
from trade_simulator.core.exchange_profile import US_PROFILE

NEW_YORK = ZoneInfo("America/New_York")


def ny(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=NEW_YORK)


@pytest.fixture(scope="module")
def calendar():
    return ExchangeCalendar(US_PROFILE)


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (ny(2026, 9, 28, 10), True),  # Monday mid-morning
        (ny(2026, 9, 28, 9, 0), False),  # before the 9:30 open
        (ny(2026, 9, 28, 16, 30), False),  # after the 4:00 close
        (ny(2026, 9, 26, 12), False),  # Saturday
        (ny(2026, 11, 26, 12), False),  # Thanksgiving holiday
        (ny(2026, 11, 27, 12), True),  # day after Thanksgiving, before the early close
        (ny(2026, 11, 27, 14), False),  # after the 1:00 early close
    ],
)
def test_is_open(calendar, moment, expected):
    assert calendar.is_open(moment) is expected


def test_next_open_skips_the_weekend(calendar):
    assert calendar.next_open(ny(2026, 9, 25, 17)) == ny(2026, 9, 28, 9, 30)


def test_next_open_skips_holidays(calendar):
    assert calendar.next_open(ny(2026, 11, 25, 17)) == ny(2026, 11, 27, 9, 30)


def test_next_open_is_returned_in_exchange_timezone(calendar):
    assert calendar.next_open(ny(2026, 9, 25, 17)).tzinfo == NEW_YORK


def test_naive_datetimes_are_refused(calendar):
    with pytest.raises(ValueError):
        calendar.is_open(datetime(2026, 9, 28, 10))
