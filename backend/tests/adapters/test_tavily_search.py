import pytest

from trade_simulator.adapters.tavily_search import TavilySearch
from trade_simulator.application.ports import SearchResult
from trade_simulator.core.errors import SearchError


def test_provider_declares_its_free_monthly_allowance():
    assert TavilySearch(client=object()).free_searches_per_month == 1000


class FakeTavilyClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def test_search_maps_results_and_uses_basic_one_credit_depth():
    client = FakeTavilyClient({"results": [{"title": "T", "url": "https://u", "content": "C" * 2000, "score": 0.9}]})

    results = TavilySearch(client=client).search("AAPL news")

    assert results == [SearchResult("T", "https://u", "C" * TavilySearch.MAX_CONTENT_CHARS)]
    assert client.calls[0]["search_depth"] == "basic"
    assert client.calls[0]["query"] == "AAPL news"


def test_search_errors_become_search_error():
    client = FakeTavilyClient(error=RuntimeError("401 unauthorized"))

    with pytest.raises(SearchError):
        TavilySearch(client=client).search("q")
