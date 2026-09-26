from decimal import Decimal

import httpx
import pytest

from trade_simulator.adapters.finnhub_market_data import FinnhubMarketData
from trade_simulator.core.errors import MarketDataError

API_KEY = "test-key-123"


def quote(price):
    return {"c": price, "d": 0, "dp": 0, "h": price, "l": price, "o": price, "pc": price, "t": 1790000000}


def make_client(handler, max_retries=2):
    sleeps = []
    client = FinnhubMarketData(
        api_key=API_KEY,
        transport=httpx.MockTransport(handler),
        max_retries=max_retries,
        sleep=sleeps.append,
    )
    return client, sleeps


def test_returns_current_price_per_symbol_as_exact_decimal():
    prices = {"AAPL": 200.15, "MSFT": 410.5}

    def handler(request):
        return httpx.Response(200, json=quote(prices[request.url.params["symbol"]]))

    client, _ = make_client(handler)

    assert client.get_prices(["AAPL", "MSFT"]) == {
        "AAPL": Decimal("200.15"),
        "MSFT": Decimal("410.5"),
    }


def test_api_key_is_sent_as_header_never_in_url():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=quote(100))

    client, _ = make_client(handler)
    client.get_prices(["AAPL"])

    assert seen[0].headers["X-Finnhub-Token"] == API_KEY
    assert API_KEY not in str(seen[0].url)


def test_unknown_symbol_is_left_out():
    # Finnhub answers unknown symbols with a price of 0.
    def handler(request):
        return httpx.Response(200, json=quote(0 if request.url.params["symbol"] == "NOPE" else 50))

    client, _ = make_client(handler)

    assert client.get_prices(["AAPL", "NOPE"]) == {"AAPL": Decimal("50")}


def test_rate_limit_is_retried_with_backoff():
    responses = iter([httpx.Response(429), httpx.Response(429), httpx.Response(200, json=quote(10))])
    client, sleeps = make_client(lambda request: next(responses))

    assert client.get_prices(["AAPL"]) == {"AAPL": Decimal("10")}
    assert sleeps == [1, 2]


def test_gives_up_after_max_retries_without_leaking_key():
    client, sleeps = make_client(lambda request: httpx.Response(503), max_retries=2)

    with pytest.raises(MarketDataError) as error:
        client.get_prices(["AAPL"])

    assert len(sleeps) == 2
    assert API_KEY not in str(error.value)


def test_network_errors_are_retried_then_reported():
    def handler(request):
        raise httpx.ConnectError("connection refused")

    client, sleeps = make_client(handler, max_retries=1)

    with pytest.raises(MarketDataError):
        client.get_prices(["AAPL"])
    assert len(sleeps) == 1


def test_bad_api_key_fails_immediately_without_retry():
    client, sleeps = make_client(lambda request: httpx.Response(401))

    with pytest.raises(MarketDataError, match="API key"):
        client.get_prices(["AAPL"])
    assert sleeps == []


def test_empty_symbol_list_makes_no_requests():
    def handler(request):
        raise AssertionError("no request expected")

    client, _ = make_client(handler)

    assert client.get_prices([]) == {}
