from trade_simulator.application.ports import AgentUsage
from trade_simulator.core.decision_log import RunCost

NO_COST = RunCost(0, 0, 0)


def cost_of(usage: AgentUsage | None) -> RunCost:
    if usage is None:
        return NO_COST
    return RunCost(usage.input_tokens, usage.output_tokens, usage.searches, usage.model)
