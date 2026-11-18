"""No upload ends on an error (plan3d/fallback.py), and plans of our floor plan generator
skip detection. PlanTo3D is the fake of test_plan3d.py; the AI plan reader is replaced, so
no model is called."""

# ruff: noqa: F811  (the `planto3d` fixture is imported from test_plan3d and used by name)

import time

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.ai.floorplan.store import MemoryPlanStore, StoredPlan, set_store
from app.modules.parsing.errors import NoFloorPlanError
from app.modules.plan3d import fallback
from tests.unit.test_plan3d import API, OWNER, planto3d, small_pdf  # noqa: F401 (fixture)
from tests.unit.test_plan3d_convert import generator_plan, house

PLAN_ID = "5b1f0e7a-2c44-4d0b-9a61-7e3c2d9f4a10"


@pytest.fixture(autouse=True)
def fresh_fallback():
    """The fake numbers its jobs from 1 in every test: forget the jobs of the last one."""
    fallback._tried.clear()
    fallback._reading.clear()
    yield


@pytest.fixture
def client(mock_user):
    """One event loop for the whole test, so a reader started by one request keeps running."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def ai_reads(monkeypatch):
    """What the AI plan reader returns (a PlanJSON) or raises, and the PDFs it was given."""
    calls: list[bytes] = []
    outcome: dict = {"plan": house()}

    def reader(pdf: bytes) -> dict:
        calls.append(pdf)
        if "error" in outcome:
            raise outcome["error"]
        return outcome["plan"]

    app.dependency_overrides[fallback.get_ai_reader] = lambda: reader
    yield outcome, calls
    app.dependency_overrides.pop(fallback.get_ai_reader, None)


@pytest.fixture
def plans():
    store = MemoryPlanStore()
    set_store(store)
    yield store
    set_store(None)


def wait_for_review(client, job_id: str) -> dict:
    """Poll the job until a plan can be reviewed (or 5 s pass)."""
    deadline = time.monotonic() + 5
    while True:
        body = client.get(f"{API}/jobs/{job_id}").json()
        if body["stage"] != "detecting" or time.monotonic() > deadline:
            return body
        time.sleep(0.02)


def new_job(client) -> str:
    response = client.post(
        f"{API}/jobs", files={"file": ("scan.pdf", small_pdf(), "application/pdf")}
    )
    assert response.status_code == 201, response.text
    return response.json()["job_id"]


def test_when_the_detector_fails_the_ai_reader_reads_the_plan(client, planto3d, ai_reads):
    planto3d.detector_fails = True
    job_id = new_job(client)
    first = client.get(f"{API}/jobs/{job_id}").json()
    assert first["stage"] in ("detecting", "detected")  # never the detector's "failed"
    body = wait_for_review(client, job_id)
    assert body["stage"] == "detected" and body["reader"] == "ai"
    assert body["notice"].startswith(fallback.AI_NOTICE)
    (imported,) = planto3d.imports
    assert imported["reader"] == "ai" and imported["job"] == job_id
    plan = imported["plan"]
    assert plan["units"] == "ft" and len(plan["floors"][0]["walls"]) >= 4
    _, calls = ai_reads
    assert calls == [b"file:/jobs/" + job_id.encode() + b"/source.pdf"]  # the job's own PDF


def test_while_the_ai_reader_works_the_job_reads_as_being_read(client, planto3d, monkeypatch):
    planto3d.detector_fails = True
    job_id = new_job(client)
    monkeypatch.setitem(fallback._reading, job_id, fallback.READING_MESSAGE)
    fallback._tried.add(job_id)
    body = client.get(f"{API}/jobs/{job_id}").json()
    assert body["stage"] == "detecting" and body["message"] == fallback.READING_MESSAGE
    fallback.forget(job_id)


def test_when_the_ai_reader_fails_too_the_plan_is_opened_for_tracing(client, planto3d, ai_reads):
    outcome, _ = ai_reads
    outcome["error"] = NoFloorPlanError("No floor plan was found on any page.")
    planto3d.detector_fails = True
    job_id = new_job(client)
    body = wait_for_review(client, job_id)
    assert body["stage"] == "detected" and body["reader"] == "trace"
    assert "No floor plan was found" in body["notice"] and "Trace the walls" in body["notice"]
    assert planto3d.imports[0]["plan"] is None


def test_an_implausible_ai_plan_is_opened_for_tracing_with_what_was_read(
    client, planto3d, ai_reads
):
    outcome, _ = ai_reads
    tiny = house()
    tiny["levels"][0]["walls"] = tiny["levels"][0]["walls"][:2]  # no closed outline
    tiny["levels"][0]["openings"] = []
    outcome["plan"] = tiny
    planto3d.detector_fails = True
    job_id = new_job(client)
    body = wait_for_review(client, job_id)
    assert body["reader"] == "trace"
    assert planto3d.imports[0]["reader"] == "trace" and planto3d.imports[0]["plan"] is not None


def test_a_plan_the_detector_read_is_left_alone(client, planto3d, ai_reads):
    job_id = new_job(client)
    body = client.get(f"{API}/jobs/{job_id}").json()
    assert body["stage"] == "detected" and body["reader"] == "detector"
    assert planto3d.imports == [] and ai_reads[1] == []


def test_the_readers_are_tried_once_per_job(client, planto3d, ai_reads):
    outcome, calls = ai_reads
    outcome["error"] = NoFloorPlanError("nothing")
    planto3d.detector_fails = True
    job_id = new_job(client)
    wait_for_review(client, job_id)
    planto3d.jobs[job_id].update(stage="failed", reader="", floors=[])  # as if PlanTo3D lost it
    for _ in range(3):
        client.get(f"{API}/jobs/{job_id}")
    assert len(calls) == 1


def stored(store: MemoryPlanStore, owner: str) -> bytes:
    """A generated plan saved for `owner`, and the PDF its export menu gives."""
    from app.modules.ai.floorplan.render.exports import export_plan

    floor_plan, _ = generator_plan()
    floor_plan = floor_plan.model_copy(update={"id": PLAN_ID})
    store.create(StoredPlan(id=PLAN_ID, owner_id=owner, name="Villa", plan=floor_plan, version=3))
    return export_plan(floor_plan, "pdf", version=3).data


def test_a_pdf_of_the_owners_generated_plan_uses_the_stored_plan(client, planto3d, plans):
    pdf = stored(plans, OWNER)
    response = client.post(f"{API}/jobs", files={"file": ("villa.pdf", pdf, "application/pdf")})
    assert response.status_code == 201, response.text
    job_id = response.json()["job_id"]
    upload = next(r for r in planto3d.requests if r.url.path == "/api/upload")
    assert upload.headers["x-detect"] == "0"  # no detection
    (imported,) = planto3d.imports
    assert imported["reader"] == "stored" and '"Villa" (version 3)' in imported["notice"]
    assert imported["plan"]["floors"][0]["walls"]
    assert client.get(f"{API}/jobs/{job_id}").json()["reader"] == "stored"


def test_someone_elses_generated_plan_is_read_from_the_drawing(client, planto3d, plans):
    pdf = stored(plans, "someone-else-uuid-0002")
    response = client.post(f"{API}/jobs", files={"file": ("villa.pdf", pdf, "application/pdf")})
    assert response.status_code == 201
    upload = next(r for r in planto3d.requests if r.url.path == "/api/upload")
    assert "x-detect" not in upload.headers and planto3d.imports == []


def test_open_in_3d_from_the_floor_plan_generator(client, planto3d, plans):
    stored(plans, OWNER)
    response = client.post(f"{API}/jobs/from-floorplan", json={"plan_id": PLAN_ID})
    assert response.status_code == 201, response.text
    job = client.get(f"{API}/jobs/{response.json()['job_id']}").json()
    assert job["reader"] == "stored" and job["source"] == "floorplan" and job["name"] == "Villa.pdf"
    upload = next(r for r in planto3d.requests if r.url.path == "/api/upload")
    assert upload.headers["x-detect"] == "0" and upload.content.startswith(b"%PDF")


def test_open_in_3d_needs_the_users_own_plan(client, planto3d, plans):
    stored(plans, "someone-else-uuid-0002")
    for plan_id in (PLAN_ID, "not-a-plan"):
        response = client.post(f"{API}/jobs/from-floorplan", json={"plan_id": plan_id})
        assert response.status_code == 404
    assert not any(r.url.path == "/api/upload" for r in planto3d.requests)
