import logging

from app.core.logging import configure_logging


def test_configure_logging_sets_root_level():
    configure_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_is_idempotent():
    configure_logging("INFO")
    configure_logging("INFO")  # must not raise or duplicate handlers
    assert logging.getLogger().level == logging.INFO
