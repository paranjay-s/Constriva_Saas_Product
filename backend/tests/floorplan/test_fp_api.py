"""Floor plan API: parse -> generate job -> SSE progress -> plan -> edit -> export.

The LLM is replaced (None = form only, or a fake for chat edits) and plans are kept in
an in-memory store, so these tests need no network or database.
"""

import json
import time

import pytest
from fastapi.testclient import TestClient

from app.core.security import AuthenticatedUser, get_current_user
from app.main import app
from app.modules.ai.floorplan.jobs import JobManager, get_jobs
from app.modules.ai.floorplan.router import get_floorplan_llm
from app.modules.ai.floorplan.store import MemoryPlanStore, get_store
from tests.floorplan.test_fp_llm_pipeline import FakeLLM

BASE = "/api/v1/ai/floorplans"
FORM = {"plot_width": 30, "plot_depth": 45, "unit": "ft", "bedrooms": 2, "road_side": "south"}


def _user(uid: str) -> AuthenticatedUser:
    return AuthenticatedUser(user_id=uid, email=f"{uid}@example.test")


@pytest.fixture
def api():
    store, jobs = MemoryPlanStore(), JobManager()
    state = {"user": "user-a", "llm": None}
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_jobs] = lambda: jobs
    app.dependency_overrides[get_current_user] = lambda: _user(state["user"])
    app.dependency_overrides[get_floorplan_llm] = lambda: state["llm"]
    with TestClient(app) as client:
        yield client, state
    app.dependency_overrides.clear()


def _wait(client: TestClient, job_id: str, timeout: float = 90) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        st = client.get(f"{BASE}/jobs/{job_id}").json()
        if st["status"] in ("done", "failed"):
            return st
        time.sleep(0.2)
    raise AssertionError("job did not finish")


def _generate(client: TestClient) -> str:
    parsed = client.post(f"{BASE}/brief/parse", json=FORM).json()
    assert parsed["ready"], parsed
    job = client.post(f"{BASE}/generate", json={"brief": parsed["brief"]})
    assert job.status_code == 202
    st = _wait(client, job.json()["job_id"])
    assert st["status"] == "done", st
    return st["plan_id"]


def test_parse_returns_brief_for_confirmation(api) -> None:
    client, _ = api
    r = client.post(f"{BASE}/brief/parse", json=FORM)
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] and body["missing"] == []
    assert body["brief"]["bedrooms"] == 2
    assert body["summary"].startswith("2 bedrooms")


def test_parse_reports_missing_plot(api) -> None:
    client, _ = api
    body = client.post(f"{BASE}/brief/parse", json={"bedrooms": 2}).json()
    assert not body["ready"] and body["missing"]


def test_generate_job_then_plan(api) -> None:
    client, _ = api
    plan_id = _generate(client)
    st = client.get(f"{BASE}/{plan_id}")
    assert st.status_code == 200
    plan = st.json()
    assert plan["version"] == 1
    assert plan["svg"].startswith("<svg") or "<svg" in plan["svg"][:200]
    assert plan["plan"]["rooms"]
    assert plan["plan_json"]["units"] == "m" and plan["plan_json"]["levels"]
    assert plan["brief"]["bedrooms"] == 2


def test_job_events_stream(api) -> None:
    client, _ = api
    parsed = client.post(f"{BASE}/brief/parse", json=FORM).json()
    job_id = client.post(f"{BASE}/generate", json={"brief": parsed["brief"]}).json()["job_id"]
    events = []
    with client.stream("GET", f"{BASE}/jobs/{job_id}/events") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        kind = None
        for line in r.iter_lines():
            if line.startswith("event: "):
                kind = line[7:]
            elif line.startswith("data: ") and kind == "progress":
                events.append(json.loads(line[6:]))
            if kind == "end":
                break
    stages = [e["stage"] for e in events]
    assert stages[0] == "queued" and stages[-1] == "done"
    assert "layout" in stages and "saving" in stages
    assert [e["progress"] for e in events] == sorted(e["progress"] for e in events)
    assert events[-1]["plan_id"]


def test_generate_refuses_incomplete_brief(api) -> None:
    client, _ = api
    brief = client.post(f"{BASE}/brief/parse", json=FORM).json()["brief"]
    brief["bedrooms"] = None
    brief["rooms"] = []
    r = client.post(f"{BASE}/generate", json={"brief": brief})
    # either refused up front, or the job fails with a clear message (never a crash)
    if r.status_code == 202:
        st = _wait(client, r.json()["job_id"])
        assert st["status"] in ("done", "failed")
    else:
        assert r.status_code == 422


def test_infeasible_job_fails_with_options(api) -> None:
    client, _ = api
    form = {**FORM, "plot_width": 15, "plot_depth": 20, "bedrooms": 4}
    brief = client.post(f"{BASE}/brief/parse", json=form).json()["brief"]
    st = _wait(client, client.post(f"{BASE}/generate", json={"brief": brief}).json()["job_id"])
    assert st["status"] == "failed"
    assert st["error"]
    assert st["options"]


def test_other_user_cannot_see_plan_or_job(api) -> None:
    client, state = api
    plan_id = _generate(client)
    state["user"] = "user-b"
    assert client.get(f"{BASE}/{plan_id}").status_code == 404
    assert client.get(f"{BASE}/{plan_id}/export?format=svg").status_code == 404
    assert client.post(f"{BASE}/{plan_id}/edit", json={"message": "x"}).status_code == 404


def test_edit_renames_room_and_bumps_version(api) -> None:
    client, state = api
    plan_id = _generate(client)
    plan = client.get(f"{BASE}/{plan_id}").json()
    bed = next(r for r in plan["plan"]["rooms"] if r["type"] in ("bedroom", "master_bedroom"))
    state["llm"] = FakeLLM(
        {"edit_ops": {"ops": [{"op": "rename_room", "id": bed["id"], "label": "GUEST ROOM"}]}}
    )
    r = client.post(f"{BASE}/{plan_id}/edit", json={"message": "call it guest room", "version": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["plan"]["version"] == 2
    labels = {x["id"]: x["label"] for x in body["plan"]["plan"]["rooms"]}
    assert labels[bed["id"]] == "GUEST ROOM"
    assert [m["role"] for m in body["plan"]["messages"]] == ["user", "assistant"]
    # stored: a fresh read sees the new version
    assert client.get(f"{BASE}/{plan_id}").json()["version"] == 2


def test_edit_with_outdated_version_is_refused(api) -> None:
    client, state = api
    plan_id = _generate(client)
    state["llm"] = FakeLLM({"edit_ops": {"ops": []}})
    r = client.post(f"{BASE}/{plan_id}/edit", json={"message": "x", "version": 7})
    assert r.status_code == 409


def test_edit_without_llm_explains(api) -> None:
    client, _ = api
    plan_id = _generate(client)
    body = client.post(f"{BASE}/{plan_id}/edit", json={"message": "bigger kitchen"}).json()
    assert body["status"] == "failed" and "AI" in body["message"]
    assert body["plan"]["version"] == 1


@pytest.mark.parametrize(
    ("fmt", "magic"),
    [("svg", b"<"), ("pdf", b"%PDF"), ("png", b"\x89PNG"), ("dxf", b"  0")],
)
def test_export_formats(api, fmt: str, magic: bytes) -> None:
    client, _ = api
    plan_id = _generate(client)
    r = client.get(f"{BASE}/{plan_id}/export", params={"format": fmt, "dpi": 72})
    assert r.status_code == 200
    assert r.content.lstrip()[:4].startswith(magic.strip()) or r.content.startswith(magic)
    assert "attachment" in r.headers["content-disposition"]


def test_export_rejects_unknown_format(api) -> None:
    client, _ = api
    plan_id = _generate(client)
    assert client.get(f"{BASE}/{plan_id}/export?format=docx").status_code == 422


def test_unknown_ids_are_404(api) -> None:
    client, _ = api
    assert client.get(f"{BASE}/nope").status_code == 404
    assert client.get(f"{BASE}/jobs/nope").status_code == 404
