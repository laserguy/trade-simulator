import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from trade_simulator.adapters.openai_agents import trading_agents
from trade_simulator.adapters.openai_agents.mcp_config import McpServers
from trade_simulator.adapters.openai_agents.prompts import PromptLibrary
from trade_simulator.adapters.openai_agents.schemas import WatchlistResult
from trade_simulator.adapters.openai_agents.toolbox import ResearchToolbox
from trade_simulator.application.ports import RefreshContext
from trade_simulator.application.settings import ModelSelection
from trade_simulator.core.errors import AgentError
from trade_simulator.core.exchange_profile import US_PROFILE
from trade_simulator.core.model_pricing import ModelOption
from trade_simulator.core.run_budget import REFRESH_RUN_LIMITS

PROMPTS_DIR = Path(__file__).parents[2] / "prompts"
CALLS = [(1000, 50), (2000, 80)]


def make_agents():
    option = ModelOption("openai", "gpt-6-luna", "gpt-6-luna", Decimal("1"), Decimal("1"))
    return trading_agents.OpenAITradingAgents(
        model_selection=lambda: ModelSelection(option, "key", None),
        toolbox=ResearchToolbox(finnhub=None, search=None),
        prompts=PromptLibrary(PROMPTS_DIR),
        profile=US_PROFILE,
        mcp_servers=McpServers([]),
    )


def refresh_context():
    return RefreshContext(
        profile=US_PROFILE,
        limits=REFRESH_RUN_LIMITS,
        stock_pool=frozenset({"AAPL"}),
        current_watchlist=None,
        now=datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc),
    )


def fake_runner(monkeypatch, *, then_fail: bool):
    """Makes two model calls through the run's hooks, then fails or returns, like the SDK's Runner.run."""

    async def fake_run(agent, input_text, *, context, hooks, **kwargs):
        wrapper = SimpleNamespace(context=context)
        for tokens_in, tokens_out in CALLS:
            usage = SimpleNamespace(input_tokens=tokens_in, output_tokens=tokens_out)
            await hooks.on_llm_end(wrapper, agent, SimpleNamespace(usage=usage))
        if then_fail:
            raise ConnectionError("Server disconnected without sending a response")
        total = SimpleNamespace(input_tokens=3000, output_tokens=130)
        output = WatchlistResult(market_overview="Calm", market_sources=[], picks=[])
        return SimpleNamespace(final_output=output, context_wrapper=SimpleNamespace(usage=total))

    monkeypatch.setattr(trading_agents.Runner, "run", fake_run)


def test_a_failed_run_keeps_the_tokens_its_finished_model_calls_spent(monkeypatch):
    fake_runner(monkeypatch, then_fail=True)

    with pytest.raises(AgentError) as failure:
        asyncio.run(make_agents().build_watchlist(refresh_context()))

    usage = failure.value.usage
    assert (usage.input_tokens, usage.output_tokens) == (3000, 130)


def test_a_finished_run_counts_each_model_call_once(monkeypatch):
    fake_runner(monkeypatch, then_fail=False)

    proposal = asyncio.run(make_agents().build_watchlist(refresh_context()))

    assert (proposal.usage.input_tokens, proposal.usage.output_tokens) == (3000, 130)
