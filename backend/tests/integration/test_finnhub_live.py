"""Opt-in: calls the real Finnhub API. Run with `uv run pytest -m integration` and FINNHUB_API_KEY set."""

import os

import pytest
from dotenv import load_dotenv

from trade_simulator.adapters.finnhub_market_data import FinnhubMarketData

load_dotenv()
pytestmark = pytest.mark.integration


@pytest.mark.skipif(not os.environ.get("FINNHUB_API_KEY"), reason="FINNHUB_API_KEY not set")
def test_real_quote_for_spy():
    client = FinnhubMarketData(api_key=os.environ["FINNHUB_API_KEY"])

    prices = client.get_prices(["SPY"])

    assert prices["SPY"] > 0


@pytest.mark.skipif(not os.environ.get("FINNHUB_API_KEY"), reason="FINNHUB_API_KEY not set")
def test_real_market_news_is_on_the_free_plan():
    client = FinnhubMarketData(api_key=os.environ["FINNHUB_API_KEY"])

    items = client.market_news()

    assert 0 < len(items) <= 25
    assert all(item.headline and item.url for item in items)
