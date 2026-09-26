"""The live step timeline of the run in progress (D28). Held in memory only; a new run starts it afresh."""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ActivityEvent:
    at: datetime
    actor: str
    text: str


@dataclass(frozen=True)
class ActivitySnapshot:
    active: bool
    label: str | None
    events: tuple[ActivityEvent, ...]


class ActivityFeed:
    """Thread-safe: agent tools report from worker threads while the API reads."""

    def __init__(self, clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._active = False
        self._label: str | None = None
        self._events: list[ActivityEvent] = []

    def begin(self, label: str) -> None:
        with self._lock:
            self._active, self._label, self._events = True, label, []

    def add(self, actor: str, text: str) -> None:
        with self._lock:
            if self._active:
                self._events.append(ActivityEvent(self._clock(), actor, text))

    def end(self) -> None:
        with self._lock:
            self._active = False

    def snapshot(self) -> ActivitySnapshot:
        with self._lock:
            return ActivitySnapshot(self._active, self._label, tuple(self._events))


class NoActivity:
    """Stand-in when nobody is watching (e.g. the command-line tool)."""

    def begin(self, label: str) -> None: ...

    def add(self, actor: str, text: str) -> None: ...

    def end(self) -> None: ...
