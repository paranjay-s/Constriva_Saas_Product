"""Who owns which PlanTo3D job.

PlanTo3D knows nothing about users. This store maps each of its job ids to the user who
uploaded the plan and, optionally, to a project. Every request for a job is checked
against it, so one user can never reach another user's plan or house.
"""

import logging
import threading
from datetime import UTC, datetime
from typing import Any, Protocol

from app.modules.plan3d.models import TABLE
from app.modules.plan3d.settings import get_settings

logger = logging.getLogger("construtiva.plan3d.store")


def _now() -> str:
    return datetime.now(UTC).isoformat()


class JobStore(Protocol):
    def add(
        self, job_id: str, user_id: str, *, project_id: str | None, name: str, source: str
    ) -> dict[str, Any]: ...

    def get(self, job_id: str) -> dict[str, Any] | None: ...

    def list_for_user(
        self, user_id: str, project_id: str | None = None
    ) -> list[dict[str, Any]]: ...

    def set_quality(self, job_id: str, quality: str) -> None: ...

    def delete(self, job_id: str) -> None: ...


class MemoryJobStore:
    """Kept in this process only. For tests, and for local work before the table exists."""

    def __init__(self) -> None:
        self._rows: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def add(self, job_id, user_id, *, project_id, name, source):
        row = {
            "id": job_id,
            "user_id": user_id,
            "project_id": project_id,
            "name": name,
            "source": source,
            "quality": None,
            "created_at": _now(),
            "updated_at": _now(),
        }
        with self._lock:
            self._rows[job_id] = row
        return dict(row)

    def get(self, job_id):
        with self._lock:
            row = self._rows.get(job_id)
            return dict(row) if row else None

    def list_for_user(self, user_id, project_id=None):
        with self._lock:
            rows = [
                dict(r)
                for r in self._rows.values()
                if r["user_id"] == user_id and (project_id is None or r["project_id"] == project_id)
            ]
        return sorted(rows, key=lambda r: r["created_at"], reverse=True)

    def set_quality(self, job_id, quality):
        with self._lock:
            if job_id in self._rows:
                self._rows[job_id].update(quality=quality, updated_at=_now())

    def delete(self, job_id):
        with self._lock:
            self._rows.pop(job_id, None)


class SupabaseJobStore:
    """The `plan3d_jobs` table, through the service client. Every read is by id or by owner."""

    def _table(self):
        from app.core.supabase import get_supabase_client

        return get_supabase_client().table(TABLE)

    def add(self, job_id, user_id, *, project_id, name, source):
        row = {
            "id": job_id,
            "user_id": user_id,
            "project_id": project_id,
            "name": name,
            "source": source,
        }
        result = self._table().insert(row).execute()
        return (result.data or [row])[0]

    def get(self, job_id):
        result = self._table().select("*").eq("id", job_id).limit(1).execute()
        return result.data[0] if result.data else None

    def list_for_user(self, user_id, project_id=None):
        query = self._table().select("*").eq("user_id", user_id)
        if project_id is not None:
            query = query.eq("project_id", project_id)
        return query.order("created_at", desc=True).limit(100).execute().data or []

    def set_quality(self, job_id, quality):
        self._table().update({"quality": quality, "updated_at": _now()}).eq("id", job_id).execute()

    def delete(self, job_id):
        self._table().delete().eq("id", job_id).execute()


_store: JobStore | None = None


def get_job_store() -> JobStore:
    """The store the settings name (PLAN3D_STORE). One per process."""
    global _store
    if _store is None:
        if get_settings().store.strip().lower() == "memory":
            logger.warning(
                "PLAN3D_STORE=memory: 3D job ownership is lost when the server restarts."
            )
            _store = MemoryJobStore()
        else:
            _store = SupabaseJobStore()
    return _store
