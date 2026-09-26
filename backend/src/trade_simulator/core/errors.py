"""Typed exceptions (D19). Every error raised by this app derives from TradeSimulatorError."""


class TradeSimulatorError(Exception):
    """Base class for all errors raised by the trade simulator."""


class DomainError(TradeSimulatorError):
    """A business rule was broken or core input was invalid."""


class InvalidOrderError(DomainError):
    """An order is malformed (bad symbol or quantity)."""


class MissingPriceError(DomainError):
    """A price needed for a calculation was not provided."""

    def __init__(self, symbol: str) -> None:
        super().__init__(f"No price available for {symbol}")
        self.symbol = symbol


class BudgetExceededError(DomainError):
    """A run tried to use more research calls or searches than its limit allows (D13, D14)."""


class StorageError(TradeSimulatorError):
    """Reading or writing persistent data failed."""


class MarketDataError(TradeSimulatorError):
    """Market data could not be fetched (network, rate limit, bad API key)."""


class SearchError(TradeSimulatorError):
    """Web search failed."""


class ConfigError(TradeSimulatorError):
    """Configuration is missing or invalid. Messages name settings, never their secret values."""


class MarketClosedError(TradeSimulatorError):
    """A decision run was requested while the market is closed (D21)."""

    def __init__(self, next_open) -> None:
        super().__init__(f"Market closed; opens {next_open:%a %d %b %H:%M %Z}")
        self.next_open = next_open


class RunInProgressError(TradeSimulatorError):
    """Another run is still in progress; runs never overlap (D20)."""

    def __init__(self) -> None:
        super().__init__("Another run is still in progress")


class AgentError(TradeSimulatorError):
    """The AI agents failed mid-run. Carries what was spent so the failed run can still be logged (D22)."""

    def __init__(self, message: str, *, trace_id: str | None = None, usage=None) -> None:
        super().__init__(message)
        self.trace_id = trace_id
        self.usage = usage
