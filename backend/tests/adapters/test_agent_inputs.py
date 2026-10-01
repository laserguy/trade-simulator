from datetime import datetime, timezone
from decimal import Decimal

from trade_simulator.adapters.openai_agents.inputs import (
    render_decision_input,
    render_refresh_input,
    render_research_note,
    with_research_note,
)
from trade_simulator.application.ports import (
    DecisionContext,
    ExecutedTrade,
    MarketOverview,
    Performance,
    RefreshContext,
)
from trade_simulator.core.decision_log import Watchlist, WatchlistEntry
from trade_simulator.core.exchange_profile import US_PROFILE
from trade_simulator.core.order import Side
from trade_simulator.core.portfolio import Portfolio, Position
from trade_simulator.core.run_budget import DECISION_RUN_LIMITS, REFRESH_RUN_LIMITS
from trade_simulator.core.trading_rules import TradingRules

NOW = datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc)
WATCHLIST = Watchlist((WatchlistEntry("AAPL", "Earnings"), WatchlistEntry("MSFT", "Cloud")), NOW)


def test_decision_input_shows_cash_holdings_weights_and_watchlist():
    context = DecisionContext(
        profile=US_PROFILE,
        rules=TradingRules.for_exchange(US_PROFILE),
        limits=DECISION_RUN_LIMITS,
        portfolio=Portfolio(Decimal("8000"), {"AAPL": Position("AAPL", 10, Decimal("190"))}),
        prices={"AAPL": Decimal("200")},
        watchlist=WATCHLIST,
        now=NOW,
    )

    text = render_decision_input(context)

    assert "Cash: 8,000.00 USD" in text
    assert "Total portfolio value: 10,000.00 USD" in text
    assert "AAPL: 10 shares" in text and "20.0% of portfolio" in text
    assert "MSFT (price unavailable): Cloud" in text
    assert "3 Research Agent calls, 5 web searches" in text


def decision_context(market_overview=None):
    return DecisionContext(
        profile=US_PROFILE,
        rules=TradingRules.for_exchange(US_PROFILE),
        limits=DECISION_RUN_LIMITS,
        portfolio=Portfolio(Decimal("10000"), {}),
        prices={},
        watchlist=WATCHLIST,
        now=NOW,
        market_overview=market_overview,
    )


def test_decision_input_includes_the_latest_market_overview_with_its_date():
    overview = MarketOverview("Tech led by AI demand; tariff worries weigh on chips.", ("https://m",), NOW)

    text = render_decision_input(decision_context(overview))

    assert "Latest market overview (from the watchlist refresh on 2026-09-28):" in text
    assert "tariff worries weigh on chips" in text


def test_decision_input_says_when_there_is_no_market_overview():
    assert "Latest market overview: none yet" in render_decision_input(decision_context())


def holding_context(**extra):
    return DecisionContext(
        profile=US_PROFILE,
        rules=TradingRules.for_exchange(US_PROFILE),
        limits=DECISION_RUN_LIMITS,
        portfolio=Portfolio(Decimal("8000"), {"AAPL": Position("AAPL", 10, Decimal("190"))}),
        prices={"AAPL": Decimal("200")},
        watchlist=WATCHLIST,
        now=NOW,
        **extra,
    )


def test_decision_input_shows_each_holding_gain_and_why_it_was_bought():
    bought = datetime(2026, 9, 25, 14, 0, tzinfo=timezone.utc)
    buy = ExecutedTrade(bought, Side.BUY, 10, Decimal("190"), "run-0", "AAPL", "Strong iPhone demand.")

    text = render_decision_input(holding_context(holding_buys={"AAPL": (buy,)}))

    assert "20.0% of portfolio), +5.3% on cost" in text
    assert '  Bought 10 on 2026-09-25 at 190. Your reason then: "Strong iPhone demand."' in text


def test_a_holding_that_is_almost_flat_is_not_shown_as_a_loss():
    context = holding_context()
    flat = DecisionContext(**{**context.__dict__, "prices": {"AAPL": Decimal("189.99")}})

    assert "+0.0% on cost" in render_decision_input(flat)


def test_decision_input_shows_performance_against_the_benchmark():
    performance = Performance(datetime(2026, 9, 25, tzinfo=timezone.utc), Decimal("-0.7"), "SPY", Decimal("1.234"))

    text = render_decision_input(holding_context(performance=performance))

    assert "Performance since 2026-09-25: portfolio -0.70%, SPY +1.23%" in text


def test_decision_input_without_history_or_performance_stays_as_before():
    text = render_decision_input(holding_context())

    assert "Performance" not in text
    assert "Bought" not in text


def test_research_note_lists_each_holding_with_the_reason_it_was_bought():
    first = ExecutedTrade(datetime(2026, 9, 25, 14, 0, tzinfo=timezone.utc), Side.BUY, 6, Decimal("190"), "r0", "AAPL", "Strong iPhone demand.")
    second = ExecutedTrade(datetime(2026, 9, 28, 14, 0, tzinfo=timezone.utc), Side.BUY, 4, Decimal("190"), "r1", "AAPL", "Added on a dip.")

    note = render_research_note(holding_context(holding_buys={"AAPL": (first, second)}))

    assert note.splitlines() == [
        "Current holdings and the reason each was bought:",
        '- AAPL (bought 2026-09-25): "Strong iPhone demand."',
        '- AAPL (bought 2026-09-28): "Added on a dip."',
        "Report the facts that bear on these reasons. The Trading Agent judges whether they still hold.",
    ]


def test_research_note_is_empty_when_no_holding_has_a_recorded_reason():
    assert render_research_note(holding_context()) == ""
    assert render_research_note(decision_context()) == ""


def test_research_request_gets_the_note_appended():
    assert with_research_note("Check AAPL", "Current holdings…") == "Check AAPL\n\nCurrent holdings…"
    assert with_research_note("Check AAPL", "") == "Check AAPL"


def test_refresh_input_lists_the_allowed_stocks_and_current_watchlist():
    context = RefreshContext(
        profile=US_PROFILE,
        limits=REFRESH_RUN_LIMITS,
        stock_pool=frozenset({"MSFT", "AAPL"}),
        current_watchlist=WATCHLIST,
        now=NOW,
    )

    text = render_refresh_input(context)

    assert "AAPL, MSFT" in text
    assert "- AAPL: Earnings" in text
    assert "20 searches" in text
