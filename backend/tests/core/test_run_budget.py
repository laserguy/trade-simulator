import pytest

from trade_simulator.core.errors import BudgetExceededError
from trade_simulator.core.run_budget import DECISION_RUN_LIMITS, REFRESH_RUN_LIMITS, RunBudget


def test_decision_and_refresh_limits_match_decisions_d13_d14():
    assert DECISION_RUN_LIMITS.max_research_calls == 3
    assert DECISION_RUN_LIMITS.max_searches == 5
    assert REFRESH_RUN_LIMITS.max_searches == 20


def test_budget_counts_usage():
    budget = RunBudget(DECISION_RUN_LIMITS)

    budget.use_search()
    budget.use_search()
    budget.use_research_call()

    assert budget.searches_used == 2
    assert budget.research_calls_used == 1
    assert budget.searches_remaining == 3


def test_search_beyond_limit_raises():
    budget = RunBudget(DECISION_RUN_LIMITS)
    for _ in range(5):
        budget.use_search()

    with pytest.raises(BudgetExceededError):
        budget.use_search()
    assert budget.searches_used == 5


def test_research_call_beyond_limit_raises():
    budget = RunBudget(DECISION_RUN_LIMITS)
    for _ in range(3):
        budget.use_research_call()

    with pytest.raises(BudgetExceededError):
        budget.use_research_call()


def test_refresh_has_no_research_call_cap():
    budget = RunBudget(REFRESH_RUN_LIMITS)
    for _ in range(50):
        budget.use_research_call()

    assert budget.research_calls_remaining is None
