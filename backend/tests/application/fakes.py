"""In-memory stand-ins for the ports, so use cases can be tested without AI, network, or clock (D18)."""

from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from trade_simulator.application.ports import AgentDecision, AgentUsage, WatchlistProposal
from trade_simulator.core.errors import MarketDataError

NEW_YORK = ZoneInfo("America/New_York")


class FakeMarketData:
    def __init__(self, prices=None, error=None):
        self.prices = {k: Decimal(v) for k, v in (prices or {}).items()}
        self.error = error
        self.requested = []

    def get_prices(self, symbols):
        symbols = list(symbols)
        self.requested.append(symbols)
        if self.error:
            raise self.error
        return {s: self.prices[s] for s in symbols if s in self.prices}


class FakeCalendar:
    def __init__(self, open_=True):
        self.open = open_

    def is_open(self, moment):
        return self.open

    def next_open(self, moment):
        return moment + timedelta(hours=12)

    def next_close(self, moment):
        return moment + timedelta(hours=6)


class WeekdayCalendar:
    """Sessions Monday to Friday closing at 16:00 New York time, minus the given holidays."""

    def __init__(self, holidays=()):
        self.holidays = set(holidays)

    def is_open(self, moment):
        return False

    def next_open(self, moment):
        raise NotImplementedError

    def next_close(self, moment):
        local = moment.astimezone(NEW_YORK)
        day = local.date()
        while True:
            close = datetime.combine(day, time(16), NEW_YORK)
            if day.weekday() < 5 and day not in self.holidays and close > local:
                return close
            day += timedelta(days=1)


class FakeAgent:
    """Returns scripted decisions; records what it was asked."""

    def __init__(self, decision=None, proposal=None, error=None, review=None):
        self.decision = decision
        self.proposal = proposal
        self.error = error
        self.review = review
        self.decision_contexts = []
        self.refresh_contexts = []
        self.review_contexts = []

    async def decide(self, context):
        self.decision_contexts.append(context)
        if self.error:
            raise self.error
        return self.decision

    async def build_watchlist(self, context):
        self.refresh_contexts.append(context)
        if self.error:
            raise self.error
        return self.proposal

    async def review_strategy(self, context):
        self.review_contexts.append(context)
        if self.error:
            raise self.error
        return self.review


class FakeUniverse:
    def __init__(self, symbols=("AAPL", "MSFT", "NVDA"), error=None):
        self._symbols = frozenset(symbols)
        self.error = error

    def symbols(self):
        if self.error:
            raise self.error
        return self._symbols


class FixedClock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self):
        return self.now


def decision(orders=(), findings=(), trace_id="trace_1", usage=AgentUsage(100, 20, 2)):
    return AgentDecision(orders=tuple(orders), findings=tuple(findings), usage=usage, trace_id=trace_id)


def proposal(entries, findings=(), trace_id="trace_r", usage=AgentUsage(500, 80, 12)):
    return WatchlistProposal(entries=tuple(entries), findings=tuple(findings), usage=usage, trace_id=trace_id)


MARKET_DOWN = MarketDataError("Finnhub unreachable")
