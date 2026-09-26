import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from fakes import FakeAgent, FakeUniverse, FixedClock, proposal
from trade_simulator.adapters.sqlite_repository import SqliteRepository
from trade_simulator.application.initial_watchlist import InitialWatchlist
from trade_simulator.application.refresh_watchlist import WatchlistRefresher
from trade_simulator.application.run_guard import RunGuard
from trade_simulator.application.settings import SettingsService
from trade_simulator.core.decision_log import RunStatus, Watchlist, WatchlistEntry
from trade_simulator.core.exchange_profile import US_PROFILE
from trade_simulator.core.model_pricing import ModelCatalogue, ModelOption

NOW = datetime(2026, 9, 26, 20, 0, tzinfo=timezone.utc)
CATALOGUE = ModelCatalogue(
    date(2026, 9, 26), (ModelOption("openai", "gpt-6-luna", "GPT-6 Luna", Decimal("0.1"), Decimal("0.5")),)
)


@pytest.fixture
def repo(tmp_path):
    repository = SqliteRepository(tmp_path / "sim.sqlite3")
    repository.initialize()
    return repository


def make(repo, agent=None, guard=None):
    agent = agent or FakeAgent(proposal=proposal([WatchlistEntry("AAPL", "Earnings")]))
    settings = SettingsService(store=repo, catalogue=CATALOGUE, default_model_id="gpt-6-luna")
    refresher = WatchlistRefresher(
        repository=repo, agent=agent, universe=FakeUniverse(), profile=US_PROFILE,
        guard=guard or RunGuard(), clock=FixedClock(NOW),
    )
    return InitialWatchlist(repository=repo, settings=settings, store=repo, refresher=refresher), settings, agent


def build(initial):
    return asyncio.run(initial.build_if_needed())


def test_builds_first_watchlist_when_none_exists_and_a_key_is_saved(repo):
    initial, settings, _ = make(repo)
    settings.set_api_key("openai", "sk-1")

    run = build(initial)

    assert run.status is RunStatus.COMPLETED
    assert repo.load_watchlist().symbols == {"AAPL"}


def test_does_nothing_without_an_ai_key(repo):
    initial, _, agent = make(repo)

    assert build(initial) is None
    assert agent.refresh_contexts == []


def test_does_nothing_when_a_watchlist_already_exists(repo):
    repo.save_watchlist(Watchlist((WatchlistEntry("MSFT", "x"),), NOW))
    initial, settings, agent = make(repo)
    settings.set_api_key("openai", "sk-1")

    assert build(initial) is None
    assert agent.refresh_contexts == []


def test_happens_only_once_even_if_it_failed(repo):
    initial, settings, agent = make(repo, agent=FakeAgent(error=RuntimeError("model down")))
    settings.set_api_key("openai", "sk-1")

    first = build(initial)
    second = build(initial)

    assert first.status is RunStatus.FAILED
    assert second is None
    assert len(agent.refresh_contexts) == 1


def test_waits_if_another_run_is_in_progress(repo):
    guard = RunGuard()
    guard.try_acquire()
    initial, settings, agent = make(repo, guard=guard)
    settings.set_api_key("openai", "sk-1")

    assert build(initial) is None
    guard.release()

    assert build(initial).status is RunStatus.COMPLETED
