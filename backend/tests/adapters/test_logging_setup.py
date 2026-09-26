import logging

from trade_simulator.adapters.logging_setup import configure_logging


def test_log_file_gets_tracebacks_but_never_secrets(tmp_path):
    log_file = tmp_path / "logs" / "app.log"
    configure_logging(log_file, secrets=["sk-secret-123", ""])
    logger = logging.getLogger("trade_simulator.test")

    try:
        raise RuntimeError("call failed with key sk-secret-123")
    except RuntimeError:
        logger.exception("Run failed")
    for handler in logging.getLogger().handlers:
        handler.flush()

    text = log_file.read_text()
    assert "Traceback" in text
    assert "Run failed" in text
    assert "sk-secret-123" not in text
    assert "***" in text
