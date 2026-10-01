from dataclasses import dataclass
from enum import Enum

from trade_simulator.core.errors import InvalidOrderError
from trade_simulator.core.strategy import ORDER_BASES


class Side(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True)
class Order:
    """An order proposed by the Trading Agent. Whole shares only (D6)."""

    symbol: str
    side: Side
    quantity: int
    reason: str = ""
    # The strategy section the order follows, or DEVIATION (D43); None for orders from before strategies.
    follows: str | None = None

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        if not symbol:
            raise InvalidOrderError("Order symbol must not be empty")
        # bool is a subclass of int, so exclude it explicitly.
        if type(self.quantity) is not int:
            raise InvalidOrderError(f"Quantity must be a whole number of shares, got {self.quantity!r}")
        if self.quantity <= 0:
            raise InvalidOrderError(f"Quantity must be positive, got {self.quantity}")
        if self.follows is not None and self.follows not in ORDER_BASES:
            raise InvalidOrderError(f"Unknown strategy section {self.follows!r}")
        object.__setattr__(self, "symbol", symbol)
