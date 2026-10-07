from datetime import date, datetime, timezone
from decimal import Decimal

from fakes import WeekdayCalendar
from trade_simulator.application.ports import ValueSnapshot
from trade_simulator.application.strategy_outcomes import last_close, order_outcomes, trading_days, unbought_moves
from trade_simulator.core.decision_log import OVERALL, DecisionRun, Finding, RunCost, RunStatus, RunTrigger
from trade_simulator.core.order import Order, Side
from trade_simulator.core.strategy_review import OrderOutcome, StockMove, TradingDay
from trade_simulator.core.trading_rules import OrderResult, OrderStatus, RejectionReason


def utc(month, day, hour, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=timezone.utc)


NOW = utc(10, 7, 20, 15)  # Wednesday 16:15 New York, after the close
CALENDAR = WeekdayCalendar()


def executed(symbol, side, quantity, price):
    return OrderResult(Order(symbol, side, quantity, "reason", "what_i_look_for"), OrderStatus.EXECUTED,
                       Decimal(price), Decimal("1"))


def rejected(symbol):
    return OrderResult(Order(symbol, Side.BUY, 99, "reason", "what_i_look_for"), OrderStatus.REJECTED,
                       rejection_reason=RejectionReason.INSUFFICIENT_CASH)


def run(run_id, started_at, results=(), status=RunStatus.COMPLETED, summary=None):
    return DecisionRun(
        id=run_id, trigger=RunTrigger.EVERY_15_MIN, started_at=started_at, finished_at=started_at, status=status,
        failure_reason=None, findings=(Finding(OVERALL, summary),) if summary else (),
        order_results=tuple(results), cost=RunCost(0, 0, 0), trace_id=None, strategy_version=1,
    )


BUY_RUN = run("a", utc(10, 1, 14, 15), [executed("NVDA", Side.BUY, 10, "120"), rejected("AMD")])  # Thu 10:15 NY
SELL_RUN = run("b", utc(10, 2, 14, 15), [executed("AAPL", Side.SELL, 5, "180")])  # Fri 10:15 NY
FAILED_RUN = run("c", utc(10, 2, 14, 30), status=RunStatus.FAILED)
SNAPSHOTS = [
    ValueSnapshot(utc(10, 1, 14, 0), Decimal("10000"), Decimal("490")),
    ValueSnapshot(utc(10, 1, 14, 16), Decimal("10000"), Decimal("500")),  # recorded right after the buy
    ValueSnapshot(utc(10, 2, 14, 16), Decimal("10000"), Decimal("502")),
]
PRICES = {"NVDA": Decimal("132"), "AAPL": Decimal("189")}


def outcomes(**changes):
    args = dict(runs=[BUY_RUN, SELL_RUN, FAILED_RUN], snapshots=SNAPSHOTS, prices=PRICES,
                benchmark_now=Decimal("510"), calendar=CALENDAR, now=NOW)
    return order_outcomes(**{**args, **changes})


def test_each_executed_order_shows_its_move_to_the_review_against_the_benchmark():
    buy, sell = outcomes()

    # Closes after the buy: Thu 1, Fri 2, Mon 5, Tue 6, Wed 7. Benchmark from the point right after the run.
    assert buy == OrderOutcome(utc(10, 1, 14, 15), Side.BUY, 10, "NVDA", Decimal("120"), Decimal("132"), 5, Decimal("2"))
    assert buy.change_percent == Decimal("10")
    assert (sell.symbol, sell.side, sell.trading_days, sell.change_percent) == ("AAPL", Side.SELL, 4, Decimal("5"))


def test_rejected_orders_and_failed_runs_have_no_outcome():
    assert [o.symbol for o in outcomes()] == ["NVDA", "AAPL"]


def test_missing_prices_are_unknown_not_guessed():
    buy, sell = outcomes(prices={"AAPL": Decimal("189")}, snapshots=[])

    assert (buy.price_now, buy.change_percent, buy.benchmark_percent) == (None, None, None)
    assert sell.price_now == Decimal("189")
    assert outcomes(benchmark_now=None)[0].benchmark_percent is None


def test_without_a_point_after_the_run_the_last_one_before_it_is_used():
    [buy, _] = outcomes(snapshots=SNAPSHOTS[:1])

    assert buy.benchmark_percent == (Decimal("510") - Decimal("490")) / Decimal("490") * 100


def test_an_order_after_the_last_close_has_had_no_trading_days():
    late = run("d", utc(10, 7, 20, 5), [executed("NVDA", Side.BUY, 1, "130")])  # 16:05 New York

    [outcome] = outcomes(runs=[late])

    assert outcome.trading_days == 0


def test_unbought_watchlist_stocks_show_their_move_biggest_rise_first():
    moves = unbought_moves(
        watchlist=["NVDA", "AMD", "GOOGL", "TSLA", "MSFT", "AAPL"],
        runs=[BUY_RUN, SELL_RUN],
        held=["MSFT"],
        start_prices={"AMD": Decimal("100"), "GOOGL": Decimal("200"), "TSLA": Decimal("250"), "AAPL": Decimal("170")},
        prices={"AMD": Decimal("111"), "GOOGL": Decimal("206"), "TSLA": Decimal("240"), "AAPL": Decimal("189")},
    )

    # NVDA was bought in the period and MSFT is held; AMD's buy was rejected, so it counts as not bought.
    assert moves == (
        StockMove("AAPL", (Decimal("189") - Decimal("170")) / Decimal("170") * 100),  # +11.2%
        StockMove("AMD", Decimal("11")),
        StockMove("GOOGL", Decimal("3")),
        StockMove("TSLA", Decimal("-4")),
    )


def test_an_unbought_stock_without_both_prices_is_unavailable_and_listed_last():
    moves = unbought_moves(
        watchlist=["AMD", "TSLA"], runs=[], held=[],
        start_prices={"TSLA": Decimal("250")}, prices={"AMD": Decimal("111"), "TSLA": Decimal("240")},
    )

    assert moves == (StockMove("TSLA", Decimal("-4")), StockMove("AMD", None))


def test_runs_are_grouped_by_exchange_day_with_the_last_summary():
    runs = [
        run("1", utc(10, 1, 13, 45), summary="Held; nothing met What I look for."),
        run("2", utc(10, 1, 14, 15), [executed("NVDA", Side.BUY, 10, "120"), rejected("AMD")], summary="Bought NVDA."),
        run("3", utc(10, 1, 19, 45), summary="Held; TSLA above the sell line."),
        run("4", utc(10, 2, 0, 30), status=RunStatus.FAILED),  # still Thursday in New York
        run("5", utc(10, 2, 14, 15), [executed("AAPL", Side.SELL, 5, "180")], summary="Sold AAPL."),
        run("6", utc(10, 2, 14, 30), status=RunStatus.SKIPPED),
    ]

    # Failed and skipped runs are technical problems, not decisions: left out.
    assert trading_days(runs, "America/New_York") == (
        TradingDay(date(2026, 10, 1), runs=3, buys=1, sells=0, rejected=1, held=2,
                   last_summary="Held; TSLA above the sell line."),
        TradingDay(date(2026, 10, 2), runs=1, buys=0, sells=1, rejected=0, held=0, last_summary="Sold AAPL."),
    )


def test_a_day_with_only_failed_runs_has_no_line():
    assert trading_days([run("1", utc(10, 1, 14, 15), status=RunStatus.FAILED)], "America/New_York") == ()


def test_a_run_without_a_summary_leaves_it_empty():
    [day] = trading_days([run("1", utc(10, 1, 14, 15))], "America/New_York")

    assert (day.runs, day.held, day.last_summary) == (1, 1, "")


def test_last_close_is_the_latest_close_at_or_before_a_moment():
    assert last_close(CALENDAR, utc(10, 5, 14, 0)) == utc(10, 2, 20, 0)  # Monday morning: Friday's close
    assert last_close(CALENDAR, utc(10, 2, 20, 0)) == utc(10, 2, 20, 0)
