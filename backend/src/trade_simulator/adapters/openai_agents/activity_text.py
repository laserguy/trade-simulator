"""Plain-language lines for the live timeline (D28), e.g. `Checking prices: NVDA, AAPL`."""

import json

MAX_SYMBOLS_SHOWN = 6


def describe_tool_call(tool_name: str, arguments_json: str | None) -> str:
    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return f"Using tool: {tool_name}"
    describe = _DESCRIBERS.get(tool_name)
    try:
        return describe(args) if describe else f"Using tool: {tool_name}"
    except (KeyError, TypeError):
        return f"Using tool: {tool_name}"


def _symbols(symbols: list[str]) -> str:
    shown = ", ".join(symbols[:MAX_SYMBOLS_SHOWN])
    extra = len(symbols) - MAX_SYMBOLS_SHOWN
    return f"{shown} and {extra} more" if extra > 0 else shown


_DESCRIBERS = {
    "get_quotes": lambda a: f"Checking prices: {_symbols(a['symbols'])}",
    "get_company_news": lambda a: f"Reading news: {a['symbol']} (last {a['days']} days)",
    "get_market_news": lambda a: "Reading market news",
    "get_key_metrics": lambda a: f"Checking fundamentals: {a['symbol']}",
    "web_search": lambda a: f'Searching the web: "{a["query"]}"',
    "ask_research_agent": lambda a: f'Asked the Research Agent: "{a["request"]}"',
}
