from decimal import Decimal

from trade_simulator.core.order import Order, Side
from trade_simulator.core.portfolio import Portfolio, Position
from trade_simulator.core.trading_rules import (
    OrderStatus,
    RejectionReason,
    TradingRules,
    execute_orders,
)

RULES = TradingRules(fee_per_trade=Decimal("1"), max_position_fraction=Decimal("0.20"))
WATCHLIST = frozenset({"AAPL", "MSFT"})


def buy(symbol, quantity):
    return Order(symbol=symbol, side=Side.BUY, quantity=quantity)


def sell(symbol, quantity):
    return Order(symbol=symbol, side=Side.SELL, quantity=quantity)


def run(portfolio, orders, prices):
    return execute_orders(portfolio, orders, prices, WATCHLIST, RULES)


def test_valid_buy_deducts_cost_plus_fee_and_adds_position():
    report = run(Portfolio.starting(Decimal("10000")), [buy("AAPL", 5)], {"AAPL": Decimal("200")})

    [result] = report.results
    assert result.status is OrderStatus.EXECUTED
    assert result.price == Decimal("200")
    assert result.fee == Decimal("1")
    assert report.portfolio.cash == Decimal("8999")
    assert report.portfolio.quantity_of("AAPL") == 5


def test_valid_sell_adds_proceeds_minus_fee_and_reduces_position():
    portfolio = Portfolio(
        cash=Decimal("0"), positions={"AAPL": Position("AAPL", 5, Decimal("200"))}
    )

    report = run(portfolio, [sell("AAPL", 2)], {"AAPL": Decimal("210")})

    assert report.results[0].status is OrderStatus.EXECUTED
    assert report.portfolio.cash == Decimal("419")
    assert report.portfolio.quantity_of("AAPL") == 3


def test_selling_whole_position_removes_it():
    portfolio = Portfolio(
        cash=Decimal("0"), positions={"AAPL": Position("AAPL", 5, Decimal("200"))}
    )

    report = run(portfolio, [sell("AAPL", 5)], {"AAPL": Decimal("210")})

    assert "AAPL" not in report.portfolio.positions


def test_buy_that_breaks_20_percent_cap_is_rejected():
    # 11 x $200 = $2,200, which is more than 20% of the ~$10,000 portfolio.
    report = run(Portfolio.starting(Decimal("10000")), [buy("AAPL", 11)], {"AAPL": Decimal("200")})

    [result] = report.results
    assert result.status is OrderStatus.REJECTED
    assert result.rejection_reason is RejectionReason.EXCEEDS_POSITION_CAP
    assert report.portfolio == Portfolio.starting(Decimal("10000"))


def test_cap_counts_shares_already_held():
    portfolio = Portfolio(
        cash=Decimal("9000"), positions={"AAPL": Position("AAPL", 5, Decimal("200"))}
    )

    # Already 5 x $200 = $1,000 of $10,000; 6 more would make $2,200 (> 20%).
    report = run(portfolio, [buy("AAPL", 6)], {"AAPL": Decimal("200")})

    assert report.results[0].rejection_reason is RejectionReason.EXCEEDS_POSITION_CAP


def test_buy_without_enough_cash_is_rejected():
    report = run(Portfolio.starting(Decimal("500")), [buy("AAPL", 3)], {"AAPL": Decimal("200")})

    assert report.results[0].rejection_reason is RejectionReason.INSUFFICIENT_CASH


def test_buy_of_stock_not_on_watchlist_is_rejected():
    report = run(Portfolio.starting(Decimal("10000")), [buy("TSLA", 1)], {"TSLA": Decimal("250")})

    assert report.results[0].rejection_reason is RejectionReason.NOT_ON_WATCHLIST


def test_held_stock_off_the_watchlist_can_still_be_sold():
    portfolio = Portfolio(
        cash=Decimal("0"), positions={"TSLA": Position("TSLA", 2, Decimal("250"))}
    )

    report = run(portfolio, [sell("TSLA", 2)], {"TSLA": Decimal("250")})

    assert report.results[0].status is OrderStatus.EXECUTED


def test_selling_more_than_held_is_rejected_so_no_shorting():
    portfolio = Portfolio(
        cash=Decimal("0"), positions={"AAPL": Position("AAPL", 2, Decimal("200"))}
    )

    report = run(portfolio, [sell("AAPL", 3)], {"AAPL": Decimal("200")})

    assert report.results[0].rejection_reason is RejectionReason.INSUFFICIENT_SHARES


def test_selling_unheld_stock_is_rejected():
    report = run(Portfolio.starting(Decimal("10000")), [sell("AAPL", 1)], {"AAPL": Decimal("200")})

    assert report.results[0].rejection_reason is RejectionReason.INSUFFICIENT_SHARES


def test_order_without_price_is_rejected():
    report = run(Portfolio.starting(Decimal("10000")), [buy("AAPL", 1)], {})

    assert report.results[0].rejection_reason is RejectionReason.MISSING_PRICE


def test_sells_run_before_buys_so_freed_cash_can_be_used():
    portfolio = Portfolio(
        cash=Decimal("0"), positions={"MSFT": Position("MSFT", 20, Decimal("400"))}
    )

    report = run(
        portfolio,
        [buy("AAPL", 5), sell("MSFT", 4)],
        {"AAPL": Decimal("200"), "MSFT": Decimal("400")},
    )

    assert [r.order.side for r in report.results] == [Side.SELL, Side.BUY]
    assert all(r.status is OrderStatus.EXECUTED for r in report.results)
    # Sell: +1,600 - $1 fee. Buy: -1,000 - $1 fee.
    assert report.portfolio.cash == Decimal("598")


def test_rejected_order_does_not_stop_later_orders():
    report = run(
        Portfolio.starting(Decimal("10000")),
        [buy("TSLA", 1), buy("MSFT", 2)],
        {"TSLA": Decimal("250"), "MSFT": Decimal("400")},
    )

    assert [r.status for r in report.results] == [OrderStatus.REJECTED, OrderStatus.EXECUTED]


def test_input_portfolio_is_never_modified():
    portfolio = Portfolio.starting(Decimal("10000"))

    run(portfolio, [buy("AAPL", 5)], {"AAPL": Decimal("200")})

    assert portfolio == Portfolio.starting(Decimal("10000"))


def test_sell_whose_proceeds_do_not_cover_fee_is_rejected():
    portfolio = Portfolio(
        cash=Decimal("0"), positions={"AAPL": Position("AAPL", 1, Decimal("1"))}
    )

    report = run(portfolio, [sell("AAPL", 1)], {"AAPL": Decimal("0.50")})

    assert report.results[0].rejection_reason is RejectionReason.INSUFFICIENT_CASH


def test_average_cost_is_weighted_across_buys():
    portfolio = Portfolio(
        cash=Decimal("10000"), positions={"AAPL": Position("AAPL", 2, Decimal("100"))}
    )

    report = run(portfolio, [buy("AAPL", 2)], {"AAPL": Decimal("200")})

    assert report.portfolio.positions["AAPL"].average_cost == Decimal("150")
