"""Tiingo implementation of the PriceHistorySource port (D36). The only Tiingo-specific code in the app.

Free plan: 50 requests/hour, 1,000/day, 500 symbols/month, internal (personal) use.
The key travels in a header, never in the URL (D19).
"""

from datetime import date
from decimal import Decimal

import httpx

from trade_simulator.application.ports import DailyBar
from trade_simulator.core.errors import MarketDataError

BASE_URL = "https://api.tiingo.com"


class TiingoPriceHistory:
    name = "tiingo"
    max_requests_per_hour = 50

    def __init__(self, api_key: str, *, transport: httpx.BaseTransport | None = None, timeout_seconds: float = 15.0):
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
            timeout=timeout_seconds,
            transport=transport,
        )

    def daily_bars(self, symbol: str, since: date) -> list[DailyBar]:
        ticker = symbol.lower().replace(".", "-")  # Tiingo writes class shares as brk-b
        try:
            response = self._client.get(f"/tiingo/daily/{ticker}/prices", params={"startDate": since.isoformat()})
        except httpx.TransportError as exc:
            raise MarketDataError(f"Price history provider unreachable for {symbol}: {exc}") from exc
        if response.status_code == 404:
            return []
        if response.is_error:
            raise MarketDataError(f"Price history provider returned {response.status_code} for {symbol}")
        return [_bar(row) for row in response.json()]

    def close(self) -> None:
        self._client.close()


def _bar(row: dict) -> DailyBar:
    return DailyBar(
        day=date.fromisoformat(row["date"][:10]),
        open=_decimal(row["open"]),
        high=_decimal(row["high"]),
        low=_decimal(row["low"]),
        close=_decimal(row["close"]),
        adj_close=_decimal(row["adjClose"]),
        volume=int(row.get("volume") or 0),
    )


def _decimal(value) -> Decimal:
    return Decimal(str(value))
