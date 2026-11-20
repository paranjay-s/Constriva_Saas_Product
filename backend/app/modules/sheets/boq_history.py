"""Saved bills of quantities, per user (PART 3).

Every BOQ job that finishes is saved for its owner: the file name, a short summary for lists and
the whole result, so a bill can be opened again later without parsing the PDF again. A save that
fails (the table is not created yet, the database is down) is logged and never fails the BOQ
itself.

Store: BOQ_HISTORY_STORE = supabase (the `boq_history` table, migration 20261120_0001) or memory
(tests, local work before the migration is applied). Every read is by owner; another user's bill
answers 404.
"""

import logging
import os
import threading
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

logger = logging.getLogger("construtiva.sheets.boq_history")
TABLE = "boq_history"
MOST = 200  # bills listed per user, newest first


def _now() -> str:
    return datetime.now(UTC).isoformat()


def summary(result: dict[str, Any]) -> dict[str, Any]:
    """what a list shows of a bill: rows, rows in the quote, storeys, built-up area, warnings"""
    items = result.get("items") or []
    geo = result.get("geometry_summary") or {}
    area = next(
        (
            geo[k]
            for k in ("a_built_total_m2", "built_up_area_m2", "total_area_m2", "area_m2")
            if k in geo
        ),
        None,
    )
    levels = geo.get("levels_count", geo.get("levels"))
    return {
        "items": len(items),
        "in_quote": sum(
            1 for i in items if (i or {}).get("quote_status", "INCLUDED") == "INCLUDED"
        ),
        "levels": len(levels)
        if isinstance(levels, list)
        else levels
        if isinstance(levels, int)
        else None,
        "area_m2": round(float(area), 1) if isinstance(area, int | float) else None,
        "warnings": len(result.get("warnings") or []),
        "rooms": geo.get("rooms_count") if isinstance(geo.get("rooms_count"), int) else None,
    }


class HistoryStore(Protocol):
    def save(
        self, user_id: str, name: str, source: str, result: dict[str, Any]
    ) -> dict[str, Any]: ...

    def list_for_user(self, user_id: str) -> list[dict[str, Any]]: ...

    def get(self, user_id: str, bill_id: str) -> dict[str, Any] | None: ...

    def delete(self, user_id: str, bill_id: str) -> bool: ...


class MemoryHistoryStore:
    def __init__(self) -> None:
        self._rows: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def save(self, user_id, name, source, result):
        row = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "name": name[:200],
            "source": source,
            "summary": summary(result),
            "result": result,
            "created_at": _now(),
        }
        with self._lock:
            self._rows[row["id"]] = row
        return {k: v for k, v in row.items() if k != "result"}

    def list_for_user(self, user_id):
        with self._lock:
            rows = [
                {k: v for k, v in r.items() if k != "result"}
                for r in self._rows.values()
                if r["user_id"] == user_id
            ]
        return sorted(rows, key=lambda r: r["created_at"], reverse=True)[:MOST]

    def get(self, user_id, bill_id):
        with self._lock:
            row = self._rows.get(bill_id)
            return dict(row) if row and row["user_id"] == user_id else None

    def delete(self, user_id, bill_id):
        with self._lock:
            row = self._rows.get(bill_id)
            if not row or row["user_id"] != user_id:
                return False
            del self._rows[bill_id]
            return True


class SupabaseHistoryStore:
    LIST_COLUMNS = "id,user_id,name,source,summary,created_at"

    def _table(self):
        from app.core.supabase import get_supabase_client

        return get_supabase_client().table(TABLE)

    def save(self, user_id, name, source, result):
        row = {
            "user_id": user_id,
            "name": name[:200],
            "source": source,
            "summary": summary(result),
            "result": result,
        }
        data = self._table().insert(row).execute().data or [row]
        return {k: v for k, v in data[0].items() if k != "result"}

    def list_for_user(self, user_id):
        q = self._table().select(self.LIST_COLUMNS).eq("user_id", user_id)
        return q.order("created_at", desc=True).limit(MOST).execute().data or []

    def get(self, user_id, bill_id):
        res = self._table().select("*").eq("id", bill_id).eq("user_id", user_id).limit(1).execute()
        return res.data[0] if res.data else None

    def delete(self, user_id, bill_id):
        res = self._table().delete().eq("id", bill_id).eq("user_id", user_id).execute()
        return bool(res.data)


_store: HistoryStore | None = None


def get_history_store() -> HistoryStore:
    global _store
    if _store is None:
        kind = os.environ.get("BOQ_HISTORY_STORE") or (
            "memory" if os.environ.get("TESTING") else "supabase"
        )
        _store = MemoryHistoryStore() if kind == "memory" else SupabaseHistoryStore()
    return _store


def set_history_store(store: HistoryStore | None) -> None:
    global _store
    _store = store


def record(user_id: str, name: str, result: dict[str, Any], source: str = "upload") -> None:
    """save a finished bill for its owner; never raises"""
    try:
        get_history_store().save(user_id, name, source, result)
    except Exception:  # noqa: BLE001 - a missing table or a database error must not fail the BOQ
        logger.exception("The BOQ could not be saved to the history")
