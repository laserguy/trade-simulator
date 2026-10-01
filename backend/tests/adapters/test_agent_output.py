from decimal import Decimal
from typing import get_args

from trade_simulator.adapters.openai_agents.schemas import (
    ProposedOrder,
    ResearchFinding,
    SectionChange,
    SectionName,
    StrategyReviewResult,
    StrategyText,
    TradingDecision,
    WatchlistPick,
    WatchlistResult,
    to_findings,
    to_market_overview,
    to_orders,
    to_review_proposal,
    to_watchlist_entries,
)
from trade_simulator.application.ports import AgentUsage, Quote
from trade_simulator.core.order import Side
from trade_simulator.core.strategy import ORDER_BASES, StrategySection
from trade_simulator.core.strategy_review import Followed, ReviewDecision, TargetsVerdict


def review_result(**changes):
    fields = dict(
        targets_verdict="partly_met",
        targets_note="Behind SPY.",
        followed="yes",
        followed_note="Every order named a section.",
        decision="change",
        reason="Sizing was too large.",
        new_strategy=StrategyText(
            what_i_look_for="Earnings momentum.",
            position_size="Start at 4%.",
            when_i_sell="Sell when the reason breaks.",
            cash_and_pace="Keep 10-25% cash.",
            targets="Ahead of SPY.",
        ),
        section_changes=[SectionChange(section="position_size", why="Two buys fell together.")],
    )
    return StrategyReviewResult(**{**fields, **changes})


def test_a_review_answer_becomes_a_review_proposal():
    usage = AgentUsage(100, 20, 0, "gpt-6-luna")

    proposal = to_review_proposal(review_result(), usage, "trace_r")

    assert (proposal.decision, proposal.targets_verdict, proposal.followed) == (
        ReviewDecision.CHANGE, TargetsVerdict.PARTLY_MET, Followed.YES
    )
    assert proposal.new_strategy.position_size == "Start at 4%."
    assert proposal.section_changes == {StrategySection.POSITION_SIZE: "Two buys fell together."}
    assert (proposal.usage, proposal.trace_id) == (usage, "trace_r")


def test_a_keep_answer_has_no_strategy_and_the_first_has_no_verdicts():
    keep = to_review_proposal(review_result(decision="keep", new_strategy=None, section_changes=[]), None, None)
    first = to_review_proposal(review_result(targets_verdict=None, followed=None), None, None)

    assert (keep.decision, keep.new_strategy) == (ReviewDecision.KEEP, None)
    assert (first.targets_verdict, first.followed) == (None, None)


def test_links_are_kept_out_of_the_review_text():
    proposal = to_review_proposal(review_result(reason="See [this](https://x.com/a) for why."), None, None)

    assert "https://" not in proposal.reason


def test_the_answer_formats_allow_exactly_the_core_sections():
    sections = {s.value for s in StrategySection}

    assert set(get_args(SectionName)) == sections
    assert set(get_args(get_args(ProposedOrder.model_fields["follows"].annotation)[0])) == ORDER_BASES
    assert set(StrategyText.model_fields) == sections


def test_an_order_keeps_the_section_it_follows():
    decision = TradingDecision(
        orders=[ProposedOrder(symbol="AAPL", side="sell", quantity=1, reason="Broke", follows="deviation")], summary="s"
    )

    [order], _ = to_orders(decision)

    assert order.follows == "deviation"


def test_valid_proposed_orders_become_core_orders():
    decision = TradingDecision(
        orders=[ProposedOrder(symbol="aapl", side="buy", quantity=3, reason="Cheap", follows=None)], summary="s"
    )

    orders, warnings = to_orders(decision)

    assert [(o.symbol, o.side, o.quantity, o.reason) for o in orders] == [("AAPL", Side.BUY, 3, "Cheap")]
    assert warnings == []


def test_invalid_proposed_orders_are_ignored_with_a_warning():
    decision = TradingDecision(
        orders=[ProposedOrder(symbol="AAPL", side="buy", quantity=0, reason="?", follows=None)], summary="s"
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


def test_findings_carry_the_price_and_daily_change_the_quote_tool_returned():
    quotes = {"NVDA": Quote("NVDA", Decimal("230.25"), Decimal("2.3"), Decimal("225.07"))}
    report = [
        ResearchFinding(symbol="nvda", summary="S", sources=[], warnings=[]),
        ResearchFinding(symbol="MARKET", summary="Oil up", sources=[], warnings=[]),
    ]

    nvda, market = to_findings(report, set(), quotes)

    assert (nvda.price, nvda.change_percent) == (Decimal("230.25"), Decimal("2.3"))
    assert (market.price, market.change_percent) == (None, None)


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
