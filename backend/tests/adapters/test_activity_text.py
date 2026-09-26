from trade_simulator.adapters.openai_agents.activity_text import describe_tool_call


def test_tool_calls_are_described_in_plain_words():
    assert describe_tool_call("get_quotes", '{"symbols": ["NVDA", "AAPL"]}') == "Checking prices: NVDA, AAPL"
    assert describe_tool_call("get_company_news", '{"symbol": "AAPL", "days": 7}') == "Reading news: AAPL (last 7 days)"
    assert describe_tool_call("get_key_metrics", '{"symbol": "MSFT"}') == "Checking fundamentals: MSFT"
    assert describe_tool_call("web_search", '{"query": "NVIDIA demand"}') == 'Searching the web: "NVIDIA demand"'
    assert describe_tool_call("get_market_news", "{}") == "Reading market news"
    assert (
        describe_tool_call("ask_research_agent", '{"request": "Check NVDA news"}')
        == 'Asked the Research Agent: "Check NVDA news"'
    )


def test_long_symbol_lists_are_shortened():
    symbols = ", ".join(f'"S{i}"' for i in range(12))

    assert describe_tool_call("get_quotes", f'{{"symbols": [{symbols}]}}') == "Checking prices: S0, S1, S2, S3, S4, S5 and 6 more"


def test_unknown_or_mcp_tools_and_bad_arguments_still_get_a_line():
    assert describe_tool_call("some_mcp_tool", '{"x": 1}') == "Using tool: some_mcp_tool"
    assert describe_tool_call("get_quotes", "not json") == "Using tool: get_quotes"
