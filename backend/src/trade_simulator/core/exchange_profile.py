from dataclasses import dataclass
from datetime import time
from decimal import Decimal


@dataclass(frozen=True)
class ExchangeProfile:
    """Everything exchange-specific lives here, so nothing is hard-coded elsewhere (D24).

    `calendar_code` names the official trading calendar (holidays, early closes) used for D21.
    """

    code: str
    calendar_code: str
    name: str
    currency: str
    timezone: str
    regular_open: time
    regular_close: time
    stock_pool: str
    benchmark_symbol: str
    fee_per_trade: Decimal
    starting_capital: Decimal


US_PROFILE = ExchangeProfile(
    code="US",
    calendar_code="XNYS",  # NYSE and NASDAQ share the same trading calendar
    name="NYSE / NASDAQ",
    currency="USD",
    timezone="America/New_York",
    regular_open=time(9, 30),
    regular_close=time(16, 0),
    stock_pool="S&P 500",
    benchmark_symbol="SPY",
    fee_per_trade=Decimal("1"),
    starting_capital=Decimal("10000"),
)
