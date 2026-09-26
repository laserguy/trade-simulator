from datetime import date
from decimal import Decimal

import httpx

from trade_simulator.adapters.finnhub_market_data import FinnhubMarketData, Quote


def make_client(handler):
    return FinnhubMarketData(api_key="k", transport=httpx.MockTransport(handler), sleep=lambda s: None)


def test_get_quotes_includes_daily_change():
    def handler(request):
        return httpx.Response(200, json={"c": 110.0, "dp": 10.0, "pc": 100.0})

    quotes = make_client(handler).get_quotes(["AAPL"])

    assert quotes == {"AAPL": Quote("AAPL", Decimal("110.0"), Decimal("10.0"), Decimal("100.0"))}


def test_company_news_queries_date_range_and_maps_items():
    seen = []

    def handler(request):
        seen.append(request.url.params)
        return httpx.Response(
            200,
            json=[{"headline": "H", "source": "S", "url": "https://n", "summary": "Sum", "datetime": 1790000000}],
        )

    items = make_client(handler).company_news("AAPL", date(2026, 9, 21), date(2026, 9, 28))

    assert seen[0]["from"] == "2026-09-21" and seen[0]["to"] == "2026-09-28"
    assert items[0].headline == "H"
    assert items[0].published_at.startswith("2026-")


def test_company_news_is_capped():
    def handler(request):
        item = {"headline": "H", "source": "S", "url": "u", "summary": "s", "datetime": 1790000000}
        return httpx.Response(200, json=[item] * 50)

    assert len(make_client(handler).company_news("AAPL", date(2026, 9, 21), date(2026, 9, 28))) == 10


def test_market_news_asks_for_general_news_newest_first_capped_and_trimmed():
    seen = []

    def handler(request):
        seen.append(request.url)
        items = [
            {"headline": f"H{i}", "source": "S", "url": f"https://n/{i}", "summary": "x" * 1000, "datetime": 1790000000 + i}
            for i in range(40)
        ]
        return httpx.Response(200, json=items)

    items = make_client(handler).market_news()

    assert seen[0].path.endswith("/news") and seen[0].params["category"] == "general"
    assert len(items) == 25
    assert items[0].headline == "H39"  # newest first
    assert len(items[0].summary) <= 300


def test_basic_metrics_returns_selected_metrics_only():
    def handler(request):
        return httpx.Response(200, json={"metric": {"peTTM": 30.1, "beta": 1.2, "someNoise": 5}})

    metrics = make_client(handler).basic_metrics("AAPL")

    assert metrics == {"peTTM": 30.1, "beta": 1.2}
