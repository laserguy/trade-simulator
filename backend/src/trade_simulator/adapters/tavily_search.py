"""Tavily web search for market research (D10): one implementation of the WebSearch port (D34).

Basic depth = 1 credit per search. On the free plan, searches stop when the monthly credits run out.
"""

from tavily import TavilyClient

from trade_simulator.application.ports import SearchResult
from trade_simulator.core.errors import SearchError


class TavilySearch:
    MAX_RESULTS = 5
    MAX_CONTENT_CHARS = 600  # keeps the agent's input, and so token cost, small
    free_searches_per_month = 1000  # Tavily free plan credits; basic search = 1 credit

    def __init__(self, api_key: str | None = None, *, client=None) -> None:
        self._client = client or TavilyClient(api_key=api_key)

    def search(self, query: str) -> list[SearchResult]:
        try:
            response = self._client.search(
                query=query,
                search_depth="basic",
                topic="news",
                time_range="month",
                max_results=self.MAX_RESULTS,
            )
        except Exception as exc:  # the Tavily client raises several unrelated exception types
            raise SearchError(f"Tavily search failed: {type(exc).__name__}: {exc}") from exc
        return [
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                content=(item.get("content") or "")[: self.MAX_CONTENT_CHARS],
            )
            for item in response.get("results", [])
        ]
