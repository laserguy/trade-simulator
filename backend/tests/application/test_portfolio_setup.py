from decimal import Decimal

from trade_simulator.adapters.sqlite_repository import SqliteRepository
from trade_simulator.application.portfolio_setup import load_or_create_portfolio
from trade_simulator.core.exchange_profile import US_PROFILE
from trade_simulator.core.portfolio import Portfolio


def make_repo(tmp_path):
    repo = SqliteRepository(tmp_path / "sim.sqlite3")
    repo.initialize()
    return repo


def test_first_start_creates_portfolio_with_starting_capital(tmp_path):
    repo = make_repo(tmp_path)

    portfolio = load_or_create_portfolio(repo, US_PROFILE)

    assert portfolio == Portfolio.starting(Decimal("10000"))
    assert repo.load_portfolio() == portfolio


def test_existing_portfolio_is_returned_unchanged(tmp_path):
    repo = make_repo(tmp_path)
    existing = Portfolio.starting(Decimal("1234"))
    repo.save_portfolio(existing)

    assert load_or_create_portfolio(repo, US_PROFILE) == existing
