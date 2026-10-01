import json
from datetime import date
from decimal import Decimal

from trade_simulator.adapters.finnhub_market_data import NewsItem, Quote
from trade_simulator.adapters.openai_agents.state import AgentRunState
from trade_simulator.adapters.openai_agents.toolbox import ResearchToolbox
from trade_simulator.application.ports import SearchResult
from trade_simulator.core.errors import MarketDataError, SearchError
from trade_simulator.core.run_budget import RunBudget, RunLimits

TODAY = date(2026, 9, 28)


class FakeFinnhub:
    def __init__(self, error=None):
        self.error = error
        self.quote_requests = []

    def get_quotes(self, symbols):
        self.quote_requests.append(list(symbols))
        if self.error:
            raise self.error
        return {s: Quote(s, Decimal("100.5"), Decimal("12.3"), Decimal("89.5")) for s in symbols}

    def company_news(self, symbol, start, end):
        return [NewsItem("Big launch", "Reuters", "https://r/1", "Summary text", "2026-09-27T12:00:00+00:00")]

    def market_news(self):
        return [NewsItem("Fed holds rates", "Reuters", "https://r/2", "Summary", "2026-09-27T13:00:00+00:00")]

    def basic_metrics(self, symbol):
        return {"peTTM": 30.1, "marketCapitalization": 3000000}


class FakeSearch:
    def __init__(self, error=None):
        self.error = error
        self.queries = []

    def search(self, query):
        self.queries.append(query)
        if self.error:
            raise self.error
        return [SearchResult("Title", "https://t/1", "Content")]


def make(limits=RunLimits(max_searches=2, max_research_calls=1), finnhub=None, search=None):
    toolbox = ResearchToolbox(finnhub or FakeFinnhub(), search or FakeSearch(), today=lambda: TODAY)
    return toolbox, AgentRunState(budget=RunBudget(limits))


def test_quotes_report_price_and_daily_change():
    toolbox, state = make()

    data = json.loads(toolbox.quotes(state, ["aapl"]))

    assert data == {"AAPL": {"price": "100.5", "change_percent": "12.3", "previous_close": "89.5"}}


def test_quotes_are_remembered_for_the_decision_log():
    toolbox, state = make()

    toolbox.quotes(state, ["aapl"])

    assert state.quotes == {"AAPL": Quote("AAPL", Decimal("100.5"), Decimal("12.3"), Decimal("89.5"))}


def test_quotes_are_capped_per_call_to_protect_rate_limit():
    finnhub = FakeFinnhub()
    toolbox, state = make(finnhub=finnhub)

    toolbox.quotes(state, [f"S{i}" for i in range(40)])

    assert len(finnhub.quote_requests[0]) == ResearchToolbox.MAX_SYMBOLS_PER_CALL


def test_web_search_uses_the_search_budget():
    search = FakeSearch()
    toolbox, state = make(search=search)

    data = json.loads(toolbox.web_search(state, "NVDA earnings"))

    assert data[0]["url"] == "https://t/1"
    assert state.budget.searches_used == 1


def test_web_search_beyond_budget_tells_the_agent_instead_of_crashing():
    search = FakeSearch()
    toolbox, state = make(search=search)
    toolbox.web_search(state, "q1")
    toolbox.web_search(state, "q2")

    message = toolbox.web_search(state, "q3")

    assert "limit" in message.lower()
    assert search.queries == ["q1", "q2"]


def test_company_news_uses_last_n_days_and_no_search_budget():
    toolbox, state = make()

    data = json.loads(toolbox.company_news(state, "AAPL", days=7))

    assert data[0]["headline"] == "Big launch"
    assert state.budget.searches_used == 0


def test_market_news_returns_headlines_and_uses_no_search_budget():
    toolbox, state = make()

    data = json.loads(toolbox.market_news(state))

    assert data[0]["headline"] == "Fed holds rates"
    assert state.budget.searches_used == 0


def test_tool_errors_are_reported_to_the_agent_as_text():
    toolbox, state = make(finnhub=FakeFinnhub(error=MarketDataError("Finnhub down")), search=FakeSearch(SearchError("Tavily down")))

    assert "Finnhub down" in toolbox.quotes(state, ["AAPL"])
    assert "Tavily down" in toolbox.web_search(state, "q")


def test_key_metrics_returns_metrics_json():
    toolbox, state = make()

    assert json.loads(toolbox.key_metrics(state, "AAPL"))["peTTM"] == 30.1
