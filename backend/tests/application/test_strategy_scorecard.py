from datetime import datetime, timedelta, timezone
from decimal import Decimal

from trade_simulator.application.ports import ExecutedTrade, ValueSnapshot
from trade_simulator.application.strategy_scorecard import build_scorecard
from trade_simulator.core.decision_log import DecisionRun, RunCost, RunStatus, RunTrigger
from trade_simulator.core.order import Order, Side
from trade_simulator.core.portfolio import Portfolio, Position
from trade_simulator.core.strategy import DEVIATION, Strategy, StrategyVersion
from trade_simulator.core.strategy_review import ClosedTrade, HoldingResult
from trade_simulator.core.trading_rules import OrderResult, OrderStatus, RejectionReason

START = datetime(2026, 9, 14, 14, 0, tzinfo=timezone.utc)
NOW = START + timedelta(days=14)
STRATEGY = Strategy("Look for", "Size", "Sell", "Cash", "Targets")
VERSION = StrategyVersion(number=1, strategy=STRATEGY, started_at=START, ended_at=None, review_id="rev-1")
FEE = Decimal("1")


def executed(symbol, side, quantity, price, follows):
    return OrderResult(Order(symbol, side, quantity, "reason", follows), OrderStatus.EXECUTED, Decimal(price), FEE)


def run(run_id, started_at, results, status=RunStatus.COMPLETED):
    return DecisionRun(
        id=run_id,
        trigger=RunTrigger.DAILY,
        started_at=started_at,
        finished_at=started_at,
        status=status,
        failure_reason=None,
        findings=(),
        order_results=tuple(results),
        cost=RunCost(0, 0, 0),
        trace_id=None,
        strategy_version=1,
    )


RUN_A = run(
    "a",
    START + timedelta(days=1),
    [
        executed("AAPL", Side.BUY, 10, "110", "what_i_look_for"),
        OrderResult(
            Order("NVDA", Side.BUY, 99, "reason", "what_i_look_for"),
            OrderStatus.REJECTED,
            rejection_reason=RejectionReason.INSUFFICIENT_CASH,
        ),
    ],
)
RUN_B = run(
    "b",
    START + timedelta(days=2),
    [executed("AAPL", Side.SELL, 4, "120", "when_i_sell"), executed("MSFT", Side.BUY, 5, "200", DEVIATION)],
)
FAILED = run("c", START + timedelta(days=3), [], status=RunStatus.FAILED)

# Every executed trade, oldest first: the AAPL bought before this version sets part of the cost basis.
TRADES = [
    ExecutedTrade(START - timedelta(days=5), Side.BUY, 10, Decimal("90"), "old", "AAPL"),
    ExecutedTrade(RUN_A.started_at, Side.BUY, 10, Decimal("110"), "a", "AAPL"),
    ExecutedTrade(RUN_B.started_at, Side.SELL, 4, Decimal("120"), "b", "AAPL"),
    ExecutedTrade(RUN_B.started_at, Side.BUY, 5, Decimal("200"), "b", "MSFT"),
]
SNAPSHOTS = [
    ValueSnapshot(START - timedelta(hours=2), Decimal("10000"), Decimal("500")),
    ValueSnapshot(START + timedelta(days=1), Decimal("10000"), Decimal("505"), cash=Decimal("4000")),
    ValueSnapshot(NOW - timedelta(hours=1), Decimal("10200"), Decimal("510"), cash=Decimal("3060")),
]
PORTFOLIO = Portfolio(
    Decimal("3060"),
    {"AAPL": Position("AAPL", 16, Decimal("100")), "MSFT": Position("MSFT", 5, Decimal("200"))},
)
PRICES = {"AAPL": Decimal("110"), "MSFT": Decimal("190")}


def card(**changes):
    args = dict(
        version=VERSION,
        runs=[RUN_A, RUN_B, FAILED],
        trades=TRADES,
        snapshots=SNAPSHOTS,
        portfolio=PORTFOLIO,
        prices=PRICES,
        now=NOW,
    )
    return build_scorecard(**{**args, **changes})


def test_period_runs_from_the_version_start_to_now():
    scorecard = card()

    assert (scorecard.period_start, scorecard.period_end) == (START, NOW)


def test_returns_compare_portfolio_and_benchmark_over_the_period():
    scorecard = card()

    # From the last point before the version started (10,000 / 500) to the latest one (10,200 / 510).
    assert scorecard.portfolio_percent == Decimal("2")
    assert scorecard.benchmark_percent == Decimal("2")


def test_counts_completed_runs_and_executed_trades_with_their_fees():
    scorecard = card()

    assert (scorecard.trading_runs, scorecard.trades, scorecard.fees) == (2, 3, Decimal("3"))


def test_each_sell_is_a_closed_trade_with_its_gain_after_the_fee():
    # Average cost before the sale: (10 x 90 + 10 x 110) / 20 = 100. Gain: 4 x (120 - 100) - 1 fee.
    assert card().closed_trades == (ClosedTrade("AAPL", Decimal("79")),)


def test_holdings_show_their_gain_on_cost_and_skip_stocks_without_a_price():
    assert card().holdings == (HoldingResult("AAPL", Decimal("10")), HoldingResult("MSFT", Decimal("-5")))
    assert card(prices={"AAPL": Decimal("110")}).holdings == (HoldingResult("AAPL", Decimal("10")),)


def test_average_cash_comes_from_the_points_inside_the_period():
    assert card().average_cash_percent == Decimal("35")  # 40% and 30%


def test_average_cash_falls_back_to_now_when_no_point_has_cash():
    scorecard = card(snapshots=SNAPSHOTS[:1])

    # 3,060 cash of 3,060 + 16 x 110 + 5 x 190 = 5,770.
    assert scorecard.average_cash_percent == Decimal("3060") / Decimal("5770") * 100


def test_executed_orders_are_split_into_followed_and_deviations():
    scorecard = card()

    assert (scorecard.followed_orders, scorecard.deviations) == (2, 1)


def test_without_value_points_returns_are_zero():
    scorecard = card(snapshots=[])

    assert (scorecard.portfolio_percent, scorecard.benchmark_percent) == (Decimal("0"), Decimal("0"))
