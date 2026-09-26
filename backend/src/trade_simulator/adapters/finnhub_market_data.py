"""Finnhub implementation of the MarketData port (D7).

The API key travels in a header, never in the URL, so it can't leak into logs or error messages (D19).
"""

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

import httpx

from trade_simulator.application.ports import Quote
from trade_simulator.core.errors import MarketDataError

__all__ = ["FinnhubMarketData", "NewsItem", "Quote"]

BASE_URL = "https://finnhub.io/api/v1"
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_NEWS_ITEMS = 10
# General market news (D40): the feed returns ~100 mixed headlines, so keep the newest few, briefly.
MAX_MARKET_NEWS_ITEMS = 25
MAX_MARKET_NEWS_SUMMARY_CHARS = 300
# A focused subset keeps the agent's input (and token cost) small.
KEY_METRICS = (
    "marketCapitalization",
    "peTTM",
    "pbQuarterly",
    "epsGrowthTTMYoy",
    "revenueGrowthTTMYoy",
    "netProfitMarginTTM",
    "dividendYieldIndicatedAnnual",
    "beta",
    "52WeekHigh",
    "52WeekLow",
    "52WeekPriceReturnDaily",
)


@dataclass(frozen=True)
class NewsItem:
    headline: str
    source: str
    url: str
    summary: str
    published_at: str


class FinnhubMarketData:
    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.BaseTransport | None = None,
        max_retries: int = 2,
        sleep: Callable[[float], None] = time.sleep,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={"X-Finnhub-Token": api_key},
            timeout=timeout_seconds,
            transport=transport,
        )
        self._max_retries = max_retries
        self._sleep = sleep

    def get_prices(self, symbols: Iterable[str]) -> dict[str, Decimal]:
        return {symbol: quote.price for symbol, quote in self.get_quotes(symbols).items()}

    def get_quotes(self, symbols: Iterable[str]) -> dict[str, Quote]:
        quotes = {}
        for symbol in symbols:
            quote = self._quote(symbol)
            if quote is not None:
                quotes[symbol] = quote
        return quotes

    def company_news(self, symbol: str, start: date, end: date) -> list[NewsItem]:
        items = self._get("/company-news", {"symbol": symbol, "from": start.isoformat(), "to": end.isoformat()})
        return [_news_item(item) for item in items[:MAX_NEWS_ITEMS]]

    def market_news(self) -> list[NewsItem]:
        """Newest general market headlines: economy, politics, central banks (D40)."""
        items = sorted(self._get("/news", {"category": "general"}), key=lambda i: i.get("datetime", 0), reverse=True)
        return [_news_item(item, MAX_MARKET_NEWS_SUMMARY_CHARS) for item in items[:MAX_MARKET_NEWS_ITEMS]]

    def basic_metrics(self, symbol: str) -> dict:
        metrics = self._get("/stock/metric", {"symbol": symbol, "metric": "all"}).get("metric") or {}
        return {key: metrics[key] for key in KEY_METRICS if key in metrics}

    def close(self) -> None:
        self._client.close()

    def _quote(self, symbol: str) -> Quote | None:
        data = self._get("/quote", {"symbol": symbol})
        current = data.get("c")
        # Finnhub reports unknown symbols as a price of 0.
        if not current:
            return None
        return Quote(
            symbol=symbol,
            price=_decimal(current),
            change_percent=_decimal(data.get("dp") or 0),
            previous_close=_decimal(data.get("pc") or 0),
        )

    def _get(self, path: str, params: dict[str, str]) -> dict:
        for attempt in range(self._max_retries + 1):
            is_last_attempt = attempt == self._max_retries
            try:
                response = self._client.get(path, params=params)
            except httpx.TransportError as exc:
                if is_last_attempt:
                    raise MarketDataError(f"Finnhub unreachable for {params}: {exc}") from exc
            else:
                if response.status_code in (401, 403):
                    raise MarketDataError("Finnhub rejected the API key")
                if response.status_code not in _RETRYABLE_STATUS:
                    if response.is_error:
                        raise MarketDataError(f"Finnhub returned {response.status_code} for {params}")
                    return response.json()
                if is_last_attempt:
                    raise MarketDataError(
                        f"Finnhub still returning {response.status_code} for {params} "
                        f"after {self._max_retries} retries"
                    )
            self._sleep(2**attempt)
        raise AssertionError("unreachable")


def _decimal(value) -> Decimal:
    # Via str so floats like 200.15 don't become 200.1499999...
    return Decimal(str(value))


def _news_item(item: dict, max_summary_chars: int | None = None) -> NewsItem:
    summary = item.get("summary", "")
    if max_summary_chars is not None and len(summary) > max_summary_chars:
        summary = summary[: max_summary_chars - 1].rstrip() + "…"
    return NewsItem(
        headline=item.get("headline", ""),
        source=item.get("source", ""),
        url=item.get("url", ""),
        summary=summary,
        published_at=datetime.fromtimestamp(item.get("datetime", 0), timezone.utc).isoformat(),
    )
