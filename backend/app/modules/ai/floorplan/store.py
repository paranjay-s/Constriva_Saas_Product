"""Where generated floor plans are kept: the existing Supabase `plans` table (no migration).

One row per floor plan:
    plan_json            legacy PlanJSON in metres (3D viewer, BOQ sheets read this)
    generation_metadata  {"kind": "floorplan_v2", "floorplan": <FloorPlan, cm, the source of
                          truth>, "program", "brief", "notes", "messages", "version",
                          "owner_user_id"}
Every edit overwrites the row and bumps `version`.

With TESTING=1, FLOORPLAN_STORE=memory, or no Supabase configured, plans live in memory
(lost on restart). If a database write fails the plan stays usable from memory and the
API reports saved=false.
"""

import copy
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from app.modules.ai.floorplan.legacy_plan_json import to_legacy_plan_json
from app.modules.ai.floorplan.schemas.brief import Brief
from app.modules.ai.floorplan.schemas.plan import FloorPlan
from app.modules.ai.floorplan.schemas.program import RoomProgram
from app.modules.ai.floorplan.settings import get_settings

logger = logging.getLogger("construtiva.ai.floorplan.store")

KIND = "floorplan_v2"
DEFAULT_PROJECT_ID = "00000000-0000-0000-0000-000000000001"  # same default as the old page
MAX_MESSAGES = 200
MAX_HISTORY = 10  # earlier versions kept for "undo" / "go back to version N"


@dataclass
class StoredPlan:
    id: str
    owner_id: str
    name: str
    plan: FloorPlan
    project_id: str | None = None
    program: RoomProgram | None = None
    brief: Brief | None = None
    notes: list[str] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)
    # earlier versions, oldest first: {"version", "floorplan", "program", "change", "at"}
    history: list[dict] = field(default_factory=list)
    version: int = 1
    saved: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def metadata(self) -> dict:
        return {
            "kind": KIND,
            "owner_user_id": self.owner_id,
            "version": self.version,
            "floorplan": self.plan.model_dump(mode="json", by_alias=True),
            "program": self.program.model_dump(mode="json") if self.program else None,
            "brief": self.brief.model_dump(mode="json") if self.brief else None,
            "notes": self.notes,
            "messages": self.messages[-MAX_MESSAGES:],
            "history": self.history[-MAX_HISTORY:],
            "created_at": self.created_at,
            "updated_at": datetime.now(UTC).isoformat(),
        }

    @classmethod
    def from_row(cls, row: dict) -> "StoredPlan | None":
        meta = row.get("generation_metadata") or {}
        if meta.get("kind") != KIND or not meta.get("floorplan"):
            return None  # a plan from another feature (PDF parsing, old generator)
        return cls(
            id=str(row["id"]),
            owner_id=str(meta.get("owner_user_id") or ""),
            name=row.get("name") or "Floor plan",
            project_id=str(row["project_id"]) if row.get("project_id") else None,
            plan=FloorPlan.model_validate(meta["floorplan"]),
            program=RoomProgram.model_validate(meta["program"]) if meta.get("program") else None,
            brief=Brief.model_validate(meta["brief"]) if meta.get("brief") else None,
            notes=list(meta.get("notes") or []),
            messages=list(meta.get("messages") or []),
            history=list(meta.get("history") or []),
            version=int(meta.get("version") or 1),
            saved=True,
            created_at=meta.get("created_at") or "",
        )


class PlanStore(Protocol):
    def create(self, sp: StoredPlan) -> StoredPlan: ...
    def get(self, plan_id: str) -> StoredPlan | None: ...
    def update(self, sp: StoredPlan) -> StoredPlan: ...
    def list_for(self, owner_id: str, project_id: str | None = None) -> list[dict]: ...


def _summary_row(sp: StoredPlan) -> dict:
    return {
        "id": sp.id,
        "project_id": sp.project_id,
        "name": sp.name,
        "version": sp.version,
        "created_at": sp.created_at,
    }


class MemoryPlanStore:
    def __init__(self) -> None:
        self._plans: dict[str, StoredPlan] = {}
        self._lock = threading.Lock()

    def create(self, sp: StoredPlan) -> StoredPlan:
        with self._lock:
            self._plans[sp.id] = copy.deepcopy(sp)
        return sp

    def get(self, plan_id: str) -> StoredPlan | None:
        with self._lock:
            sp = self._plans.get(plan_id)
            return copy.deepcopy(sp) if sp else None

    def update(self, sp: StoredPlan) -> StoredPlan:
        return self.create(sp)

    def list_for(self, owner_id: str, project_id: str | None = None) -> list[dict]:
        with self._lock:
            plans = [
                sp
                for sp in self._plans.values()
                if sp.owner_id == owner_id and (project_id is None or sp.project_id == project_id)
            ]
        plans.sort(key=lambda sp: sp.created_at, reverse=True)
        return [_summary_row(sp) for sp in plans]


class SupabasePlanStore:
    """The `plans` table, with a memory copy so a failed write never loses the plan."""

    def __init__(self) -> None:
        self._cache = MemoryPlanStore()

    def _table(self):
        from app.core.supabase import get_supabase_client  # imported lazily: optional in tests

        return get_supabase_client().table("plans")

    def _row(self, sp: StoredPlan) -> dict:
        return {
            "name": sp.name,
            "plan_json": to_legacy_plan_json(sp.plan),
            "overall_confidence": 1.0,
            "status": "verified",
            "generation_metadata": sp.metadata(),
        }

    def create(self, sp: StoredPlan) -> StoredPlan:
        row = {
            "id": sp.id,
            "project_id": sp.project_id or DEFAULT_PROJECT_ID,
            "origin": "chat",
            **self._row(sp),
        }
        try:
            try:
                self._table().insert(row).execute()
            except Exception as e:  # the origin check constraint may not allow 'chat'
                if "plans_origin_check" not in str(e):
                    raise
                row["origin"] = "extracted"
                self._table().insert(row).execute()
            sp.saved = True
        except Exception as e:
            logger.warning("floor plan %s not saved to the database: %s", sp.id, e)
            sp.saved = False
        return self._cache.create(sp)

    def get(self, plan_id: str) -> StoredPlan | None:
        cached = self._cache.get(plan_id)
        if cached:
            return cached
        try:
            res = self._table().select("*").eq("id", plan_id).limit(1).execute()
        except Exception as e:
            logger.warning("could not read floor plan %s: %s", plan_id, e)
            return None
        rows = getattr(res, "data", None) or []
        sp = StoredPlan.from_row(rows[0]) if rows else None
        if sp:
            self._cache.create(sp)
        return sp

    def list_for(self, owner_id: str, project_id: str | None = None) -> list[dict]:
        """Summaries only (the full plan, history and chat stay in the database)."""
        query = (
            self._table()
            .select("id, name, project_id, created_at, version:generation_metadata->>version")
            .eq("generation_metadata->>kind", KIND)
            .eq("generation_metadata->>owner_user_id", owner_id)
        )
        if project_id:
            query = query.eq("project_id", project_id)
        res = query.order("created_at", desc=True).limit(200).execute()
        rows = getattr(res, "data", None) or []
        return [
            {
                "id": str(r["id"]),
                "project_id": str(r["project_id"]) if r.get("project_id") else None,
                "name": r.get("name") or "Floor plan",
                "version": int(r.get("version") or 1),
                "created_at": r.get("created_at") or "",
            }
            for r in rows
        ]

    def update(self, sp: StoredPlan) -> StoredPlan:
        try:
            self._table().update(self._row(sp)).eq("id", sp.id).execute()
            sp.saved = True
        except Exception as e:
            logger.warning("floor plan %s update not saved to the database: %s", sp.id, e)
            sp.saved = False
        return self._cache.update(sp)


_store: PlanStore | None = None
_store_lock = threading.Lock()


def _use_memory() -> bool:
    if os.environ.get("TESTING") == "1" or get_settings().store.strip().lower() == "memory":
        return True
    from app.core.config import settings

    return not (settings.supabase_url and settings.supabase_service_role_key)


def get_store() -> PlanStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = MemoryPlanStore() if _use_memory() else SupabasePlanStore()
            logger.info("floor plan store: %s", type(_store).__name__)
        return _store


def set_store(store: PlanStore | None) -> None:
    """Tests: replace the store (None = choose again on next use)."""
    global _store
    with _store_lock:
        _store = store
