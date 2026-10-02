"""OpenAI Agents SDK implementation of the TradingAgents port (D8, D9, D12, D20, D25).

The model comes from Settings at the start of every run, so a change in Settings applies to the next run.
Every run is traced when an OpenAI key exists; the trace ID is returned for the decision log.
Any SDK or model failure becomes an AgentError that still carries the trace ID and what was spent.
"""

from collections.abc import Callable
from contextlib import AsyncExitStack

from agents import Agent, RunConfig, Runner, gen_trace_id, set_tracing_export_api_key, trace

from trade_simulator.adapters.openai_agents.agent_factory import AgentModels, AgentSet, build_agents
from trade_simulator.adapters.openai_agents.inputs import (
    render_decision_input,
    render_refresh_input,
    render_research_note,
)
from trade_simulator.adapters.openai_agents.mcp_config import McpServers
from trade_simulator.adapters.openai_agents.models import make_model
from trade_simulator.adapters.openai_agents.prompts import PromptLibrary
from trade_simulator.adapters.openai_agents.review_input import render_review_input
from trade_simulator.adapters.openai_agents.schemas import (
    TradingDecision,
    WatchlistResult,
    to_decision_summary,
    to_market_overview,
    to_orders,
    to_review_proposal,
    to_watchlist_entries,
)
from trade_simulator.adapters.openai_agents.run_hooks import AgentRunHooks
from trade_simulator.adapters.openai_agents.state import AgentRunState
from trade_simulator.adapters.openai_agents.timeline_hooks import TimelineHooks
from trade_simulator.adapters.openai_agents.toolbox import ResearchToolbox
from trade_simulator.application.ports import (
    ActivityReporter,
    AgentDecision,
    DecisionContext,
    RefreshContext,
    ReviewContext,
    ReviewProposal,
    WatchlistProposal,
)
from trade_simulator.application.settings import ModelSelection
from trade_simulator.core.errors import AgentError
from trade_simulator.core.exchange_profile import ExchangeProfile
from trade_simulator.core.run_budget import STRATEGY_REVIEW_LIMITS, RunBudget, RunLimits

TRADING_MAX_TURNS = 10
REFRESH_MAX_TURNS = 40  # a refresh makes many free tool calls while shortlisting
REVIEW_MAX_TURNS = 2  # one answer, no tools (D43)


class OpenAITradingAgents:
    def __init__(
        self,
        *,
        model_selection: Callable[[], ModelSelection],
        toolbox: ResearchToolbox,
        prompts: PromptLibrary,
        profile: ExchangeProfile,
        mcp_servers: McpServers,
        activity: ActivityReporter | None = None,
    ) -> None:
        self._model_selection = model_selection
        self._toolbox = toolbox
        self._prompts = prompts
        self._profile = profile
        self._mcp_servers = mcp_servers
        self._hooks = AgentRunHooks(TimelineHooks(activity) if activity else None)

    async def decide(self, context: DecisionContext) -> AgentDecision:
        agents, state = self._prepare(context.limits)
        state.research_note = render_research_note(context)
        decision, trace_id = await self._run(
            "Decision run", agents.trading, render_decision_input(context), state, TRADING_MAX_TURNS
        )
        decision: TradingDecision
        orders, warnings = to_orders(decision)
        overall = to_decision_summary(decision)
        return AgentDecision(
            orders=tuple(orders),
            findings=(overall, *state.findings, *warnings),
            usage=state.usage(),
            trace_id=trace_id,
        )

    async def build_watchlist(self, context: RefreshContext) -> WatchlistProposal:
        agents, state = self._prepare(context.limits)
        result, trace_id = await self._run(
            "Watchlist refresh", agents.watchlist_builder, render_refresh_input(context), state, REFRESH_MAX_TURNS
        )
        result: WatchlistResult
        return WatchlistProposal(
            entries=tuple(to_watchlist_entries(result, state.tool_urls)),
            findings=(to_market_overview(result, state.tool_urls),),
            usage=state.usage(),
            trace_id=trace_id,
        )

    def _prepare(self, limits: RunLimits) -> tuple[AgentSet, AgentRunState]:
        """Build agents for this run from the current Settings choice."""
        selection = self._model_selection()
        if selection.tracing_api_key:
            set_tracing_export_api_key(selection.tracing_api_key)
        agents = build_agents(
            models=AgentModels.same(make_model(selection)),
            prompts=self._prompts,
            toolbox=self._toolbox,
            profile=self._profile,
            mcp_servers=self._mcp_servers,
        )
        run_config = RunConfig(tracing_disabled=selection.tracing_api_key is None)
        state = AgentRunState(
            budget=RunBudget(limits), run_config=run_config, hooks=self._hooks, model_id=selection.option.model_id
        )
        return agents, state

    async def review_strategy(self, context: ReviewContext) -> ReviewProposal:
        agents, state = self._prepare(STRATEGY_REVIEW_LIMITS)
        result, trace_id = await self._run(
            "Strategy review", agents.strategy_reviewer, render_review_input(context), state, REVIEW_MAX_TURNS,
            use_mcp=False,
        )
        return to_review_proposal(result, state.usage(), trace_id)

    async def _run(
        self, workflow: str, agent: Agent, input_text: str, state: AgentRunState, max_turns: int, use_mcp: bool = True
    ):
        trace_id = gen_trace_id()
        tracing_on = not state.run_config.tracing_disabled
        try:
            async with AsyncExitStack() as stack:
                for server in self._mcp_servers.all() if use_mcp else ():
                    await stack.enter_async_context(server)
                with trace(workflow, trace_id=trace_id, disabled=not tracing_on):
                    result = await Runner.run(
                        agent,
                        input_text,
                        context=state,
                        run_config=state.run_config,
                        hooks=state.hooks,
                        max_turns=max_turns,
                    )
        except Exception as exc:
            raise AgentError(
                f"{workflow} failed: {type(exc).__name__}: {exc}",
                trace_id=trace_id if tracing_on else None,
                usage=state.usage(),
            ) from exc
        return result.final_output, (trace_id if tracing_on else None)
