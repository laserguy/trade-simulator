from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from decimal import Decimal

from trade_simulator.core.errors import MissingPriceError


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: int
    average_cost: Decimal


@dataclass(frozen=True)
class Portfolio:
    """Immutable snapshot of cash and holdings. Changes return a new Portfolio."""

    cash: Decimal
    positions: Mapping[str, Position] = field(default_factory=dict)

    @classmethod
    def starting(cls, cash: Decimal) -> "Portfolio":
        return cls(cash=cash, positions={})

    def quantity_of(self, symbol: str) -> int:
        position = self.positions.get(symbol)
        return position.quantity if position else 0

    def total_value(self, prices: Mapping[str, Decimal]) -> Decimal:
        """Cash plus every holding valued at its current price."""
        holdings = Decimal("0")
        for symbol, position in self.positions.items():
            if symbol not in prices:
                raise MissingPriceError(symbol)
            holdings += position.quantity * prices[symbol]
        return self.cash + holdings

    def after_buy(self, symbol: str, quantity: int, price: Decimal, fee: Decimal) -> "Portfolio":
        held = self.positions.get(symbol)
        if held:
            total_quantity = held.quantity + quantity
            average_cost = (held.quantity * held.average_cost + quantity * price) / total_quantity
        else:
            total_quantity, average_cost = quantity, price
        positions = {**self.positions, symbol: Position(symbol, total_quantity, average_cost)}
        return replace(self, cash=self.cash - quantity * price - fee, positions=positions)

    def after_sell(self, symbol: str, quantity: int, price: Decimal, fee: Decimal) -> "Portfolio":
        held = self.positions[symbol]
        positions = dict(self.positions)
        remaining = held.quantity - quantity
        if remaining:
            positions[symbol] = replace(held, quantity=remaining)
        else:
            del positions[symbol]
        return replace(self, cash=self.cash + quantity * price - fee, positions=positions)
