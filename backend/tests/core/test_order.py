import pytest

from trade_simulator.core.errors import InvalidOrderError
from trade_simulator.core.order import Order, Side


def test_order_normalises_symbol_to_upper_case():
    order = Order(symbol=" aapl ", side=Side.BUY, quantity=5)

    assert order.symbol == "AAPL"


@pytest.mark.parametrize("quantity", [0, -1])
def test_order_rejects_non_positive_quantity(quantity):
    with pytest.raises(InvalidOrderError):
        Order(symbol="AAPL", side=Side.BUY, quantity=quantity)


@pytest.mark.parametrize("quantity", [1.5, "3", True])
def test_order_requires_whole_shares(quantity):
    with pytest.raises(InvalidOrderError):
        Order(symbol="AAPL", side=Side.BUY, quantity=quantity)


def test_order_rejects_empty_symbol():
    with pytest.raises(InvalidOrderError):
        Order(symbol="  ", side=Side.SELL, quantity=1)
