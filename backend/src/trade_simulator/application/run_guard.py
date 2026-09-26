import threading


class RunGuard:
    """Ensures only one run (decision or watchlist refresh) happens at a time (D20).

    Shared by every use case that runs agents. Non-blocking: a busy guard means "skip or refuse", never "wait".
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        return self._lock.acquire(blocking=False)

    def release(self) -> None:
        self._lock.release()

    @property
    def busy(self) -> bool:
        return self._lock.locked()
