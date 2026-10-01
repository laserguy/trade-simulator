from datetime import datetime, timedelta, timezone
from decimal import Decimal

from trade_simulator.application.ports import BenchmarkStart, ExecutedTrade, Performance
from trade_simulator.application.trade_memory import open_position_buys, performance_since_start
from trade_simulator.core.exchange_profile import US_PROFILE
from trade_simulator.core.order import Side
from trade_simulator.core.portfolio import Portfolio, Position

START = datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc)


def trade(symbol, side, quantity, day=0, reason="Because"):
    return ExecutedTrade(START + timedelta(days=day), side, quantity, Decimal("100"), f"run-{day}", symbol, reason)


def test_every_buy_of_a_held_stock_is_kept_with_its_reason():
    first = trade("WMT", Side.BUY, 10, day=0, reason="Defensive")
    second = trade("WMT", Side.BUY, 5, day=1, reason="Added on a dip")

    assert open_position_buys([first, second]) == {"WMT": (first, second)}


def test_buys_before_a_full_sale_belong_to_a_closed_position():
    rebuy = trade("WMT", Side.BUY, 4, day=2, reason="Back in")
    trades = [trade("WMT", Side.BUY, 10, day=0), trade("WMT", Side.SELL, 10, day=1), rebuy]

    assert open_position_buys(trades) == {"WMT": (rebuy,)}


def test_a_stock_sold_completely_has_no_open_buys():
    trades = [trade("WMT", Side.BUY, 10, day=0), trade("WMT", Side.SELL, 10, day=1)]

    assert open_position_buys(trades) == {}


def test_a_partial_sale_keeps_the_buys():
    buy = trade("WMT", Side.BUY, 10, day=0)

    assert open_position_buys([buy, trade("WMT", Side.SELL, 4, day=1)]) == {"WMT": (buy,)}


def test_performance_compares_the_portfolio_with_the_benchmark_since_tracking_began():
    portfolio = Portfolio(Decimal("8300"), {"AAPL": Position("AAPL", 10, Decimal("190"))})
    start = BenchmarkStart("SPY", Decimal("500"), START)

    result = performance_since_start(portfolio, {"AAPL": Decimal("200")}, US_PROFILE, start, Decimal("510"))

    assert result == Performance(START, Decimal("3"), "SPY", Decimal("2"))


def test_performance_is_unknown_without_a_benchmark_start_or_a_price():
    portfolio = Portfolio(Decimal("8000"), {"AAPL": Position("AAPL", 10, Decimal("190"))})
    start = BenchmarkStart("SPY", Decimal("500"), START)
    prices = {"AAPL": Decimal("200")}

    assert performance_since_start(portfolio, prices, US_PROFILE, None, Decimal("510")) is None
    assert performance_since_start(portfolio, prices, US_PROFILE, start, None) is None
    assert performance_since_start(portfolio, {}, US_PROFILE, start, Decimal("510")) is None
