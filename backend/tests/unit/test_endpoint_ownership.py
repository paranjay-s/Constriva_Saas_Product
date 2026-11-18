"""The endpoints that used to be open: each needs a signed-in user, and the user's own data.

The parsing progress stream, the job image, the plan drawing, the rasteriser, the upload
limits and the material catalogue had no authentication at all. They now use the app's
one auth dependency, and the three that return a user's data answer only its owner: a
stranger gets the same 404 as for something that does not exist.
"""

import base64
import json

import pymupdf
import pytest

from app.core.security import AuthenticatedUser, get_current_user
from app.main import app

OWNER = "test-architect-uuid-0001"  # the `client` fixture's user
STRANGER = "someone-else-uuid-0002"
JOB = "11111111-1111-4111-8111-111111111111"
OTHER_JOB = "22222222-2222-4222-8222-222222222222"
PROJECT = "33333333-3333-4333-8333-333333333333"
OTHER_PROJECT = "44444444-4444-4444-8444-444444444444"
PLAN = "55555555-5555-4555-8555-555555555555"
OTHER_PLAN = "66666666-6666-4666-8666-666666666666"
BARE_PLAN = "77777777-7777-4777-8777-777777777777"
PNG = b"\x89PNG\r\n\x1a\n" + b"drawing-bytes"

OPEN_BY_DESIGN = {
    ("GET", "/health"),
    ("GET", "/health/deep"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/signup"),
    ("POST", "/api/v1/auth/refresh"),
}


def job(job_id: str, user_id: str, **result) -> dict:
    return {
        "id": job_id,
        "user_id": user_id,
        "status": "done",
        "progress": 100,
        "step": "Finished",
        "result": {"plan_id": PLAN, **result},
    }


@pytest.fixture
def db(fake_db):
    return fake_db(
        jobs=[
            job(JOB, OWNER, preview_image_url="https://storage.test/mine.png"),
            job(OTHER_JOB, STRANGER, preview_image_url="https://storage.test/theirs.png"),
        ],
        projects=[
            {"id": PROJECT, "user_id": OWNER},
            {"id": OTHER_PROJECT, "user_id": STRANGER},
        ],
        plans=[
            {
                "id": PLAN,
                "name": "My Plan",
                "project_id": PROJECT,
                "generation_metadata": {"png_base64": base64.b64encode(PNG).decode()},
            },
            {
                "id": OTHER_PLAN,
                "name": "Their Plan",
                "project_id": OTHER_PROJECT,
                "generation_metadata": {"png_base64": base64.b64encode(PNG).decode()},
            },
            {"id": BARE_PLAN, "name": "No drawing", "project_id": PROJECT},
        ],
    )


def as_stranger() -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        user_id=STRANGER, email="other@example.com", metadata={}
    )


def test_only_health_ping_and_sign_in_are_open():
    open_operations = {
        (method.upper(), path)
        for path, item in app.openapi()["paths"].items()
        for method, operation in item.items()
        if not operation.get("security")
    }
    pings = {op for op in open_operations if op[1].endswith("/ping")}
    assert open_operations - pings == OPEN_BY_DESIGN


# ------------------------------------------------------------------ progress stream


def test_the_owner_can_follow_the_progress_stream(client, db):
    response = client.get(f"/api/v1/parsing/stream/{JOB}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    event, data = response.text.strip().split("\n")[:2]
    assert event == "event: complete"
    payload = json.loads(data.removeprefix("data: "))
    assert (payload["task_id"], payload["status"], payload["progress"]) == (JOB, "done", 100)


@pytest.mark.parametrize("task_id", [OTHER_JOB, "99999999-9999-4999-8999-999999999999", "nope"])
def test_someone_elses_or_an_unknown_job_stream_is_404(client, db, task_id):
    response = client.get(f"/api/v1/parsing/stream/{task_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Parsing job not found."
    assert "event:" not in response.text  # no stream was opened


def test_a_stranger_cannot_follow_my_job(client, db):
    as_stranger()
    assert client.get(f"/api/v1/parsing/stream/{JOB}").status_code == 404
    assert client.get(f"/api/v1/parsing/stream/{OTHER_JOB}").status_code == 200  # their own


# ------------------------------------------------------------------ job image


def test_the_owner_is_redirected_to_the_signed_image(client, db):
    response = client.get(f"/api/v1/parsing/job/{JOB}/image", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "https://storage.test/mine.png"


def test_someone_elses_job_image_is_404(client, db):
    response = client.get(f"/api/v1/parsing/job/{OTHER_JOB}/image", follow_redirects=False)
    assert response.status_code == 404 and "location" not in response.headers
    assert client.get("/api/v1/parsing/job/nope/image").status_code == 404


def test_a_job_image_is_signed_from_its_storage_key_for_the_owner_only(client, fake_db):
    fake_db(jobs=[job(JOB, OWNER, png_storage_key="rasters/p/a.png")])
    response = client.get(f"/api/v1/parsing/job/{JOB}/image", follow_redirects=False)
    assert (response.status_code, response.headers["location"]) == (
        307,
        "https://storage.test/p/a.png",
    )
    as_stranger()
    assert client.get(f"/api/v1/parsing/job/{JOB}/image", follow_redirects=False).status_code == 404


# ------------------------------------------------------------------ plan drawing


@pytest.mark.parametrize("route", ["/api/v1/plans/{}/download-png", "/api/v1/ai/plans/{}/png"])
def test_the_owner_downloads_the_plan_drawing(client, db, route):
    response = client.get(route.format(PLAN))
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png" and response.content == PNG
    assert response.headers["content-disposition"] == 'attachment; filename="My_Plan.png"'


@pytest.mark.parametrize("route", ["/api/v1/plans/{}/download-png", "/api/v1/ai/plans/{}/png"])
@pytest.mark.parametrize("plan_id", [OTHER_PLAN, BARE_PLAN, "nope"])
def test_someone_elses_missing_or_empty_plan_drawing_is_the_same_404(client, db, route, plan_id):
    response = client.get(route.format(plan_id))
    assert response.status_code == 404
    assert response.json()["detail"] == "This plan has no downloadable drawing."


def test_a_stranger_cannot_download_my_drawing(client, db):
    as_stranger()
    assert client.get(f"/api/v1/plans/{PLAN}/download-png").status_code == 404
    assert client.get(f"/api/v1/plans/{OTHER_PLAN}/download-png").status_code == 200


def test_ownership_is_not_granted_when_the_check_fails(client, db, monkeypatch):
    def broken():
        raise RuntimeError("database unreachable")

    monkeypatch.setattr("app.modules.projects.service.get_supabase_client", broken)
    assert client.get(f"/api/v1/plans/{PLAN}/download-png").status_code == 404


# ------------------------------------------------------------------ signed-in only


def small_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=200, height=120)
    page.insert_text((20, 60), "BEDROOM 12' X 14'")
    data = doc.tobytes()
    doc.close()
    return data


def test_the_rasteriser_needs_a_user_and_keeps_the_upload_limits(client):
    files = {"file": ("plan.pdf", small_pdf(), "application/pdf")}
    response = client.post("/api/v1/parsing/pdf-to-image?dpi=72", files=files)
    assert response.status_code == 200 and response.content.startswith(b"\x89PNG")
    not_pdf = {"file": ("plan.png", b"\x89PNG", "image/png")}
    assert client.post("/api/v1/parsing/pdf-to-image", files=not_pdf).status_code == 400


def test_limits_and_catalogue_answer_a_signed_in_user(client):
    assert client.get("/api/v1/parsing/upload-limits").json() == {
        "max_pdf_mb": 20.0,
        "max_pdf_pages": 10,
    }
    assert client.get("/api/v1/sheets/materials/catalogue").json()["count"] == 7


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", f"/api/v1/parsing/stream/{JOB}"),
        ("GET", f"/api/v1/parsing/job/{JOB}/image"),
        ("POST", "/api/v1/parsing/pdf-to-image"),
        ("GET", "/api/v1/parsing/upload-limits"),
        ("GET", f"/api/v1/plans/{PLAN}/download-png"),
        ("GET", f"/api/v1/ai/plans/{PLAN}/png"),
        ("GET", "/api/v1/sheets/materials/catalogue"),
    ],
)
def test_the_formerly_open_endpoints_refuse_a_request_without_a_token(
    unauthenticated_client, method, path
):
    assert unauthenticated_client.request(method, path).status_code == 401
