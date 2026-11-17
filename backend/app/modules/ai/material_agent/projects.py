"""The logged-in user's projects and their saved plans (read only).

Every lookup is filtered by the user's id: a project of another user is never found,
even by exact name or id. Plans are only read here; nothing in the material finder
writes to the `plans` table.
"""

import difflib
import logging
import re
from dataclasses import dataclass, field
from typing import Protocol

logger = logging.getLogger("construtiva.ai.material.projects")


@dataclass
class ProjectInfo:
    id: str
    name: str


class ProjectSource(Protocol):
    def list_projects(self, user_id: str) -> list[ProjectInfo]: ...
    def latest_plan(self, project_id: str) -> dict | None: ...


def _norm(s: str) -> str:
    s = re.sub(r"^(project|my project|the project)\s*[:\-]?\s*", "", s.strip().lower())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s)).strip()


@dataclass
class ProjectMatch:
    status: str  # ok, ambiguous, not_found
    project: ProjectInfo | None = None
    options: list[ProjectInfo] = field(default_factory=list)
    all_projects: list[ProjectInfo] = field(default_factory=list)


def find_project(source: ProjectSource, user_id: str, name: str) -> ProjectMatch:
    """Own projects only: exact name, then contains, then close spelling."""
    try:
        projects = source.list_projects(user_id)
    except Exception as e:  # database down: say so instead of guessing
        logger.warning("could not list projects: %s", e)
        projects = []
    q = _norm(name)
    if not q:
        return ProjectMatch(status="not_found", all_projects=projects)
    exact = [p for p in projects if _norm(p.name) == q]
    if len(exact) == 1:
        return ProjectMatch(status="ok", project=exact[0], all_projects=projects)
    candidates = exact or [
        p for p in projects if q in _norm(p.name) or (_norm(p.name) and _norm(p.name) in q)
    ]
    if not candidates:
        names = {_norm(p.name): p for p in projects}
        close = difflib.get_close_matches(q, list(names), n=3, cutoff=0.75)
        candidates = [names[c] for c in close]
    if len(candidates) == 1:
        return ProjectMatch(status="ok", project=candidates[0], all_projects=projects)
    if candidates:
        return ProjectMatch(status="ambiguous", options=candidates, all_projects=projects)
    return ProjectMatch(status="not_found", all_projects=projects)


def own_project(source: ProjectSource, user_id: str, project_id: str) -> ProjectInfo | None:
    try:
        return next((p for p in source.list_projects(user_id) if p.id == project_id), None)
    except Exception as e:
        logger.warning("could not list projects: %s", e)
        return None


# ------------------------------------------------------------- implementations


class MemoryProjectSource:
    """Tests and offline use."""

    def __init__(self) -> None:
        self.projects: dict[str, tuple[str, ProjectInfo]] = {}  # id -> (owner, info)
        self.plans: dict[str, dict] = {}  # project id -> plan_json

    def add(self, owner: str, project_id: str, name: str, plan_json: dict | None = None) -> None:
        self.projects[project_id] = (owner, ProjectInfo(id=project_id, name=name))
        if plan_json is not None:
            self.plans[project_id] = plan_json

    def list_projects(self, user_id: str) -> list[ProjectInfo]:
        return [p for owner, p in self.projects.values() if owner == user_id]

    def latest_plan(self, project_id: str) -> dict | None:
        return self.plans.get(project_id)


class SupabaseProjectSource:
    def _client(self):
        from app.core.supabase import get_supabase_client  # lazily: optional in tests

        return get_supabase_client()

    def list_projects(self, user_id: str) -> list[ProjectInfo]:
        res = (
            self._client()
            .table("projects")
            .select("id,name")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(200)
            .execute()
        )
        return [
            ProjectInfo(id=str(r["id"]), name=r.get("name") or "Untitled") for r in res.data or []
        ]

    def latest_plan(self, project_id: str) -> dict | None:
        res = (
            self._client()
            .table("plans")
            .select("plan_json,updated_at")
            .eq("project_id", project_id)
            .order("updated_at", desc=True)
            .limit(5)
            .execute()
        )
        for row in res.data or []:
            pj = row.get("plan_json")
            if isinstance(pj, dict) and pj.get("levels"):
                return pj
        return None
