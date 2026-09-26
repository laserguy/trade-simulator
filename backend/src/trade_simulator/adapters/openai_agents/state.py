from dataclasses import dataclass, field
from typing import Any

from trade_simulator.application.ports import AgentUsage
from trade_simulator.core.decision_log import Finding
from trade_simulator.core.run_budget import RunBudget


@dataclass
class AgentRunState:
    """Per-run state shared by every agent and tool in one run (passed as the SDK's run context)."""

    budget: RunBudget
    run_config: Any = None
    hooks: Any = None  # SDK RunHooks for the live timeline (D28), shared with nested Research Agent runs
    model_id: str | None = None
    findings: list[Finding] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0

    def add_usage(self, usage) -> None:
        """Add an SDK Usage. Nested agent runs report usage separately, so every run's usage is added here."""
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens

    def usage(self) -> AgentUsage:
        return AgentUsage(self.input_tokens, self.output_tokens, self.budget.searches_used, self.model_id)
