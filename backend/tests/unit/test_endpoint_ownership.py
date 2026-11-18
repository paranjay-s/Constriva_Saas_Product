"""The endpoints that used to be open: each needs a signed-in user, and the user's own data.

The plan drawing, the rasteriser, the upload limits and the material catalogue had no
authentication at all. They now use the app's one auth dependency, and the plan drawing
answers only its owner: a stranger gets the same 404 as for something that does not exist.
(The parsing progress stream and job image were removed with the old 2D-to-3D import.)
"""

import base64

import pymupdf
import pytest

from app.core.security import AuthenticatedUser, get_current_user
from app.main import app

OWNER = "test-architect-uuid-0001"  # the `client` fixture's user
STRANGER = "someone-else-uuid-0002"
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


@pytest.fixture
def db(fake_db):
    return fake_db(
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


def test_a_drawing_that_does_not_exist_is_a_404_not_another_plan(client, fake_db):
    fake_db()  # an empty database
    response = client.get("/api/v1/plans/44444444-4444-4444-4444-444444444444/download-png")
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
