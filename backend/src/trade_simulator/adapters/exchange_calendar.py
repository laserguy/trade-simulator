"""Market open/closed status from the official exchange calendar, including holidays and early closes (D21)."""

from datetime import datetime
from zoneinfo import ZoneInfo

import exchange_calendars
import pandas as pd

from trade_simulator.core.exchange_profile import ExchangeProfile


class ExchangeCalendar:
    def __init__(self, profile: ExchangeProfile) -> None:
        self._calendar = exchange_calendars.get_calendar(profile.calendar_code)
        self._timezone = ZoneInfo(profile.timezone)

    def is_open(self, moment: datetime) -> bool:
        return bool(self._calendar.is_open_on_minute(_to_utc_timestamp(moment)))

    def next_open(self, moment: datetime) -> datetime:
        opening = self._calendar.next_open(_to_utc_timestamp(moment))
        return opening.to_pydatetime().astimezone(self._timezone)

    def next_close(self, moment: datetime) -> datetime:
        closing = self._calendar.next_close(_to_utc_timestamp(moment))
        return closing.to_pydatetime().astimezone(self._timezone)


def _to_utc_timestamp(moment: datetime) -> pd.Timestamp:
    if moment.tzinfo is None:
        raise ValueError("Datetime must be timezone-aware")
    return pd.Timestamp(moment).tz_convert("UTC")
