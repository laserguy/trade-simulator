"""Builds the Trading Agent, the Research Agent, and the Research Agent's watchlist-building variant (D12, D14)."""

import asyncio
from dataclasses import dataclass

from agents import Agent, Model, RunContextWrapper, Runner, function_tool

from trade_simulator.adapters.openai_agents.inputs import with_research_note
from trade_simulator.adapters.openai_agents.mcp_config import McpServers
from trade_simulator.adapters.openai_agents.prompts import PromptLibrary
from trade_simulator.adapters.openai_agents.schemas import (
    ResearchReport,
    StrategyReviewResult,
    TradingDecision,
    WatchlistResult,
    to_findings,
)
from trade_simulator.adapters.openai_agents.state import AgentRunState
from trade_simulator.adapters.openai_agents.toolbox import ResearchToolbox
from trade_simulator.core.errors import BudgetExceededError
from trade_simulator.core.exchange_profile import ExchangeProfile

RESEARCH_MAX_TURNS = 12


@dataclass(frozen=True)
class AgentSet:
    trading: Agent
    research: Agent
    watchlist_builder: Agent
    strategy_reviewer: Agent  # the Trading Agent reviewing its own strategy: same model, no tools (D43)


@dataclass(frozen=True)
class AgentModels:
    """The model per agent. v1 uses one model for all (D9); agent-specific models are parked for later."""

    trading: str | Model
    research: str | Model

    @classmethod
    def same(cls, model: str | Model) -> "AgentModels":
        return cls(trading=model, research=model)


def build_agents(
    *,
    models: AgentModels,
    prompts: PromptLibrary,
    toolbox: ResearchToolbox,
    profile: ExchangeProfile,
    mcp_servers: McpServers,
) -> AgentSet:
    research = Agent(
        name="Research Agent",
        instructions=prompts.render("research_agent", profile),
        model=models.research,
        tools=_research_tools(toolbox),
        mcp_servers=mcp_servers.for_agent("research"),
        output_type=ResearchReport,
    )
    watchlist_builder = research.clone(
        name="Research Agent (watchlist refresh)",
        instructions=research.instructions + "\n\n" + prompts.render("refresh_watchlist", profile),
        output_type=WatchlistResult,
    )
    trading = Agent(
        name="Trading Agent",
        instructions=prompts.render("trading_agent", profile),
        model=models.trading,
        tools=[_ask_research_agent_tool(research)],
        mcp_servers=mcp_servers.for_agent("trading"),
        output_type=TradingDecision,
    )
    strategy_reviewer = Agent(
        name="Trading Agent (strategy review)",
        instructions=prompts.render("strategy_review", profile),
        model=models.trading,
        output_type=StrategyReviewResult,
    )
    return AgentSet(
        trading=trading, research=research, watchlist_builder=watchlist_builder, strategy_reviewer=strategy_reviewer
    )


def _research_tools(toolbox: ResearchToolbox) -> list:
    @function_tool
    async def get_quotes(ctx: RunContextWrapper[AgentRunState], symbols: list[str]) -> str:
        """Current price, today's percent change and previous close for up to 25 stock symbols.

        Args:
            symbols: Ticker symbols, e.g. ["AAPL", "MSFT"].
        """
        return await asyncio.to_thread(toolbox.quotes, ctx.context, symbols)

    @function_tool
    async def get_company_news(ctx: RunContextWrapper[AgentRunState], symbol: str, days: int) -> str:
        """Recent company news headlines and summaries from Finnhub (free, no search limit).

        Args:
            symbol: Ticker symbol, e.g. "AAPL".
            days: How many days back to look, 1 to 30.
        """
        return await asyncio.to_thread(toolbox.company_news, ctx.context, symbol, days)

    @function_tool
    async def get_market_news(ctx: RunContextWrapper[AgentRunState]) -> str:
        """The newest general market headlines: economy, central banks, politics, geopolitics, regulation.

        Free, no search limit. Use it first to find the events that can move the stocks you research.
        """
        return await asyncio.to_thread(toolbox.market_news, ctx.context)

    @function_tool
    async def get_key_metrics(ctx: RunContextWrapper[AgentRunState], symbol: str) -> str:
        """Key fundamentals: market cap, P/E, growth, margins, dividend yield, beta, 52-week range.

        Args:
            symbol: Ticker symbol, e.g. "AAPL".
        """
        return await asyncio.to_thread(toolbox.key_metrics, ctx.context, symbol)

    @function_tool
    async def web_search(ctx: RunContextWrapper[AgentRunState], query: str) -> str:
        """Search recent web news. Limited per run: use it for what Finnhub news can't answer.

        Args:
            query: A focused search query, e.g. "NVIDIA data center demand September 2026".
        """
        return await asyncio.to_thread(toolbox.web_search, ctx.context, query)

    return [get_quotes, get_company_news, get_market_news, get_key_metrics, web_search]


def _ask_research_agent_tool(research: Agent):
    @function_tool
    async def ask_research_agent(ctx: RunContextWrapper[AgentRunState], request: str) -> str:
        """Ask the Research Agent to research stocks. Limited calls per run: batch related questions.

        Args:
            request: What to research, e.g. "Check news and price moves for AAPL and MSFT today."
        """
        state = ctx.context
        try:
            state.budget.use_research_call()
        except BudgetExceededError as exc:
            return f"{exc}. Decide with the research you already have."
        result = await Runner.run(
            research,
            with_research_note(request, state.research_note),
            context=state,
            run_config=state.run_config,
            hooks=state.hooks,
            max_turns=RESEARCH_MAX_TURNS,
        )
        state.add_usage(result.context_wrapper.usage)
        report: ResearchReport = result.final_output
        state.findings.extend(to_findings(report.findings, state.tool_urls, state.quotes))
        return report.model_dump_json()

    return ask_research_agent
