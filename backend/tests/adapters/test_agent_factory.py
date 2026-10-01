import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from agents.mcp import MCPServerStdio
from agents.tool_context import ToolContext

from trade_simulator.adapters.openai_agents import agent_factory
from trade_simulator.adapters.openai_agents.agent_factory import AgentModels, build_agents
from trade_simulator.adapters.openai_agents.mcp_config import McpServers
from trade_simulator.adapters.openai_agents.prompts import PromptLibrary
from trade_simulator.adapters.openai_agents.schemas import ResearchReport
from trade_simulator.adapters.openai_agents.state import AgentRunState
from trade_simulator.adapters.openai_agents.toolbox import ResearchToolbox
from trade_simulator.core.errors import ConfigError
from trade_simulator.core.exchange_profile import US_PROFILE
from trade_simulator.core.run_budget import DECISION_RUN_LIMITS, RunBudget
from trade_simulator.core.strategy import StrategySection

PROMPTS_DIR = Path(__file__).parents[2] / "prompts"


def make_agents(mcp=None, models=None):
    return build_agents(
        models=models or AgentModels.same("gpt-6-luna"),
        prompts=PromptLibrary(PROMPTS_DIR),
        toolbox=ResearchToolbox(finnhub=None, search=None),
        profile=US_PROFILE,
        mcp_servers=mcp or McpServers([]),
    )


def test_every_prompt_file_renders_with_exchange_values():
    library = PromptLibrary(PROMPTS_DIR)

    for name in ("trading_agent", "research_agent", "refresh_watchlist", "strategy_review"):
        text = library.render(name, US_PROFILE)
        assert "$" not in text.replace("$1", "")  # no unfilled $placeholders
        assert text.strip()


def test_trading_prompt_states_the_real_rules():
    text = PromptLibrary(PROMPTS_DIR).render("trading_agent", US_PROFILE)

    assert "20%" in text
    assert "S&P 500" in text or "watchlist" in text


def test_missing_prompt_file_is_a_config_error(tmp_path):
    with pytest.raises(ConfigError):
        PromptLibrary(tmp_path).render("trading_agent", US_PROFILE)


def test_agents_get_their_tools_and_model():
    agents = make_agents()

    trading_tools = {t.name for t in agents.trading.tools}
    research_tools = {t.name for t in agents.research.tools}
    assert trading_tools == {"ask_research_agent"}
    assert research_tools == {"get_quotes", "get_company_news", "get_market_news", "get_key_metrics", "web_search"}
    assert agents.trading.model == agents.research.model == "gpt-6-luna"


def test_every_research_request_carries_the_holdings_note(monkeypatch):
    requests = []

    async def fake_run(agent, request, **kwargs):
        requests.append(request)
        usage = SimpleNamespace(input_tokens=1, output_tokens=1)
        return SimpleNamespace(final_output=ResearchReport(findings=[]), context_wrapper=SimpleNamespace(usage=usage))

    monkeypatch.setattr(agent_factory.Runner, "run", fake_run)
    state = AgentRunState(budget=RunBudget(DECISION_RUN_LIMITS), research_note="Current holdings…")
    [ask_research_agent] = make_agents().trading.tools
    arguments = '{"request": "Check AAPL"}'
    context = ToolContext(context=state, tool_name="ask_research_agent", tool_call_id="call-1", tool_arguments=arguments)

    asyncio.run(ask_research_agent.on_invoke_tool(context, arguments))

    assert requests == ["Check AAPL\n\nCurrent holdings…"]


def test_each_agent_can_get_its_own_model_for_later_agent_specific_choice():
    agents = make_agents(models=AgentModels(trading="gpt-6-sol", research="gpt-6-luna"))

    assert agents.trading.model == "gpt-6-sol"
    assert agents.research.model == agents.watchlist_builder.model == "gpt-6-luna"


def test_watchlist_builder_is_the_research_agent_with_refresh_instructions():
    agents = make_agents()

    assert {t.name for t in agents.watchlist_builder.tools} == {t.name for t in agents.research.tools}
    assert "watchlist" in agents.watchlist_builder.instructions.lower()


def test_the_strategy_review_is_the_trading_agent_with_no_tools():
    agents = make_agents(models=AgentModels(trading="gpt-6-sol", research="gpt-6-luna"))

    reviewer = agents.strategy_reviewer
    assert reviewer.name == "Trading Agent (strategy review)"
    assert (reviewer.tools, reviewer.mcp_servers, reviewer.model) == ([], [], "gpt-6-sol")


def test_section_names_in_the_prompts_come_from_the_code():
    library = PromptLibrary(PROMPTS_DIR)
    names = [f"`{s.value}`" for s in StrategySection]

    trading = library.render("trading_agent", US_PROFILE)
    review = library.render("strategy_review", US_PROFILE)

    assert ", ".join(names[:-1]) + f" or {names[-1]}" in trading
    assert "`follows`" in trading and '`"deviation"`' in trading
    assert all(f"- {name}:" in review for name in names)


def test_the_review_prompt_states_the_real_limits():
    text = PromptLibrary(PROMPTS_DIR).render("strategy_review", US_PROFILE)

    assert "at most 60 words" in text
    assert "at least 10 trading days and 5 trading runs" in text
    assert "20%" in text


def test_mcp_servers_are_attached_per_agent():
    server = MCPServerStdio(params={"command": "c"}, name="market")
    agents = make_agents(McpServers([(server, frozenset({"research"}))]))

    assert agents.research.mcp_servers == [server]
    assert agents.watchlist_builder.mcp_servers == [server]
    assert agents.trading.mcp_servers == []
    assert agents.strategy_reviewer.mcp_servers == []
