"""The API server prints the app's own INFO lines (uvicorn alone would drop them)."""

import io
import logging

import pytest

from app.core import logging as app_logging
from app.core.config import settings
from app.core.logging import APP_LOGGER, setup_logging


@pytest.fixture
def loggers():
    """(root, app) loggers; whatever a test does to them is undone afterwards."""
    root, app = logging.getLogger(), logging.getLogger(APP_LOGGER)
    saved = (root.handlers[:], app.handlers[:], app.level)
    yield root, app
    root.handlers[:], app.handlers[:] = saved[0], saved[1]
    app.setLevel(saved[2])


def as_a_fresh_server(root: logging.Logger, app: logging.Logger) -> None:
    """No handler on the root logger or on the app's, as in a new uvicorn process."""
    root.handlers.clear()
    app.handlers.clear()
    app.setLevel(logging.NOTSET)


def test_app_info_lines_are_printed_once(loggers, monkeypatch):
    root, app = loggers
    as_a_fresh_server(root, app)
    stream = io.StringIO()
    monkeypatch.setattr(app_logging.sys, "stderr", stream)
    assert setup_logging() is True
    assert setup_logging() is False  # a second start adds no second handler
    assert len(app.handlers) == 1

    logging.getLogger("construtiva.parsing.llm").info("plan parse: provider=x cache_hit=False")
    logging.getLogger("construtiva.parsing.llm").debug("not shown at INFO")
    logging.getLogger("some.library").info("not ours")
    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    assert lines[0].endswith(
        "INFO construtiva.parsing.llm | plan parse: provider=x cache_hit=False"
    )


def test_log_level_setting_is_used(loggers, monkeypatch):
    root, app = loggers
    as_a_fresh_server(root, app)
    monkeypatch.setattr(settings, "log_level", "warning")
    setup_logging()
    assert app.level == logging.WARNING
    monkeypatch.setattr(settings, "log_level", "nonsense")
    setup_logging()
    assert app.level == logging.INFO


def test_nothing_is_added_when_logging_is_already_configured(loggers):
    root, app = loggers
    as_a_fresh_server(root, app)
    root.addHandler(logging.NullHandler())  # a Celery worker or a script configured logging
    assert setup_logging() is False and app.handlers == []
