"""Decides, on each tick, whether a scheduled run or the daily close value point is due.

Holds no timer itself: the web app calls `due(now)` every few seconds. After a long sleep, a missed
slot causes one catch-up run, never a burst. Overlap is handled by the runner, which logs a
skipped run if another one is still going (D20).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from trade_simulator.application.run_mode import RunMode
from trade_simulator.application.schedule import Schedule
from trade_simulator.core.decision_log import RunTrigger

TRIGGERS = {RunMode.DAILY: RunTrigger.DAILY, RunMode.EVERY_15_MIN: RunTrigger.EVERY_15_MIN}


class RunModeSource(Protocol):
    def get(self) -> RunMode: ...


@dataclass(frozen=True)
class Due:
    run: RunTrigger | None
    snapshot: bool


class Scheduler:
    def __init__(self, schedule: Schedule, run_mode: RunModeSource, now: datetime) -> None:
        self._schedule = schedule
        self._run_mode = run_mode
        self._mode = run_mode.get()
        self._next_run = schedule.next_run(self._mode, now)
        self._next_close = schedule.next_close(now)

    def next_run_at(self) -> datetime | None:
        return self._next_run

    def due(self, now: datetime) -> Due:
        mode = self._run_mode.get()
        if mode is not self._mode:
            self._mode = mode
            self._next_run = self._schedule.next_run(mode, now)

        run = None
        if self._next_run is not None and now >= self._next_run:
            run = TRIGGERS[mode]
            self._next_run = self._schedule.next_run(mode, now)

        snapshot = now >= self._next_close
        if snapshot:
            self._next_close = self._schedule.next_close(now)
        return Due(run=run, snapshot=snapshot)
