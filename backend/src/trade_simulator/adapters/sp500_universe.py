"""The S&P 500 stock pool (D4), from the maintained open dataset at github.com/datasets/s-and-p-500-companies."""

import csv
import io

import httpx

from trade_simulator.core.errors import MarketDataError

CONSTITUENTS_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"


class Sp500Universe:
    def __init__(self, *, url: str = CONSTITUENTS_URL, transport: httpx.BaseTransport | None = None) -> None:
        self._url = url
        self._transport = transport

    def symbols(self) -> frozenset[str]:
        try:
            with httpx.Client(transport=self._transport, timeout=15, follow_redirects=True) as client:
                response = client.get(self._url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MarketDataError(f"Could not download the S&P 500 list: {exc}") from exc
        rows = csv.DictReader(io.StringIO(response.text))
        return frozenset(row["Symbol"].strip().upper() for row in rows if row.get("Symbol"))
