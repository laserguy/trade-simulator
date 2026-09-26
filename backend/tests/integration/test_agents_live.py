"""Opt-in: runs the real agents against OpenAI, Finnhub and Tavily. Costs a little money.

Run with `uv run pytest -m integration`. Finnhub/Tavily keys come from backend/.env; the OpenAI key for
this test comes from the OPENAI_API_KEY environment variable and is saved into the test's own
temporary Settings (the app itself only reads LLM keys from Settings, D9).
"""

import asyncio
import os
from datetime import datetime, timezone

import pytest
from dotenv import load_dotenv

from trade_simulator.adapters.bootstrap import build_services
from trade_simulator.adapters.config import BACKEND_DIR, load_config
from trade_simulator.core.decision_log import RunStatus

load_dotenv(BACKEND_DIR / ".env")
pytestmark = pytest.mark.integration
KEYS = ("OPENAI_API_KEY", "FINNHUB_API_KEY", "TAVILY_API_KEY")


@pytest.mark.skipif(not all(os.environ.get(k) for k in KEYS), reason="API keys not set")
def test_real_watchlist_refresh(tmp_path):
    config = load_config(base_dir=tmp_path)
    services = build_services(config)
    services.settings.set_api_key("openai", os.environ["OPENAI_API_KEY"])

    run = asyncio.run(services.watchlist_refresher.refresh())

    assert run.status is RunStatus.COMPLETED, run.failure_reason
    assert run.trace_id
    assert 1 <= len(services.repository.load_watchlist().entries) <= 20
    assert run.cost.searches <= 20
