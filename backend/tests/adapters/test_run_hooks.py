import asyncio
from types import SimpleNamespace

from trade_simulator.adapters.openai_agents.run_hooks import AgentRunHooks
from trade_simulator.adapters.openai_agents.state import AgentRunState
from trade_simulator.core.run_budget import DECISION_RUN_LIMITS, RunBudget


def tool_ends(hooks, tool_name, result):
    state = AgentRunState(budget=RunBudget(DECISION_RUN_LIMITS))
    asyncio.run(hooks.on_tool_end(SimpleNamespace(context=state), None, SimpleNamespace(name=tool_name), result))
    return state


def test_links_in_any_tool_output_are_remembered_for_the_run():
    state = tool_ends(AgentRunHooks(), "get_company_news", '[{"url": "https://finnhub.io/api/news?id=abc"}]')

    assert state.tool_urls == {"https://finnhub.io/api/news?id=abc"}


def test_research_agent_reports_do_not_count_as_tool_sources():
    # its sources were written by the agent, which is exactly what is being checked
    state = tool_ends(AgentRunHooks(), "ask_research_agent", '{"findings": [{"sources": ["https://made.up/z"]}]}')

    assert state.tool_urls == set()


def test_timeline_hooks_still_receive_every_step():
    calls = []

    class FakeTimeline:
        async def on_agent_start(self, context, agent):
            calls.append("agent_start")

        async def on_tool_start(self, context, agent, tool):
            calls.append("tool_start")

        async def on_tool_end(self, context, agent, tool, result):
            calls.append("tool_end")

        async def on_agent_end(self, context, agent, output):
            calls.append("agent_end")

    hooks = AgentRunHooks(FakeTimeline())
    ctx, tool = SimpleNamespace(context=AgentRunState(budget=RunBudget(DECISION_RUN_LIMITS))), SimpleNamespace(name="t")

    async def run_steps():
        await hooks.on_agent_start(ctx, None)
        await hooks.on_tool_start(ctx, None, tool)
        await hooks.on_tool_end(ctx, None, tool, "no links")
        await hooks.on_agent_end(ctx, None, None)

    asyncio.run(run_steps())

    assert calls == ["agent_start", "tool_start", "tool_end", "agent_end"]
