"""Two caches for the plan parser: the model's reply, and the normalised PlanJSON.

  * The reply cache holds what the model answered for a PDF. Its key is the PDF's sha256,
    the prompt version, the provider and the model: the only things that decide what a
    model is asked and who answers. As long as none of them changes, the model is never
    called for that PDF again.
  * The plan cache holds the normalised PlanJSON. Its key adds the parser and schema
    versions. When the normaliser or a rule changes (a new `PARSER_VERSION`), the plan
    entry no longer matches and the plan is built again from the cached reply, without a
    model call.

The prompt version stands for everything sent to the model: the prompt text, the wire
schema and the way pages are rendered. Changing any of them means raising it
(`tests/unit/test_plan_parser.py` pins a fingerprint so it cannot be forgotten).

Entries live in the folder the blueprint import has always cached in
(`backend/.tmp/plan_cache`, git-ignored). Only the reply and the plan are stored: no
project, user or plan-row ids, so a cache hit can never hand one project another project's
records.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from app.modules.plans.schemas import SCHEMA_VERSION, PlanJSON

logger = logging.getLogger("construtiva.parsing.plan_cache")

BACKEND_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CACHE_DIR = BACKEND_ROOT / ".tmp" / "plan_cache"


def plan_cache_key(
    pdf_sha256: str, parser_version: str, prompt_version: str, provider: str, model: str
) -> str:
    """Everything that decides what a PDF parses to.

    The provider and the model are part of it: after a switch to another model the PDF is
    parsed again, and the older model's result is not returned as if it were the new one's.
    """
    return (
        f"{pdf_sha256}.parser-{parser_version}.prompt-{prompt_version}"
        f".schema-{SCHEMA_VERSION}.{provider}.{model}"
    )


def reply_cache_key(pdf_sha256: str, prompt_version: str, provider: str, model: str) -> str:
    """Everything that decides what a model is asked about a PDF, and which model answers."""
    return f"{pdf_sha256}.reply.prompt-{prompt_version}.{provider}.{model}"


class PlanCache(Protocol):
    def get(self, key: str) -> dict | None: ...

    def put(self, key: str, plan: dict) -> None: ...

    def get_reply(self, key: str) -> dict | None: ...

    def put_reply(self, key: str, record: dict) -> None: ...


class NullPlanCache:
    """Caching switched off."""

    def get(self, key: str) -> dict | None:
        return None

    def put(self, key: str, plan: dict) -> None:
        return None

    def get_reply(self, key: str) -> dict | None:
        return None

    def put_reply(self, key: str, record: dict) -> None:
        return None


class FilePlanCache:
    def __init__(self, directory: Path | str = DEFAULT_CACHE_DIR) -> None:
        self.directory = Path(directory)

    def _path(self, key: str) -> Path:
        safe = "".join(c for c in key if c.isalnum() or c in ".-_")
        return self.directory / f"{safe}.json"

    def get(self, key: str) -> dict | None:
        path = self._path(key)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return PlanJSON.model_validate(raw).model_dump()
        except FileNotFoundError:
            return None
        except (OSError, ValueError, ValidationError) as e:
            logger.warning("plan cache entry %s is unreadable and was ignored: %s", path.name, e)
            return None

    def put(self, key: str, plan: dict) -> None:
        self._write(key, plan)

    def get_reply(self, key: str) -> dict | None:
        """A stored model reply: `{"reply": {...}, "input_tokens": ..., ...}`, or None."""
        path = self._path(key)
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as e:
            logger.warning("reply cache entry %s is unreadable and was ignored: %s", path.name, e)
            return None
        if isinstance(record, dict) and isinstance(record.get("reply"), dict):
            return record
        logger.warning("reply cache entry %s has no reply and was ignored", path.name)
        return None

    def put_reply(self, key: str, record: dict) -> None:
        self._write(key, record)

    def _write(self, key: str, content: dict) -> None:
        """Write atomically, so a reader never sees half a file. Failures are logged only."""
        tmp_name = ""
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(content, f, sort_keys=True)
            os.replace(tmp_name, self._path(key))
            tmp_name = ""
        except (OSError, TypeError, ValueError) as e:
            logger.warning("plan cache entry could not be written: %s", e)
        finally:
            if tmp_name:
                Path(tmp_name).unlink(missing_ok=True)


def default_plan_cache() -> PlanCache:
    from app.modules.parsing.settings import get_settings

    settings = get_settings()
    if settings.cache.strip().lower() in ("off", "0", "false", "no"):
        return NullPlanCache()
    return FilePlanCache(settings.cache_dir or DEFAULT_CACHE_DIR)
