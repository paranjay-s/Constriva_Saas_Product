"""Logging setup for the API server.

uvicorn configures only its own loggers. Without this, the app's loggers ("construtiva.*")
have no handler and their INFO lines are dropped, including the one line per plan parse
(provider, model, tokens, duration, cache hit).

`setup_logging()` sends "construtiva.*" at LOG_LEVEL (default INFO) to stderr. It leaves the
root logger and uvicorn's loggers alone, and does nothing when something else has already
configured the root logger (a Celery worker, a script, a test runner), so lines are never
printed twice. Nothing in the app logs file contents or keys.
"""

import logging
import sys

from app.core.config import settings

APP_LOGGER = "construtiva"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s | %(message)s"


def _level(name: str) -> int:
    level = logging.getLevelName(str(name or "").strip().upper())
    return level if isinstance(level, int) else logging.INFO


def setup_logging() -> bool:
    """Attach the app's log handler once. Returns True when it attached one."""
    app_logger = logging.getLogger(APP_LOGGER)
    app_logger.setLevel(_level(settings.log_level))
    if logging.getLogger().handlers or app_logger.handlers:
        return False  # already configured elsewhere: its handlers will print our lines
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    app_logger.addHandler(handler)
    return True
