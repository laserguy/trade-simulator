import pytest

from trade_simulator.adapters.sqlite_repository import SqliteRepository
from trade_simulator.application.run_mode import RunMode, RunModeSetting
from trade_simulator.application.settings import SettingsError


@pytest.fixture
def store(tmp_path):
    repo = SqliteRepository(tmp_path / "sim.sqlite3")
    repo.initialize()
    return repo


def test_manual_is_the_default(store):
    assert RunModeSetting(store).get() is RunMode.MANUAL


def test_choice_is_saved(store):
    RunModeSetting(store).set("every_15_min")

    assert RunModeSetting(store).get() is RunMode.EVERY_15_MIN


def test_unknown_mode_is_rejected(store):
    with pytest.raises(SettingsError):
        RunModeSetting(store).set("hourly")
