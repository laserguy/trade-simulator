from decimal import Decimal

from trade_simulator.core.exchange_profile import US_PROFILE
from trade_simulator.core.trading_rules import TradingRules


def test_us_profile_holds_all_us_specific_settings():
    assert US_PROFILE.code == "US"
    assert US_PROFILE.currency == "USD"
    assert US_PROFILE.timezone == "America/New_York"
    assert US_PROFILE.stock_pool == "S&P 500"
    assert US_PROFILE.benchmark_symbol == "SPY"
    assert US_PROFILE.fee_per_trade == Decimal("1")
    assert US_PROFILE.starting_capital == Decimal("10000")


def test_trading_rules_take_fee_from_exchange_profile():
    rules = TradingRules.for_exchange(US_PROFILE)

    assert rules.fee_per_trade == Decimal("1")
    assert rules.max_position_fraction == Decimal("0.20")
