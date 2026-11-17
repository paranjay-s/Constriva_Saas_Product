"""Loads the editable JSON files in ./data (catalog, rules, application rules, room aliases).

The files are plain JSON so the firm can edit them without touching code. They are read
once per process; call `reload()` after editing them while the server runs.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"


def _load(name: str) -> dict[str, Any]:
    with (DATA_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache
def catalog() -> list[dict[str, Any]]:
    return list(_load("material_catalog.json")["materials"])


@lru_cache
def catalog_by_id() -> dict[str, dict[str, Any]]:
    return {e["id"]: e for e in catalog()}


@lru_cache
def rules() -> dict[str, Any]:
    return _load("material_rules.json")


@lru_cache
def application_rules() -> dict[str, Any]:
    return _load("application_rules.json")


@lru_cache
def knowledge() -> dict[str, Any]:
    return _load("material_knowledge.json")


@lru_cache
def room_aliases() -> dict[str, list[str]]:
    return {k: v for k, v in _load("room_aliases.json").items() if not k.startswith("_")}


def reload() -> None:
    for f in (catalog, catalog_by_id, rules, application_rules, room_aliases, knowledge):
        f.cache_clear()
