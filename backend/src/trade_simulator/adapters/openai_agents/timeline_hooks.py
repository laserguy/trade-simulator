"""SDK run hooks that turn agent steps into live timeline lines (D28)."""

import json

from agents import RunHooks

from trade_simulator.adapters.openai_agents.activity_text import describe_tool_call
from trade_simulator.adapters.openai_agents.schemas import TradingDecision, WatchlistResult
from trade_simulator.application.ports import ActivityReporter


class TimelineHooks(RunHooks):
    def __init__(self, activity: ActivityReporter) -> None:
        self._activity = activity

    async def on_agent_start(self, context, agent) -> None:
        self._activity.add(agent.name, "Started")

    async def on_tool_start(self, context, agent, tool) -> None:
        self._activity.add(agent.name, describe_tool_call(tool.name, getattr(context, "tool_arguments", None)))

    async def on_tool_end(self, context, agent, tool, result) -> None:
        if tool.name == "ask_research_agent":
            self._activity.add("Research Agent", _research_summary(result))

    async def on_agent_end(self, context, agent, output) -> None:
        if isinstance(output, TradingDecision):
            self._activity.add(agent.name, _proposal_line(output))
        elif isinstance(output, WatchlistResult):
            self._activity.add(agent.name, f"Picked {len(output.picks)} stocks")


def _research_summary(result: object) -> str:
    try:
        findings = json.loads(str(result))["findings"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return str(result)[:160]  # e.g. "research limit reached" message
    warnings = sum(len(f.get("warnings", [])) for f in findings)
    return f"Reported {_plural(len(findings), 'finding')} ({_plural(warnings, 'warning')})"


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _proposal_line(decision: TradingDecision) -> str:
    if not decision.orders:
        return "Proposed no trades (holding)"
    orders = ", ".join(f"{o.side.upper()} {o.quantity} {o.symbol.upper()}" for o in decision.orders)
    return f"Proposed: {orders}"
