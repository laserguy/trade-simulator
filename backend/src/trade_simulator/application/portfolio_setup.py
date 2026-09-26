from trade_simulator.application.ports import Repository
from trade_simulator.core.exchange_profile import ExchangeProfile
from trade_simulator.core.portfolio import Portfolio


def load_or_create_portfolio(repository: Repository, profile: ExchangeProfile) -> Portfolio:
    """Return the saved portfolio, creating one with the exchange's starting capital on first start (D5)."""
    portfolio = repository.load_portfolio()
    if portfolio is None:
        portfolio = Portfolio.starting(profile.starting_capital)
        repository.save_portfolio(portfolio)
    return portfolio
