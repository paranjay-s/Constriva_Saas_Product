"""Material finder sessions in the existing tables (no new table, no migration).

    conversations  one row per session: conversation_type "material_finder", user_id,
                   project_id, title
    messages       the chat (role user / assistant, content). The newest message carries
                   the whole session state in metadata = {"kind": "material_state", ...}:
                   detected materials, the measured space, follow-up requests, the
                   latest report and an uploaded plan (kept here, never in `plans`).

With TESTING=1, MATERIAL_STORE=memory or no Supabase, sessions live in memory. A failed
database write never loses the session (memory copy, saved=false).
"""

import copy
import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from app.modules.ai.material_agent.calculator import Applied
from app.modules.ai.material_agent.schemas import (
    ApplicationRequest,
    ChatMessage,
    ImageAnalysis,
    Material,
    MaterialReport,
    Overrides,
    TargetSpace,
)
from app.modules.ai.material_agent.settings import get_settings

logger = logging.getLogger("construtiva.ai.material.store")

KIND = "material_state"
CONVERSATION_TYPES = ("material_finder", "material", "chat", "general")  # first one accepted
DEFAULT_PROJECT_ID = "00000000-0000-0000-0000-000000000001"


@dataclass
class Session:
    id: str
    owner_id: str
    project_id: str | None = None
    project_name: str | None = None
    focus: str = ""
    image_hashes: list[str] = field(default_factory=list)
    analysis: ImageAnalysis | None = None
    materials: list[Material] = field(default_factory=list)
    target: TargetSpace | None = None
    applied: list[Applied] = field(default_factory=list)
    overrides: Overrides = field(default_factory=Overrides)
    report: MaterialReport | None = None
    uploaded_plan: dict | None = None
    uploaded_plan_name: str | None = None
    pending: dict | None = None  # {"intent": {...}, "missing": "layout", "question", "options"}
    last_material_id: str | None = None  # the material talked about last ("this one")
    messages: list[ChatMessage] = field(default_factory=list)
    saved: bool = False
    # database bookkeeping
    stored_messages: int = 0
    last_message_row: str | None = None

    def say(
        self, role: str, text: str, status: str | None = None, options: list[str] | None = None
    ) -> None:
        self.messages.append(
            ChatMessage(role=role, text=text, status=status, options=options or [])
        )  # type: ignore[arg-type]

    def state(self) -> dict:
        return {
            "kind": KIND,
            "owner_user_id": self.owner_id,
            "project_name": self.project_name,
            "focus": self.focus,
            "image_hashes": self.image_hashes,
            "analysis": self.analysis.model_dump(mode="json") if self.analysis else None,
            "materials": [m.model_dump(mode="json") for m in self.materials],
            "target": self.target.model_dump(mode="json") if self.target else None,
            "applied": [
                {
                    "material_id": a.material_id,
                    "request": a.request.model_dump(mode="json"),
                    "target": a.target.model_dump(mode="json"),
                    "coverage": a.coverage,
                }
                for a in self.applied
            ],
            "overrides": self.overrides.model_dump(mode="json"),
            "report": self.report.model_dump(mode="json") if self.report else None,
            "uploaded_plan": self.uploaded_plan,
            "uploaded_plan_name": self.uploaded_plan_name,
            "pending": self.pending,
            "last_material_id": self.last_material_id,
        }

    @classmethod
    def from_state(
        cls, sid: str, project_id: str | None, state: dict, messages: list[ChatMessage]
    ) -> "Session":
        return cls(
            id=sid,
            owner_id=str(state.get("owner_user_id") or ""),
            project_id=project_id,
            project_name=state.get("project_name"),
            focus=state.get("focus") or "",
            image_hashes=list(state.get("image_hashes") or []),
            analysis=ImageAnalysis.model_validate(state["analysis"])
            if state.get("analysis")
            else None,
            materials=[Material.model_validate(m) for m in state.get("materials") or []],
            target=TargetSpace.model_validate(state["target"]) if state.get("target") else None,
            applied=[
                Applied(
                    material_id=a["material_id"],
                    request=ApplicationRequest.model_validate(a["request"]),
                    target=TargetSpace.model_validate(a["target"]),
                    coverage=float(a.get("coverage", 1.0)),
                )
                for a in state.get("applied") or []
            ],
            overrides=Overrides.model_validate(state.get("overrides") or {}),
            report=MaterialReport.model_validate(state["report"]) if state.get("report") else None,
            uploaded_plan=state.get("uploaded_plan"),
            uploaded_plan_name=state.get("uploaded_plan_name"),
            pending=state.get("pending"),
            last_material_id=state.get("last_material_id"),
            messages=messages,
            saved=True,
            stored_messages=len(messages),
        )


class SessionStore(Protocol):
    def create(self, s: Session) -> Session: ...
    def get(self, sid: str) -> Session | None: ...
    def update(self, s: Session) -> Session: ...


class MemorySessionStore:
    def __init__(self) -> None:
        self._items: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self, s: Session) -> Session:
        with self._lock:
            self._items[s.id] = copy.deepcopy(s)
        return s

    def get(self, sid: str) -> Session | None:
        with self._lock:
            s = self._items.get(sid)
            return copy.deepcopy(s) if s else None

    def update(self, s: Session) -> Session:
        return self.create(s)


class SupabaseSessionStore:
    def __init__(self) -> None:
        self._cache = MemorySessionStore()

    def _db(self):
        from app.core.supabase import get_supabase_client

        return get_supabase_client()

    def create(self, s: Session) -> Session:
        base = {"id": s.id, "user_id": s.owner_id, "title": (s.focus or "Material finder")[:120]}
        saved = False
        last_error: Exception | None = None
        for ctype in CONVERSATION_TYPES:
            for pid in [s.project_id] if s.project_id else [None, DEFAULT_PROJECT_ID]:
                try:
                    self._db().table("conversations").insert(
                        {**base, "conversation_type": ctype, "project_id": pid}
                    ).execute()
                    saved = True
                    break
                except Exception as e:  # check constraint / not-null: try the next value
                    last_error = e
            if saved:
                break
        if not saved:
            logger.warning("material session %s not saved: %s", s.id, last_error)
        s.saved = saved
        if saved:
            self._write_messages(s)
        return self._cache.create(s)

    def _write_messages(self, s: Session) -> None:
        try:
            new = s.messages[s.stored_messages :]
            if not new:
                if s.last_message_row:
                    self._db().table("messages").update({"metadata": s.state()}).eq(
                        "id", s.last_message_row
                    ).execute()
                    s.saved = True
                return  # nothing said yet: the state is written with the first reply
            for i, m in enumerate(new):
                row_id = str(uuid.uuid4())
                row = {
                    "id": row_id,
                    "conversation_id": s.id,
                    "role": m.role,
                    "content": m.text,
                    "metadata": s.state()
                    if i == len(new) - 1
                    else {"status": m.status, "options": m.options},
                }
                self._db().table("messages").insert(row).execute()
                s.last_message_row = row_id
            s.stored_messages = len(s.messages)
            s.saved = True
        except Exception as e:
            logger.warning("material session %s messages not saved: %s", s.id, e)
            s.saved = False

    def get(self, sid: str) -> Session | None:
        cached = self._cache.get(sid)
        if cached:
            return cached
        try:
            conv = (
                self._db()
                .table("conversations")
                .select("id,project_id")
                .eq("id", sid)
                .limit(1)
                .execute()
            )
            if not conv.data:
                return None
            rows = (
                self._db()
                .table("messages")
                .select("id,role,content,metadata,created_at")
                .eq("conversation_id", sid)
                .order("created_at")
                .execute()
            ).data or []
        except Exception as e:
            logger.warning("could not read material session %s: %s", sid, e)
            return None
        state_row = next(
            (r for r in reversed(rows) if (r.get("metadata") or {}).get("kind") == KIND), None
        )
        if state_row is None:
            return None
        msgs = []
        for r in rows:
            meta = r.get("metadata") or {}
            if r.get("role") in ("user", "assistant"):
                status = meta.get("status") if meta.get("kind") != KIND else None
                msgs.append(
                    ChatMessage(
                        role=r["role"],
                        text=r.get("content") or "",
                        status=status,
                        options=meta.get("options") or [],
                    )
                )
        pid = conv.data[0].get("project_id")
        s = Session.from_state(
            sid,
            str(pid) if pid and pid != DEFAULT_PROJECT_ID else None,
            state_row["metadata"],
            msgs,
        )
        s.last_message_row = str(state_row["id"])
        self._cache.create(s)
        return s

    def update(self, s: Session) -> Session:
        if s.saved or s.stored_messages:
            self._write_messages(s)
        return self._cache.update(s)


_store: SessionStore | None = None
_lock = threading.Lock()


def _use_memory() -> bool:
    if os.environ.get("TESTING") == "1" or get_settings().store.strip().lower() == "memory":
        return True
    from app.core.config import settings

    return not (settings.supabase_url and settings.supabase_service_role_key)


def get_store() -> SessionStore:
    global _store
    with _lock:
        if _store is None:
            _store = MemorySessionStore() if _use_memory() else SupabaseSessionStore()
            logger.info("material session store: %s", type(_store).__name__)
        return _store


def set_store(store: SessionStore | None) -> None:
    global _store
    with _lock:
        _store = store
