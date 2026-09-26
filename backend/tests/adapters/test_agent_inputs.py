from datetime import datetime, timezone
from decimal import Decimal

from trade_simulator.adapters.openai_agents.inputs import render_decision_input, render_refresh_input
from trade_simulator.application.ports import DecisionContext, MarketOverview, RefreshContext
from trade_simulator.core.decision_log import Watchlist, WatchlistEntry
from trade_simulator.core.exchange_profile import US_PROFILE
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
