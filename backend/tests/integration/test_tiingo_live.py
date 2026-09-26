"""Opt-in: calls the real Tiingo API (free). Run with `uv run pytest -m integration` and TIINGO_API_KEY set."""

import os
from datetime import date, timedelta

import pytest
from dotenv import load_dotenv

from trade_simulator.adapters.config import BACKEND_DIR
from trade_simulator.adapters.tiingo_price_history import TiingoPriceHistory

load_dotenv(BACKEND_DIR / ".env")
pytestmark = pytest.mark.integration


@pytest.mark.skipif(not os.environ.get("TIINGO_API_KEY"), reason="TIINGO_API_KEY not set")
def test_real_daily_history_for_spy():
    bars = TiingoPriceHistory(os.environ["TIINGO_API_KEY"]).daily_bars("SPY", date.today() - timedelta(days=14))

    assert len(bars) >= 5
    assert all(b.adj_close > 0 for b in bars)
