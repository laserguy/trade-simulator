from datetime import date
from decimal import Decimal

import httpx
import pytest

from trade_simulator.adapters.tiingo_price_history import TiingoPriceHistory
from trade_simulator.application.ports import DailyBar
from trade_simulator.core.errors import MarketDataError

KEY = "tiingo-secret-1"
ROW = {
    "date": "2026-09-25T00:00:00.000Z", "open": 180.1, "high": 184.0, "low": 179.5, "close": 182.4,
    "volume": 1200, "adjClose": 182.4, "adjOpen": 180.1, "adjHigh": 184.0, "adjLow": 179.5, "adjVolume": 1200,
}


def make(handler):
    return TiingoPriceHistory(api_key=KEY, transport=httpx.MockTransport(handler))


def test_daily_bars_are_parsed_exactly():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=[ROW])

    bars = make(handler).daily_bars("NVDA", date(2026, 9, 1))

    assert bars == [
        DailyBar(date(2026, 9, 25), Decimal("180.1"), Decimal("184.0"), Decimal("179.5"), Decimal("182.4"), Decimal("182.4"), 1200)
    ]
    assert seen[0].url.path == "/tiingo/daily/nvda/prices"
    assert seen[0].url.params["startDate"] == "2026-09-01"


def test_key_is_sent_as_header_never_in_url():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=[])

    make(handler).daily_bars("AAPL", date(2026, 9, 1))

    assert seen[0].headers["Authorization"] == f"Token {KEY}"
    assert KEY not in str(seen[0].url)


def test_class_shares_use_tiingo_ticker_format():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=[])

    make(handler).daily_bars("BRK.B", date(2026, 9, 1))

    assert seen[0].url.path == "/tiingo/daily/brk-b/prices"


def test_unknown_symbol_gives_no_bars():
    assert make(lambda r: httpx.Response(404, json={"detail": "Not found"})).daily_bars("NOPE", date(2026, 9, 1)) == []


def test_errors_become_market_data_errors_without_the_key():
    with pytest.raises(MarketDataError) as error:
        make(lambda r: httpx.Response(429)).daily_bars("NVDA", date(2026, 9, 1))

    assert KEY not in str(error.value)


def test_declares_its_request_limit():
    assert make(lambda r: httpx.Response(200, json=[])).max_requests_per_hour == 50
