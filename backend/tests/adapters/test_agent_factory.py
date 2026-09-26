from pathlib import Path

import pytest
from agents.mcp import MCPServerStdio

from trade_simulator.adapters.openai_agents.agent_factory import AgentModels, build_agents
from trade_simulator.adapters.openai_agents.mcp_config import McpServers
from trade_simulator.adapters.openai_agents.prompts import PromptLibrary
from trade_simulator.adapters.openai_agents.toolbox import ResearchToolbox
from trade_simulator.core.errors import ConfigError
from trade_simulator.core.exchange_profile import US_PROFILE

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

    for name in ("trading_agent", "research_agent", "refresh_watchlist"):
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


def test_each_agent_can_get_its_own_model_for_later_agent_specific_choice():
    agents = make_agents(models=AgentModels(trading="gpt-6-sol", research="gpt-6-luna"))

    assert agents.trading.model == "gpt-6-sol"
    assert agents.research.model == agents.watchlist_builder.model == "gpt-6-luna"


def test_watchlist_builder_is_the_research_agent_with_refresh_instructions():
    agents = make_agents()

    assert {t.name for t in agents.watchlist_builder.tools} == {t.name for t in agents.research.tools}
    assert "watchlist" in agents.watchlist_builder.instructions.lower()


def test_mcp_servers_are_attached_per_agent():
    server = MCPServerStdio(params={"command": "c"}, name="market")
    agents = make_agents(McpServers([(server, frozenset({"research"}))]))

    assert agents.research.mcp_servers == [server]
    assert agents.watchlist_builder.mcp_servers == [server]
    assert agents.trading.mcp_servers == []
