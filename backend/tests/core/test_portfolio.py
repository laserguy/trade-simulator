from decimal import Decimal

import pytest

from trade_simulator.core.errors import MissingPriceError
from trade_simulator.core.portfolio import Portfolio, Position


def test_new_portfolio_holds_only_cash():
    portfolio = Portfolio.starting(Decimal("10000"))

    assert portfolio.cash == Decimal("10000")
    assert portfolio.positions == {}
    assert portfolio.total_value({}) == Decimal("10000")


def test_total_value_adds_holdings_at_current_prices():
    portfolio = Portfolio(
        cash=Decimal("1000"),
        positions={"AAPL": Position("AAPL", 10, Decimal("150"))},
    )

    assert portfolio.total_value({"AAPL": Decimal("200")}) == Decimal("3000")


def test_total_value_needs_a_price_for_every_holding():
    portfolio = Portfolio(
        cash=Decimal("1000"),
        positions={"AAPL": Position("AAPL", 10, Decimal("150"))},
    )

    with pytest.raises(MissingPriceError):
        portfolio.total_value({})


def test_quantity_of_unheld_symbol_is_zero():
    assert Portfolio.starting(Decimal("10000")).quantity_of("MSFT") == 0
