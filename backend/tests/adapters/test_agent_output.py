from trade_simulator.adapters.openai_agents.schemas import (
    ProposedOrder,
    ResearchFinding,
    TradingDecision,
    WatchlistPick,
    WatchlistResult,
    to_findings,
    to_market_overview,
    to_orders,
    to_watchlist_entries,
)
from trade_simulator.core.order import Side


def test_valid_proposed_orders_become_core_orders():
    decision = TradingDecision(
        orders=[ProposedOrder(symbol="aapl", side="buy", quantity=3, reason="Cheap")], summary="s"
    )

    orders, warnings = to_orders(decision)

    assert [(o.symbol, o.side, o.quantity, o.reason) for o in orders] == [("AAPL", Side.BUY, 3, "Cheap")]
    assert warnings == []


def test_invalid_proposed_orders_are_ignored_with_a_warning():
    decision = TradingDecision(
        orders=[ProposedOrder(symbol="AAPL", side="buy", quantity=0, reason="?")], summary="s"
    )

    orders, warnings = to_orders(decision)

    assert orders == []
    assert warnings[0].symbol == "AAPL"
    assert "ignored" in warnings[0].warnings[0].lower()


def test_research_findings_convert_to_core_findings():
    [finding] = to_findings(
        [ResearchFinding(symbol="nvda", summary="S", sources=["https://r.com/u"], warnings=["w"])], {"https://r.com/u"}
    )

    assert (finding.symbol, finding.sources, finding.warnings) == ("NVDA", ("https://r.com/u",), ("w",))


def test_watchlist_picks_convert_to_entries():
    result = WatchlistResult(
        market_overview="Calm",
        market_sources=[],
        picks=[WatchlistPick(symbol="msft", reason="Cloud", sources=["https://r.com/u"])],
    )

    [entry] = to_watchlist_entries(result, {"https://r.com/u"})

    assert (entry.symbol, entry.reason, entry.sources) == ("MSFT", "Cloud", ("https://r.com/u",))


def test_market_overview_keeps_its_own_sources_and_loses_inline_links():
    result = WatchlistResult(
        market_overview="Tech led. Sources: [CNBC](https://cnbc.com/a)",
        market_sources=["https://reuters.com/b"],
        picks=[],
    )

    overview = to_market_overview(result, {"https://reuters.com/b", "https://cnbc.com/a"})

    assert overview.summary == "Tech led."
    assert overview.sources == ("https://reuters.com/b", "https://cnbc.com/a")


def test_links_inside_research_findings_move_to_sources():
    [finding] = to_findings(
        [ResearchFinding(symbol="NVDA", summary="Beat, per [Reuters](https://r.com/x).", sources=[], warnings=[])],
        {"https://r.com/x"},
    )

    assert finding.summary == "Beat, per Reuters."
    assert finding.sources == ("https://r.com/x",)


def test_sources_no_tool_returned_are_dropped_everywhere():
    known = {"https://r.com/real"}
    bad = ["https://r.com/rea", "https://made.up/z"]

    [finding] = to_findings([ResearchFinding(symbol="NVDA", summary="S", sources=["https://r.com/real", *bad], warnings=[])], known)
    result = WatchlistResult(
        market_overview="Calm", market_sources=bad, picks=[WatchlistPick(symbol="MSFT", reason="Cloud", sources=bad)]
    )

    assert finding.sources == ("https://r.com/real",)
    assert to_market_overview(result, known).sources == ()
    assert to_watchlist_entries(result, known)[0].sources == ()
