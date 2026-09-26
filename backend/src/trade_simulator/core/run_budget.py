"""Per-run research limits, enforced in code so the agent can't exceed them (D13, D14)."""

from dataclasses import dataclass

from trade_simulator.core.errors import BudgetExceededError


@dataclass(frozen=True)
class RunLimits:
    max_searches: int
    max_research_calls: int | None  # None = no cap


DECISION_RUN_LIMITS = RunLimits(max_searches=5, max_research_calls=3)
REFRESH_RUN_LIMITS = RunLimits(max_searches=20, max_research_calls=None)


class RunBudget:
    """Tracks what one run has used. Usage counts also feed the run-cost line of the decision log (D22)."""

    def __init__(self, limits: RunLimits) -> None:
        self._limits = limits
        self.searches_used = 0
        self.research_calls_used = 0

    @property
    def searches_remaining(self) -> int:
        return self._limits.max_searches - self.searches_used

    @property
    def research_calls_remaining(self) -> int | None:
        if self._limits.max_research_calls is None:
            return None
        return self._limits.max_research_calls - self.research_calls_used

    def use_search(self) -> None:
        if self.searches_remaining <= 0:
            raise BudgetExceededError(f"Search limit of {self._limits.max_searches} reached for this run")
        self.searches_used += 1

    def use_research_call(self) -> None:
        remaining = self.research_calls_remaining
        if remaining is not None and remaining <= 0:
            raise BudgetExceededError(
                f"Research call limit of {self._limits.max_research_calls} reached for this run"
            )
        self.research_calls_used += 1
