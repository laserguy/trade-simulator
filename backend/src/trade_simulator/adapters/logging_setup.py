"""File logging with full tracebacks, and API keys scrubbed from every line (D19)."""

import logging
from collections.abc import Callable, Iterable
from logging.handlers import RotatingFileHandler
from pathlib import Path

REDACTED = "***"


class _RedactingFormatter(logging.Formatter):
    def __init__(self, secrets: Callable[[], Iterable[str]]) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s: %(message)s")
        self._secrets = secrets

    def format(self, record: logging.LogRecord) -> str:
        # Formats message and traceback together, then scrubs, so secrets inside exceptions are caught too.
        # Secrets are looked up on every line because keys can change in Settings while the app runs.
        text = super().format(record)
        for secret in self._secrets():
            if secret:
                text = text.replace(secret, REDACTED)
        return text


def configure_logging(
    log_file: Path, secrets: Iterable[str] | Callable[[], Iterable[str]], level: int = logging.INFO
) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    secret_source = secrets if callable(secrets) else (lambda fixed=list(secrets): fixed)
    handler.setFormatter(_RedactingFormatter(secret_source))

    root = logging.getLogger()
    for existing in list(root.handlers):
        if isinstance(existing, RotatingFileHandler):
            root.removeHandler(existing)
            existing.close()
    root.addHandler(handler)
    root.setLevel(level)
