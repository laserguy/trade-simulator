"""The run mode setting (D3): Manual (default), Daily at market open, or every 15 minutes."""

from enum import Enum

from trade_simulator.application.ports import SettingsStore
from trade_simulator.application.settings import SettingsError

RUN_MODE_SETTING = "run_mode"


class RunMode(Enum):
    MANUAL = "manual"
    DAILY = "daily"
    EVERY_15_MIN = "every_15_min"


class RunModeSetting:
    def __init__(self, store: SettingsStore) -> None:
        self._store = store

    def get(self) -> RunMode:
        saved = self._store.load_settings().get(RUN_MODE_SETTING)
        try:
            return RunMode(saved) if saved else RunMode.MANUAL
        except ValueError:
            return RunMode.MANUAL

    def set(self, mode: str) -> None:
        try:
            RunMode(mode)
        except ValueError as exc:
            choices = ", ".join(m.value for m in RunMode)
            raise SettingsError(f"Unknown run mode '{mode}'; expected one of {choices}") from exc
        self._store.save_setting(RUN_MODE_SETTING, mode)
