"""Validates and executes the Trading Agent's proposed orders (D6, D20).

The agent only proposes; this module decides. It never mutates the input portfolio,
so a caller can persist the resulting portfolio and results together, or not at all (D19).
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from trade_simulator.core.errors import MissingPriceError
from trade_simulator.core.exchange_profile import ExchangeProfile
from trade_simulator.core.order import Order, Side
from trade_simulator.core.portfolio import Portfolio


class OrderStatus(Enum):
    EXECUTED = "executed"
    REJECTED = "rejected"


class RejectionReason(Enum):
    NOT_ON_WATCHLIST = "Only watchlist stocks can be bought"
    MISSING_PRICE = "No current price available"
    INSUFFICIENT_CASH = "Not enough cash to cover the trade and fee"
    INSUFFICIENT_SHARES = "Cannot sell more shares than held (no shorting)"
    EXCEEDS_POSITION_CAP = "Position would exceed the per-stock cap of the portfolio"


@dataclass(frozen=True)
class TradingRules:
    fee_per_trade: Decimal
    max_position_fraction: Decimal = Decimal("0.20")

    @classmethod
    def for_exchange(cls, profile: ExchangeProfile) -> "TradingRules":
        return cls(fee_per_trade=profile.fee_per_trade)


@dataclass(frozen=True)
class OrderResult:
    order: Order
    status: OrderStatus
    price: Decimal | None = None
    fee: Decimal | None = None
    rejection_reason: RejectionReason | None = None


@dataclass(frozen=True)
class ExecutionReport:
    portfolio: Portfolio
    results: tuple[OrderResult, ...]


def execute_orders(
    portfolio: Portfolio,
    orders: Iterable[Order],
    prices: Mapping[str, Decimal],
    watchlist: frozenset[str],
    rules: TradingRules,
) -> ExecutionReport:
    """Apply orders one by one, sells first so freed cash can fund buys.

    A rejected order is recorded and skipped; it never stops later orders.
    """
    orders = list(orders)
    ordered = [o for o in orders if o.side is Side.SELL] + [o for o in orders if o.side is Side.BUY]

    results = []
    for order in ordered:
        portfolio, result = _execute_one(portfolio, order, prices, watchlist, rules)
        results.append(result)
    return ExecutionReport(portfolio=portfolio, results=tuple(results))


def _execute_one(portfolio, order, prices, watchlist, rules) -> tuple[Portfolio, OrderResult]:
    def rejected(reason: RejectionReason) -> tuple[Portfolio, OrderResult]:
        return portfolio, OrderResult(order, OrderStatus.REJECTED, rejection_reason=reason)

    if order.side is Side.BUY and order.symbol not in watchlist:
        return rejected(RejectionReason.NOT_ON_WATCHLIST)
    price = prices.get(order.symbol)
    if price is None:
        return rejected(RejectionReason.MISSING_PRICE)
    fee = rules.fee_per_trade

    if order.side is Side.SELL:
        if order.quantity > portfolio.quantity_of(order.symbol):
            return rejected(RejectionReason.INSUFFICIENT_SHARES)
        updated = portfolio.after_sell(order.symbol, order.quantity, price, fee)
    else:
        updated = portfolio.after_buy(order.symbol, order.quantity, price, fee)
        if updated.cash >= 0 and _exceeds_position_cap(updated, order.symbol, prices, rules):
            return rejected(RejectionReason.EXCEEDS_POSITION_CAP)

    if updated.cash < 0:
        return rejected(RejectionReason.INSUFFICIENT_CASH)
    return updated, OrderResult(order, OrderStatus.EXECUTED, price=price, fee=fee)


def _exceeds_position_cap(portfolio: Portfolio, symbol: str, prices, rules: TradingRules) -> bool:
    try:
        total = portfolio.total_value(prices)
    except MissingPriceError:
        # Can't prove the buy is within the cap, so treat it as exceeding it.
        return True
    position_value = portfolio.quantity_of(symbol) * prices[symbol]
    return position_value > total * rules.max_position_fraction
