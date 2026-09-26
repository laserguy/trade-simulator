"""Use case: build the very first watchlist automatically, once (D4 update).

Runs when there is no watchlist and an AI key exists. One attempt only: a failure is not retried
automatically, so a broken setup can't keep spending money; the "Refresh watchlist" button remains.
"""

from trade_simulator.application.ports import Repository, SettingsStore
from trade_simulator.application.refresh_watchlist import WatchlistRefresher
from trade_simulator.application.settings import SettingsService
from trade_simulator.core.decision_log import DecisionRun
from trade_simulator.core.errors import RunInProgressError

ATTEMPTED_SETTING = "initial_watchlist_attempted"


class InitialWatchlist:
    def __init__(
        self,
        *,
        repository: Repository,
        settings: SettingsService,
        store: SettingsStore,
        refresher: WatchlistRefresher,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._store = store
        self._refresher = refresher

    async def build_if_needed(self) -> DecisionRun | None:
        """Build the first watchlist if it's due. Returns the run, or None when nothing was started."""
        if self._repository.load_watchlist() is not None:
            return None
        if self._store.load_settings().get(ATTEMPTED_SETTING):
            return None
        if self._settings.view().selected_model_id is None:
            return None  # no AI key yet: try again when one is saved
        try:
            run = await self._refresher.refresh()
        except RunInProgressError:
            return None  # another run is busy; the next trigger will try again
        self._store.save_setting(ATTEMPTED_SETTING, run.started_at.isoformat())
        return run
