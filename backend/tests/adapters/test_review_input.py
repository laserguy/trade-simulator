from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal

from trade_simulator.adapters.openai_agents.review_input import render_review_input
from trade_simulator.application.ports import MarketOverview, ReviewContext, ReviewedOrder
from trade_simulator.core.decision_log import RunCost, RunStatus, Watchlist, WatchlistEntry
from trade_simulator.core.exchange_profile import US_PROFILE
from trade_simulator.core.order import Order, Side
from trade_simulator.core.portfolio import Portfolio, Position
from trade_simulator.core.strategy import DEVIATION, Strategy, StrategySection, StrategyVersion
from trade_simulator.core.strategy_review import (
    ClosedTrade,
    Followed,
    HoldingResult,
    OrderOutcome,
    ReviewDecision,
    ReviewTrigger,
    Scorecard,
    StockMove,
    StrategyReview,
    TargetsVerdict,
    TradingDay,
)
from trade_simulator.core.trading_rules import OrderResult, OrderStatus, RejectionReason, TradingRules


def at(month, day):
    return datetime(2026, month, day, 20, 15, tzinfo=timezone.utc)


NOW = at(9, 26)
WATCHLIST = Watchlist((WatchlistEntry("AAPL", "Earnings"), WatchlistEntry("MSFT", "Cloud")), at(9, 1))


def strategy(tag):
    return Strategy(f"{tag} look", f"{tag} size", f"{tag} sell", f"{tag} cash", f"{tag} targets")


V1 = StrategyVersion(1, strategy("V1"), at(8, 4), at(8, 18), "r1")
V2 = StrategyVersion(2, strategy("V2"), at(8, 18), at(9, 12), "r2")
V3 = StrategyVersion(3, strategy("V3"), at(9, 12), None, "r4")


def card(portfolio, benchmark):
    return Scorecard(
        period_start=at(9, 12),
        period_end=NOW,
        portfolio_percent=Decimal(portfolio),
        benchmark_percent=Decimal(benchmark),
        trading_runs=9,
        trades=6,
        fees=Decimal("6"),
        closed_trades=(ClosedTrade("NVDA", Decimal("84.1")), ClosedTrade("AMD", Decimal("-41"))),
        holdings=(HoldingResult("AAPL", Decimal("10")),),
        average_cash_percent=Decimal("18.25"),
        followed_orders=5,
        deviations=1,
    )


def review(review_id, when, reviewed, decision, **extra):
    return StrategyReview(
        id=review_id, trigger=ReviewTrigger.SCHEDULED, started_at=when, finished_at=when, status=RunStatus.COMPLETED,
        failure_reason=None, reviewed_version=reviewed, decision=decision, cost=RunCost(0, 0, 0), trace_id=None, **extra,
    )


REVIEWS = (
    review("r1", at(8, 4), None, ReviewDecision.FIRST, reason="No history yet."),
    review(
        "r2", at(8, 18), 1, ReviewDecision.CHANGE, reason="Too slow to invest.",
        targets_verdict=TargetsVerdict.MISSED, targets_note="Two points behind SPY.", followed=Followed.YES,
        section_changes={StrategySection.CASH_AND_PACE: "Cash sat at 60%."}, scorecard=card("-1.5", "0.5"),
    ),
    review("r3", at(8, 29), 2, ReviewDecision.KEEP, reason="Too early to judge sizing.",
           targets_verdict=TargetsVerdict.MET, followed=Followed.YES),
    review(
        "r4", at(9, 12), 2, ReviewDecision.CHANGE, reason="Two big buys fell together.",
        targets_verdict=TargetsVerdict.PARTLY_MET, targets_note="No forced sells, but behind SPY.",
        followed=Followed.PARTLY, followed_note="Bought NVDA before earnings.",
        section_changes={StrategySection.POSITION_SIZE: "Full buys fell together."}, scorecard=card("-0.9", "0.6"),
    ),
)

BUY = OrderResult(Order("AAPL", Side.BUY, 10, "Rising estimates.", "what_i_look_for"), OrderStatus.EXECUTED,
                  Decimal("110"), Decimal("1"))
REJECTED = OrderResult(Order("MSFT", Side.BUY, 50, "Tariff dip.", DEVIATION), OrderStatus.REJECTED,
                       rejection_reason=RejectionReason.EXCEEDS_POSITION_CAP)


def context(**changes):
    fields = dict(
        profile=US_PROFILE,
        rules=TradingRules.for_exchange(US_PROFILE),
        now=NOW,
        portfolio=Portfolio(Decimal("3000"), {"AAPL": Position("AAPL", 10, Decimal("100"))}),
        prices={"AAPL": Decimal("110")},
        watchlist=WATCHLIST,
        market_overview=MarketOverview("Rates steady; chips weak.", (), at(9, 25)),
        current=V3,
        scorecard=card("1.8", "1.1"),
        orders=(ReviewedOrder(at(9, 15), BUY), ReviewedOrder(at(9, 16), REJECTED)),
        versions=(V1, V2, V3),
        reviews=REVIEWS,
    )
    return ReviewContext(**{**fields, **changes})


def test_the_first_review_gets_the_portfolio_watchlist_and_market_only():
    text = render_review_input(context(current=None, scorecard=None, orders=(), versions=(), reviews=()))

    assert "There is no strategy yet: write the first one." in text
    assert "- AAPL: Earnings" in text
    assert "Rates steady; chips weak." in text
    assert "Scorecard" not in text and "History" not in text


def test_the_portfolio_is_shown_with_each_holding_gain():
    text = render_review_input(context())

    assert "Cash: 3,000.00 USD" in text
    assert "Total portfolio value: 4,100.00 USD" in text
    assert "- AAPL: 10 shares, average cost 100, price 110, +10.0% on cost" in text


def test_the_current_strategy_is_shown_in_full_with_its_start():
    text = render_review_input(context())

    assert "Current strategy: v3, in use since 2026-09-12" in text
    assert "- What I look for (`what_i_look_for`): V3 look" in text
    assert "- My targets for this period (`targets`): V3 targets" in text


def test_the_scorecard_is_shown_as_computed():
    text = render_review_input(context())

    assert "Scorecard for v3 (2026-09-12 to 2026-09-26, computed by the system):" in text
    assert "- Return: portfolio +1.80%, SPY +1.10%" in text
    assert "- Trading runs: 9; trades: 6; fees: 6.00 USD" in text
    assert "- Closed trades: NVDA +84.10 USD, AMD -41.00 USD" in text
    assert "- Holdings: AAPL +10.0% on cost" in text
    assert "- Average cash: 18.2% of the portfolio" in text
    assert "- Orders naming a section: 5; deviations: 1" in text


OUTCOMES = (
    OrderOutcome(at(9, 15), Side.BUY, 10, "NVDA", Decimal("120"), Decimal("131"), 5, Decimal("2.1")),
    OrderOutcome(at(9, 16), Side.SELL, 5, "AAPL", Decimal("180"), Decimal("192"), 4, Decimal("1.8")),
    OrderOutcome(at(9, 25), Side.BUY, 1, "AMD", Decimal("100"), None, 1, None),
)
DAYS = (
    TradingDay(date(2026, 9, 15), 26, 1, 0, 1, 25, "Held; TSLA is above the sell line."),
    TradingDay(date(2026, 9, 16), 1, 0, 0, 0, 1, ""),
)


def test_the_scorecard_shows_what_happened_after_each_order():
    text = render_review_input(context(scorecard=replace(card("1.8", "1.1"), order_outcomes=OUTCOMES)))

    assert "After your executed orders (to this review, computed by the system):" in text
    assert "- 2026-09-15 BUY 10 NVDA at 120.00: now 131.00, +9.2%, in 5 trading days (SPY +2.1% over the same days)" in text
    assert (
        "- 2026-09-16 SELL 5 AAPL at 180.00: now 192.00, +6.7% since you sold, in 4 trading days "
        "(SPY +1.8% over the same days)"
    ) in text
    assert "- 2026-09-25 BUY 1 AMD at 100.00: price now unavailable, in 1 trading day (SPY unavailable)" in text


def test_the_scorecard_shows_the_unbought_watchlist_stocks():
    moves = (StockMove("AMD", Decimal("11.44")), StockMove("TSLA", None))

    text = render_review_input(context(scorecard=replace(card("1.8", "1.1"), unbought=moves)))

    assert "Watchlist stocks you did not buy in this period (move over the period; SPY +1.10%):" in text
    assert "- AMD +11.4%, TSLA unavailable" in text


def test_the_scorecard_shows_each_trading_day_with_its_last_summary():
    text = render_review_input(context(scorecard=replace(card("1.8", "1.1"), days=DAYS)))

    assert "Your trading days in this period (counts, then the day's last summary):" in text
    assert (
        '- 2026-09-15: 26 runs: 1 buy, 1 rejected order, 25 held. Last: "Held; TSLA is above the sell line."'
    ) in text
    assert "- 2026-09-16: 1 run: 1 held. Last: none" in text


def test_every_order_is_listed_with_its_section_result_and_reason():
    text = render_review_input(context())

    assert '- 2026-09-15 BUY 10 AAPL (What I look for): executed at 110. Reason: "Rising estimates."' in text
    assert (
        '- 2026-09-16 BUY 50 MSFT (deviation): rejected, '
        'Position would exceed the per-stock cap of the portfolio. Reason: "Tariff dip."'
    ) in text


def test_the_previous_version_is_in_full_and_older_ones_are_compact():
    text = render_review_input(context())

    assert "v2 (2026-08-18 to 2026-09-12):" in text
    assert "  - Position size (`position_size`): V2 size" in text
    assert "v1 (2026-08-04 to 2026-08-18):" in text
    assert "V1 look" not in text  # older versions are compact


def test_history_shows_why_each_version_changed_and_how_it_did():
    text = render_review_input(context())

    assert "  Kept on 2026-08-29 (targets met): Too early to judge sizing." in text
    assert (
        "  Changed on 2026-09-12 (targets partly met: No forced sells, but behind SPY.; followed: partly): "
        "Two big buys fell together."
    ) in text
    assert "    Position size changed: Full buys fell together." in text
    assert "    Its scorecard: portfolio -0.90%, SPY +0.60%, 6 trades, 18.2% average cash" in text
    assert "  Changed on 2026-08-18 (targets missed: Two points behind SPY.; followed: yes): Too slow to invest." in text
