"""SDK run hooks for every agent run: remember the links tools return (D22) and feed the live timeline (D28).

Links are collected from every tool, including MCP tools (D27), so a source can be checked against what a
tool really returned. The Research Agent's report is skipped: its links were written by the agent.
"""

from agents import RunHooks

from trade_simulator.adapters.text_links import find_urls

AGENT_WRITTEN_TOOLS = {"ask_research_agent"}


class AgentRunHooks(RunHooks):
    def __init__(self, timeline: RunHooks | None = None) -> None:
        self._timeline = timeline

    async def on_agent_start(self, context, agent) -> None:
        if self._timeline:
            await self._timeline.on_agent_start(context, agent)

    async def on_tool_start(self, context, agent, tool) -> None:
        if self._timeline:
            await self._timeline.on_tool_start(context, agent, tool)

    async def on_tool_end(self, context, agent, tool, result) -> None:
        if tool.name not in AGENT_WRITTEN_TOOLS:
            context.context.tool_urls |= find_urls(str(result))
        if self._timeline:
            await self._timeline.on_tool_end(context, agent, tool, result)

    async def on_agent_end(self, context, agent, output) -> None:
        if self._timeline:
            await self._timeline.on_agent_end(context, agent, output)
