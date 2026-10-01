from dataclasses import dataclass, field
from typing import Any

from trade_simulator.application.ports import AgentUsage, Quote
from trade_simulator.core.decision_log import Finding
from trade_simulator.core.run_budget import RunBudget


@dataclass
class AgentRunState:
    """Per-run state shared by every agent and tool in one run (passed as the SDK's run context)."""

    budget: RunBudget
    run_config: Any = None
    hooks: Any = None  # SDK RunHooks (run_hooks.py), shared with nested Research Agent runs
    model_id: str | None = None
    findings: list[Finding] = field(default_factory=list)
    tool_urls: set[str] = field(default_factory=set)  # every link a tool returned; only these may be sources (D22)
    quotes: dict[str, Quote] = field(default_factory=dict)  # latest quote per stock, saved with its finding (D22)
    research_note: str = ""  # added to every research request: the holdings and why each was bought (D42)
    input_tokens: int = 0
    output_tokens: int = 0

    def add_usage(self, usage) -> None:
        """Add an SDK Usage. Nested agent runs report usage separately, so every run's usage is added here."""
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens

    def usage(self) -> AgentUsage:
        return AgentUsage(self.input_tokens, self.output_tokens, self.budget.searches_used, self.model_id)
