"""Cache of normalised PlanJSON, keyed by the PDF's sha256 and the parser versions.

The same PDF always yields the same PlanJSON: the first parse is stored, and every later
upload of the same bytes reads it back instead of asking a model again. The key also holds
the parser, prompt and schema versions, so changing any of them starts a fresh entry
rather than serving JSON an older parser produced.

Entries live in the folder the blueprint import has always cached in
(`backend/.tmp/plan_cache`, git-ignored). Only the plan is stored: no project, user or
plan-row ids, so a cache hit can never hand one project another project's records.
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


def plan_cache_key(pdf_sha256: str, parser_version: str, prompt_version: str) -> str:
    return f"{pdf_sha256}.parser-{parser_version}.prompt-{prompt_version}.schema-{SCHEMA_VERSION}"


class PlanCache(Protocol):
    def get(self, key: str) -> dict | None: ...

    def put(self, key: str, plan: dict) -> None: ...


class NullPlanCache:
    """Caching switched off."""

    def get(self, key: str) -> dict | None:
        return None

    def put(self, key: str, plan: dict) -> None:
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
        """Write atomically, so a reader never sees half a file. Failures are logged only."""
        tmp_name = ""
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(plan, f, sort_keys=True)
            os.replace(tmp_name, self._path(key))
            tmp_name = ""
        except (OSError, TypeError, ValueError) as e:
            logger.warning("plan could not be cached: %s", e)
        finally:
            if tmp_name:
                Path(tmp_name).unlink(missing_ok=True)


def default_plan_cache() -> PlanCache:
    from app.modules.parsing.settings import get_settings

    settings = get_settings()
    if settings.cache.strip().lower() in ("off", "0", "false", "no"):
        return NullPlanCache()
    return FilePlanCache(settings.cache_dir or DEFAULT_CACHE_DIR)
