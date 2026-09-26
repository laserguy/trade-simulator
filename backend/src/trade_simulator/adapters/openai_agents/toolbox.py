"""What the Research Agent's tools actually do. Plain Python, so it is testable without the SDK (D18).

Every method returns text for the model. Tool failures and exhausted budgets are reported as text,
so the agent can carry on with what it has instead of the whole run crashing.
"""

import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import date, timedelta

from trade_simulator.adapters.openai_agents.state import AgentRunState
from trade_simulator.core.errors import BudgetExceededError, TradeSimulatorError


class ResearchToolbox:
    MAX_SYMBOLS_PER_CALL = 25  # protects Finnhub's 60 calls/min free limit

    def __init__(self, finnhub, search, *, today: Callable[[], date] = date.today) -> None:
        self._finnhub = finnhub
        self._search = search
        self._today = today

    def quotes(self, state: AgentRunState, symbols: list[str]) -> str:
        wanted = [s.strip().upper() for s in symbols][: self.MAX_SYMBOLS_PER_CALL]
        return _as_tool_output(
            lambda: {
                symbol: {
                    "price": str(q.price),
                    "change_percent": str(q.change_percent),
                    "previous_close": str(q.previous_close),
                }
                for symbol, q in self._finnhub.get_quotes(wanted).items()
            }
        )

    def company_news(self, state: AgentRunState, symbol: str, days: int = 7) -> str:
        days = min(max(days, 1), 30)
        end = self._today()
        return _as_tool_output(
            lambda: [asdict(item) for item in self._finnhub.company_news(symbol.upper(), end - timedelta(days=days), end)]
        )

    def market_news(self, state: AgentRunState) -> str:
        return _as_tool_output(lambda: [asdict(item) for item in self._finnhub.market_news()])

    def key_metrics(self, state: AgentRunState, symbol: str) -> str:
        return _as_tool_output(lambda: self._finnhub.basic_metrics(symbol.upper()))

    def web_search(self, state: AgentRunState, query: str) -> str:
        try:
            state.budget.use_search()
        except BudgetExceededError as exc:
            return f"{exc}. No more web searches are allowed in this run; work with what you have."
        return _as_tool_output(lambda: [asdict(result) for result in self._search.search(query)])


def _as_tool_output(fetch: Callable[[], object]) -> str:
    try:
        return json.dumps(fetch())
    except TradeSimulatorError as exc:
        return f"Tool error: {exc}"
