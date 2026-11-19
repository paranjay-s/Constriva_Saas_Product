"""The 3D gateway (/api/v1/3d) in front of the private PlanTo3D service.

PlanTo3D is replaced by a fake that answers like its server.py, so these tests show what
the gateway itself adds: sign-in, ownership, the upload limits, our quality names, the
signed tokens of embedded pages, and exactly which requests a token may make.
"""

import json
import time

import httpx
import pymupdf
import pytest

from app.core.config import settings as app_settings
from app.core.security import AuthenticatedUser, get_current_user
from app.core.signed_token import TokenError, sign, verify
from app.main import app
from app.modules.plan3d import service
from app.modules.plan3d.client import Plan3dClient, get_plan3d_client
from app.modules.plan3d.settings import embed_secret, get_settings
from app.modules.plan3d.store import MemoryJobStore, get_job_store

API = "/api/v1/3d"
OWNER = "test-architect-uuid-0001"  # the `client` fixture's user
PROJECT = "33333333-3333-4333-8333-333333333333"
OTHER_PROJECT = "44444444-4444-4444-8444-444444444444"


def small_pdf(pages: int = 1) -> bytes:
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page(width=200, height=120).insert_text((20, 60), "BEDROOM 12' X 14'")
    data = doc.tobytes()
    doc.close()
    return data


class FakePlanTo3D:
    """Answers like PlanTo3D's server.py, and records every request it receives."""

    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}
        self.requests: list[httpx.Request] = []
        self.bodies: list[bytes] = []
        self.ready = True
        self.down = False
        self.detector_fails = False  # its detector gives up on every PDF
        self.imports: list[dict] = []  # bodies of POST /api/jobs/{id}/import

    def handler(self, request: httpx.Request) -> httpx.Response:
        """The answer with its body still unread, as it comes from a real server."""
        if self.down:
            raise httpx.ConnectError("connection refused")
        answer = self.answer(request)
        return httpx.Response(
            answer.status_code, headers=answer.headers, stream=httpx.ByteStream(answer.content)
        )

    def answer(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.bodies.append(request.read())
        path, method = request.url.path, request.method
        if path == "/api/system":
            ok = {"ok": self.ready}
            return httpx.Response(
                200,
                json={
                    "ready": self.ready,
                    "blender": {**ok, "version": "5.3"},
                    "pdf_tools": ok,
                    "viewer": ok,
                    "materials": ok,
                },
            )
        if path == "/examples/sample_plan.pdf":
            return httpx.Response(
                200, content=small_pdf(), headers={"content-type": "application/pdf"}
            )
        if path == "/api/upload" and method == "POST":
            job_id = f"{len(self.jobs) + 1:012x}"
            name = request.headers.get("x-filename")
            if request.headers.get("x-detect") == "0":
                self.jobs[job_id] = {"name": name, "stage": "uploaded"}
            elif self.detector_fails:
                self.jobs[job_id] = {"name": name, "stage": "failed", "message": "no vector lines"}
            else:
                self.jobs[job_id] = {"name": name, "stage": "detected", "reader": "detector"}
            return httpx.Response(200, json={"id": job_id})
        parts = path.strip("/").split("/")
        if parts[:2] == ["api", "jobs"] and len(parts) >= 3:
            job = self.jobs.get(parts[2])
            if job is None:
                return httpx.Response(404, json={"error": "no such job"})
            if len(parts) == 3 and method == "GET":
                return httpx.Response(200, json=job)
            if len(parts) == 3 and method == "DELETE":
                if job["stage"] in ("queued", "building"):
                    return httpx.Response(409, json={"error": "This plan is being built."})
                del self.jobs[parts[2]]
                return httpx.Response(200, json={"ok": True})
            if parts[3] == "build":
                quality = json.loads(self.bodies[-1])["quality"]
                job.update(stage="queued", progress=0, quality=quality, queue_position=2)
                return httpx.Response(200, json={"ok": True})
            if parts[3] == "plan":
                job["plan"] = json.loads(self.bodies[-1])
                return httpx.Response(200, json={"ok": True})
            if parts[3] == "import":
                body = json.loads(self.bodies[-1])
                self.imports.append({"job": parts[2], **body})
                job.update(stage="detected", reader=body["reader"], notice=body.get("notice", ""))
                job["floors"] = [f["name"] for f in (body.get("plan") or {}).get("floors", [])] or [
                    "Ground Floor"
                ]
                return httpx.Response(200, json={"ok": True})
            if parts[3] == "export":
                return httpx.Response(200, json={"url": f"/jobs/{parts[2]}/house_blender.zip"})
            if parts[3] == "tour":
                quality = json.loads(self.bodies[-1])["quality"]
                if job.get("stage") != "done":
                    return httpx.Response(409, json={"error": "build the house first"})
                job.update(stage="queued", progress=0, asked_tour=quality)
                return httpx.Response(200, json={"ok": True})
        if path.startswith(("/web/", "/three/", "/jobs/", "/thumbs/")):
            kind = (
                "text/html; charset=utf-8" if path.endswith(".html") else "application/octet-stream"
            )
            return httpx.Response(
                200,
                content=f"file:{path}".encode(),
                headers={"content-type": kind, "cache-control": "no-cache", "server": "PlanTo3D/1"},
            )
        if path == "/api/furniture":
            return httpx.Response(200, json={"rendering": False, "items": []})
        if path.startswith("/api/furniture/") or path == "/api/mp4":
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404, json={"error": "not found"})


@pytest.fixture
def planto3d():
    fake = FakePlanTo3D()
    http = httpx.AsyncClient(
        base_url="http://planto3d.test", transport=httpx.MockTransport(fake.handler)
    )
    store = MemoryJobStore()
    app.dependency_overrides[get_plan3d_client] = lambda: Plan3dClient(http)
    app.dependency_overrides[get_job_store] = lambda: store
    fake.store = store
    yield fake
    app.dependency_overrides.pop(get_plan3d_client, None)
    app.dependency_overrides.pop(get_job_store, None)


@pytest.fixture
def projects(monkeypatch):
    owned = {(PROJECT, OWNER)}
    monkeypatch.setattr(
        "app.modules.plan3d.router.user_owns_project",
        lambda project_id, user_id: (project_id, user_id) in owned,
    )


def as_stranger() -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        user_id="someone-else-uuid-0002", email="other@example.com", metadata={}
    )


def upload(client, name: str = "house.pdf", data: bytes | None = None, **form) -> str:
    response = client.post(
        f"{API}/jobs", files={"file": (name, data or small_pdf(), "application/pdf")}, data=form
    )
    assert response.status_code == 201, response.text
    return response.json()["job_id"]


def embed(client, job_id: str) -> dict:
    response = client.post(f"{API}/jobs/{job_id}/embed")
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------------------ signed tokens


def test_signed_token_round_trip_and_refusals():
    secret = b"a-secret-for-tests"
    token = sign({"sub": "u1", "job": "abc"}, audience="x", secret=secret, ttl_s=60, now=1000)
    claims = verify(token, audience="x", secret=secret, now=1059)
    assert (claims["sub"], claims["job"], claims["exp"]) == ("u1", "abc", 1060)

    payload, signature = token.split(".")
    for bad, now in (
        (token, 1060),  # expired
        (f"{payload}.{signature[:-2]}AA", 1000),  # forged signature
        (f"{payload[:-2]}AA.{signature}", 1000),  # altered claims
        ("not-a-token", 1000),
        ("", 1000),
    ):
        with pytest.raises(TokenError):
            verify(bad, audience="x", secret=secret, now=now)
    with pytest.raises(TokenError):  # issued for another purpose
        verify(token, audience="y", secret=secret, now=1000)
    with pytest.raises(TokenError):  # signed with another secret
        verify(token, audience="x", secret=b"another", now=1000)
    with pytest.raises(ValueError):
        sign({}, audience="x", secret=b"", ttl_s=60)


# ------------------------------------------------------------------ sign-in and ownership


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/system"),
        ("POST", "/jobs"),
        ("POST", "/jobs/sample"),
        ("POST", "/jobs/from-floorplan"),
        ("GET", "/jobs"),
        ("GET", "/jobs/000000000001"),
        ("POST", "/jobs/000000000001/build"),
        ("POST", "/jobs/000000000001/export"),
        ("POST", "/jobs/000000000001/embed"),
        ("POST", "/embed"),
        ("DELETE", "/jobs/000000000001"),
    ],
)
def test_every_gateway_endpoint_needs_a_signed_in_user(unauthenticated_client, method, path):
    assert unauthenticated_client.request(method, API + path).status_code == 401
    bad = unauthenticated_client.request(
        method, API + path, headers={"Authorization": "Bearer aaa.bbb.ccc"}
    )
    assert bad.status_code == 401


def test_upload_starts_a_job_that_belongs_to_the_user(client, planto3d, projects):
    job_id = upload(client, "My House.pdf", project_id=PROJECT)
    sent = next(r for r in planto3d.requests if r.url.path == "/api/upload")
    assert sent.headers["x-filename"] == "My%20House.pdf"
    assert planto3d.bodies[planto3d.requests.index(sent)].startswith(b"%PDF")
    row = planto3d.store.get(job_id)
    assert (row["user_id"], row["project_id"], row["name"], row["source"]) == (
        OWNER,
        PROJECT,
        "My House.pdf",
        "upload",
    )
    status = client.get(f"{API}/jobs/{job_id}").json()
    assert (status["job_id"], status["stage"], status["name"]) == (
        job_id,
        "detected",
        "My House.pdf",
    )
    assert [job["job_id"] for job in client.get(f"{API}/jobs").json()] == [job_id]


def test_a_stranger_cannot_see_use_or_delete_my_job(client, planto3d):
    job_id = upload(client)
    before = len(planto3d.requests)
    as_stranger()
    assert client.get(f"{API}/jobs").json() == []
    for method, path, body in (
        ("GET", f"/jobs/{job_id}", None),
        ("POST", f"/jobs/{job_id}/build", {"quality": "low"}),
        ("POST", f"/jobs/{job_id}/export", None),
        ("POST", f"/jobs/{job_id}/embed", None),
        ("DELETE", f"/jobs/{job_id}", None),
    ):
        response = client.request(method, API + path, json=body)
        assert response.status_code == 404, (method, path)
        assert response.json()["detail"] == "3D job not found."
    assert len(planto3d.requests) == before  # nothing reached PlanTo3D
    assert job_id in planto3d.jobs


@pytest.mark.parametrize("job_id", ["nope", "00000000000g", "../../etc", "0" * 13])
def test_a_malformed_job_id_never_reaches_planto3d(client, planto3d, job_id):
    assert client.get(f"{API}/jobs/{job_id}").status_code == 404
    assert planto3d.requests == []


def test_a_project_must_be_the_users_own(client, planto3d, projects):
    for bad in (OTHER_PROJECT, "not-a-uuid"):
        response = client.post(
            f"{API}/jobs",
            files={"file": ("p.pdf", small_pdf(), "application/pdf")},
            data={"project_id": bad},
        )
        assert response.status_code == 404 and response.json()["detail"] == "Project not found."
    assert planto3d.jobs == {}
    assert client.get(f"{API}/jobs", params={"project_id": OTHER_PROJECT}).status_code == 404


def test_jobs_are_listed_by_project(client, planto3d, projects):
    in_project = upload(client, "a.pdf", project_id=PROJECT)
    loose = upload(client, "b.pdf")
    listed = client.get(f"{API}/jobs", params={"project_id": PROJECT}).json()
    assert [job["job_id"] for job in listed] == [in_project]
    assert {job["job_id"] for job in client.get(f"{API}/jobs").json()} == {in_project, loose}


# ------------------------------------------------------------------ upload limits


def test_the_plan_upload_limits_apply_before_planto3d_is_called(client, planto3d, monkeypatch):
    from app.modules.parsing import settings as parser_settings

    def refused(name: str, data: bytes) -> httpx.Response:
        return client.post(f"{API}/jobs", files={"file": (name, data, "application/pdf")})

    assert refused("plan.png", b"\x89PNG").status_code == 400
    assert refused("plan.pdf", b"").status_code == 400
    assert refused("plan.pdf", b"not a pdf at all").status_code == 400
    assert refused("plan.pdf", small_pdf(pages=11)).status_code == 400  # 10 pages at most

    limits = parser_settings.get_settings()
    monkeypatch.setattr(limits, "max_pdf_mb", 0.001)
    too_big = refused("plan.pdf", small_pdf() + b"%" * 4096)
    assert too_big.status_code == 413
    assert planto3d.requests == []


def test_the_sample_plan_starts_a_job(client, planto3d):
    response = client.post(f"{API}/jobs/sample")
    assert response.status_code == 201
    row = planto3d.store.get(response.json()["job_id"])
    assert (row["name"], row["source"], row["user_id"]) == ("sample_plan.pdf", "sample", OWNER)
    assert [r.url.path for r in planto3d.requests] == ["/examples/sample_plan.pdf", "/api/upload"]


def test_a_job_nobody_owns_is_taken_off_the_builder(client, planto3d, monkeypatch):
    def broken(*_args, **_kwargs):
        raise RuntimeError("database unreachable")

    monkeypatch.setattr(planto3d.store, "add", broken)
    response = client.post(f"{API}/jobs", files={"file": ("p.pdf", small_pdf(), "application/pdf")})
    assert response.status_code == 503
    assert planto3d.jobs == {}  # uploaded, then deleted again


# ------------------------------------------------------------------ qualities and builds


def test_system_names_our_three_qualities(client, planto3d):
    body = client.get(f"{API}/system").json()
    assert (body["reachable"], body["ready"]) == (True, True)
    assert body["checks"]["blender"] == {"ok": True, "version": "5.3"}
    assert [(q["id"], q["label"], q["available"]) for q in body["qualities"]] == [
        ("low", "Low", True),
        ("medium", "Medium", True),
        ("high", "High", False),
    ]
    assert "cinema video tour" in body["qualities"][2]["reason"]
    assert [q["coming_soon"] for q in body["qualities"]] == [False, False, True]

    planto3d.ready = False
    body = client.get(f"{API}/system").json()
    assert body["ready"] is False and not any(q["available"] for q in body["qualities"])

    planto3d.down = True
    body = client.get(f"{API}/system").json()
    assert (body["reachable"], body["ready"]) == (False, False)
    assert "not running" in body["detail"]


@pytest.mark.parametrize(("ours", "theirs"), [("low", "draft"), ("medium", "high")])
def test_build_maps_our_quality_names_to_planto3ds(client, planto3d, ours, theirs):
    job_id = upload(client)
    response = client.post(f"{API}/jobs/{job_id}/build", json={"quality": ours})
    assert response.status_code == 200, response.text
    sent = [r for r in planto3d.requests if r.url.path.endswith("/build")]
    sent_body = json.loads(planto3d.bodies[planto3d.requests.index(sent[0])])
    # the owner's own furniture models go with the build (a set name, never the user id)
    assert sent_body == {"quality": theirs, "furniture_set": service.furniture_set(OWNER)}
    assert OWNER not in json.dumps(sent_body)
    body = response.json()
    assert (body["stage"], body["quality"], body["queue_position"]) == ("queued", ours, 2)
    assert planto3d.store.get(job_id)["quality"] == ours

    planto3d.jobs[job_id].update(stage="building", progress=40, eta_left=75, queue_position=None)
    body = client.get(f"{API}/jobs/{job_id}").json()
    assert (body["stage"], body["progress"], body["eta_left"], body["quality"]) == (
        "building",
        40,
        75,
        ours,
    )
    planto3d.jobs[job_id].update(stage="done", progress=100, build_seconds=58)
    body = client.get(f"{API}/jobs/{job_id}").json()
    assert (body["stage"], body["quality"], body["build_seconds"]) == ("done", ours, 58)


def test_the_cinema_tour_is_named_but_cannot_be_built_yet(client, planto3d):
    job_id = upload(client)
    response = client.post(f"{API}/jobs/{job_id}/build", json={"quality": "high"})
    assert response.status_code == 501 and "cinema video tour" in response.json()["detail"]
    assert not any(r.url.path.endswith("/build") for r in planto3d.requests)
    assert client.post(f"{API}/jobs/{job_id}/build", json={"quality": "ultra"}).status_code == 422


def test_planto3d_errors_and_outages_are_passed_on_plainly(client, planto3d):
    job_id = upload(client)
    client.post(f"{API}/jobs/{job_id}/build", json={"quality": "low"})
    busy = client.delete(f"{API}/jobs/{job_id}")
    assert busy.status_code == 409 and busy.json()["detail"] == "This plan is being built."
    assert planto3d.store.get(job_id) is not None  # still the user's

    planto3d.jobs[job_id]["stage"] = "done"
    assert client.delete(f"{API}/jobs/{job_id}").status_code == 204
    assert planto3d.store.get(job_id) is None and job_id not in planto3d.jobs

    gone = upload(client)
    del planto3d.jobs[gone]
    body = client.get(f"{API}/jobs/{gone}").json()
    assert body["stage"] == "failed" and "upload it again" in body["message"]

    planto3d.down = True
    outage = client.post(f"{API}/jobs", files={"file": ("p.pdf", small_pdf(), "application/pdf")})
    assert outage.status_code == 503 and "not running" in outage.json()["detail"]


def test_export_names_the_file_to_download(client, planto3d):
    job_id = upload(client)
    assert client.post(f"{API}/jobs/{job_id}/export").json() == {"file": "house_blender.zip"}


# ------------------------------------------------------------------ embedded pages


def test_embed_urls_carry_a_token_for_this_user_and_job(client, planto3d):
    job_id = upload(client)
    access = embed(client, job_id)
    base = access["base_url"]
    assert base.startswith(f"{API}/embed/") and access["expires_in"] == 3600
    assert access["review_url"] == f"{base}/web/edit.html?job={job_id}&embed"
    assert access["walkthrough_url"] == f"{base}/web/view.html?job={job_id}&embed"
    assert access["furniture_url"] == f"{base}/web/furniture.html?embed"
    assert access["files_url"] == f"{base}/jobs/{job_id}"
    claims = service.embed_claims(base.rsplit("/", 1)[-1])
    assert (claims["sub"], claims["job"]) == (OWNER, job_id)

    furniture_only = client.post(f"{API}/embed").json()
    assert furniture_only["review_url"] is None and furniture_only["files_url"] is None
    assert "job" not in service.embed_claims(furniture_only["base_url"].rsplit("/", 1)[-1])


def test_embedded_pages_need_no_bearer_token_only_the_signed_one(client, planto3d):
    job_id = upload(client)
    access = embed(client, job_id)
    app.dependency_overrides.pop(get_current_user)  # from here on, nobody is signed in
    assert client.get(f"{API}/jobs/{job_id}").status_code == 401
    page = client.get(access["walkthrough_url"])
    assert page.status_code == 200 and page.text == "file:/web/view.html"
    assert page.headers["content-type"].startswith("text/html")
    forwarded = planto3d.requests[-1]
    assert forwarded.url.path == "/web/view.html"
    assert forwarded.url.query == f"job={job_id}&embed".encode()
    assert "authorization" not in forwarded.headers


def test_embedded_responses_are_framed_only_by_our_frontend_and_leak_nothing(client, planto3d):
    access = embed(client, upload(client))
    page = client.get(access["review_url"])
    policy = page.headers["content-security-policy"]
    assert policy.startswith("frame-ancestors 'self' ") and app_settings.frontend_origin in policy
    assert page.headers["referrer-policy"] == "no-referrer"
    assert page.headers["x-content-type-options"] == "nosniff"
    assert page.headers["cache-control"] == "private, no-cache"
    assert "PlanTo3D" not in page.headers.get("server", "")  # only chosen headers pass
    assert "access-control-allow-origin" not in page.headers


def test_a_bad_or_expired_token_is_refused_before_planto3d(client, planto3d):
    job_id = upload(client)
    token = embed(client, job_id)["base_url"].rsplit("/", 1)[-1]
    before = len(planto3d.requests)
    expired = sign(
        {"sub": OWNER, "job": job_id},
        audience=service.EMBED_AUDIENCE,
        secret=embed_secret(),
        ttl_s=60,
        now=time.time() - 120,
    )
    other_purpose = sign(
        {"sub": OWNER, "job": job_id}, audience="sse", secret=embed_secret(), ttl_s=60
    )
    forged = sign(
        {"sub": OWNER, "job": job_id}, audience=service.EMBED_AUDIENCE, secret=b"x", ttl_s=60
    )
    for bad in (expired, other_purpose, forged, token[:-3] + "AAA", "nonsense"):
        response = client.get(f"{API}/embed/{bad}/web/view.html")
        assert response.status_code == 401, bad[:20]
        assert response.json()["detail"] == "This link has expired. Please reload the page."
    assert len(planto3d.requests) == before


def test_a_token_reaches_its_own_job_and_nothing_else(client, planto3d, monkeypatch):
    monkeypatch.setattr(get_settings(), "allow_furniture_changes", True)  # (off by default)
    mine = upload(client, "mine.pdf")
    other = upload(client, "other.pdf")
    base = embed(client, mine)["base_url"]

    allowed = [
        ("GET", "web/edit.html"),
        ("GET", "web/edit.js"),
        ("GET", "web/view.html"),
        ("GET", "web/view.js"),
        ("GET", "web/walk.js"),
        ("GET", "web/style.css"),
        ("GET", "web/furniture.html"),
        ("GET", "three/build/three.module.js"),
        ("GET", "three/examples/jsm/libs/draco/draco_decoder.wasm"),
        ("GET", f"jobs/{mine}/house.glb"),
        ("GET", f"jobs/{mine}/meta.json"),
        ("GET", f"jobs/{mine}/page-1.png"),
        ("GET", f"jobs/{mine}/house_blender.zip"),
        ("GET", f"api/jobs/{mine}"),
        ("GET", "api/system"),
        ("GET", "api/furniture"),
        ("GET", "thumbs/sofa.png"),
        ("POST", f"api/jobs/{mine}/plan"),
        ("POST", f"api/jobs/{mine}/export"),
        ("POST", "api/mp4"),
        ("POST", "api/furniture/sofa"),
        ("DELETE", "api/furniture/sofa"),
    ]
    for method, path in allowed:
        body = b'{"floors": [{}]}' if method == "POST" and not path.endswith("/export") else None
        response = client.request(method, f"{base}/{path}", content=body)
        assert response.status_code == 200, (method, path, response.text[:80])

    before = len(planto3d.requests)
    refused = [
        ("GET", "web/index.html"),  # the upload page: our own page replaces it
        ("GET", "index.html"),
        ("GET", "api/jobs"),  # everybody's plans
        ("GET", f"jobs/{other}/house.glb"),  # another job, even the same user's
        ("GET", f"api/jobs/{other}"),
        ("GET", f"jobs/{mine}/build.log"),
        ("GET", f"jobs/{mine}"),
        ("GET", "examples/sample_plan.pdf"),
        ("GET", "server.py"),
        ("GET", "three"),
        ("GET", "thumbs/sofa.glb"),
        ("GET", f"jobs/{mine}/../{other}/house.glb"),
        ("GET", f"jobs/{mine}/%2e%2e/{other}/house.glb"),
        ("POST", "api/upload"),
        ("POST", "api/materials"),
        ("POST", f"api/jobs/{mine}/build"),  # builds go through the signed-in API
        ("POST", f"api/jobs/{other}/plan"),
        ("DELETE", f"api/jobs/{mine}"),
        ("DELETE", f"api/jobs/{other}"),
    ]
    for method, path in refused:
        response = client.request(
            method, f"{base}/{path}", content=b"{}" if method == "POST" else None
        )
        assert response.status_code == 404, (method, path, response.status_code)
    assert len(planto3d.requests) == before  # none of them reached PlanTo3D
    assert client.put(f"{base}/web/view.html").status_code == 405


def test_the_zip_download_is_an_attachment(client, planto3d):
    job_id = upload(client)
    response = client.get(f"{embed(client, job_id)['base_url']}/jobs/{job_id}/house_blender.zip")
    assert response.headers["content-disposition"] == 'attachment; filename="house-blender.zip"'


def test_request_bodies_are_forwarded_whole_and_limited(client, planto3d, monkeypatch):
    job_id = upload(client)
    base = embed(client, job_id)["base_url"]
    plan = json.dumps({"floors": [{"name": "Ground"}], "furnish": False}).encode()
    saved = client.post(f"{base}/api/jobs/{job_id}/plan", content=plan)
    assert saved.status_code == 200
    assert planto3d.jobs[job_id]["plan"] == {"floors": [{"name": "Ground"}], "furnish": False}
    forwarded = planto3d.requests[-1]
    assert forwarded.headers["content-length"] == str(len(plan))
    assert "transfer-encoding" not in forwarded.headers  # PlanTo3D reads Content-Length bytes

    monkeypatch.setattr(service, "MAX_PLAN_BYTES", 16)
    before = len(planto3d.requests)
    assert client.post(f"{base}/api/jobs/{job_id}/plan", content=plan).status_code == 413
    assert len(planto3d.requests) == before


def test_furniture_changes_can_be_switched_off(client, planto3d, monkeypatch):
    base = embed(client, upload(client))["base_url"]
    monkeypatch.setattr(get_settings(), "allow_furniture_changes", False)
    assert client.get(f"{base}/api/furniture").status_code == 200  # looking is still fine
    assert client.post(f"{base}/api/furniture/sofa", content=b"glTF").status_code == 404
    assert client.delete(f"{base}/api/furniture/sofa").status_code == 404


def test_a_furniture_only_token_reaches_no_job(client, planto3d):
    job_id = upload(client)
    base = client.post(f"{API}/embed").json()["base_url"]
    assert client.get(f"{base}/web/furniture.html").status_code == 200
    assert client.get(f"{base}/api/furniture").status_code == 200
    assert client.get(f"{base}/jobs/{job_id}/house.glb").status_code == 404
    assert client.get(f"{base}/api/jobs/{job_id}").status_code == 404
    assert client.post(f"{base}/api/jobs/{job_id}/plan", content=b"{}").status_code == 404


def test_planto3d_being_down_is_a_503_for_embedded_pages_too(client, planto3d):
    base = embed(client, upload(client))["base_url"]
    planto3d.down = True
    response = client.get(f"{base}/web/view.html")
    assert response.status_code == 503 and "not running" in response.json()["detail"]


def test_frame_ancestors_lists_only_configured_origins(monkeypatch):
    monkeypatch.setattr(app_settings, "frontend_origin", "https://app.example.com")
    monkeypatch.setattr(get_settings(), "frame_ancestors", "https://admin.example.com/, ")
    assert service.frame_ancestors() == "'self' https://app.example.com https://admin.example.com"
    monkeypatch.setattr(app_settings, "frontend_origin", "http://localhost:5173")
    monkeypatch.setattr(get_settings(), "frame_ancestors", "")
    assert service.frame_ancestors() == (
        "'self' http://localhost:5173 http://localhost:* http://127.0.0.1:*"
    )


def test_the_page_proxy_is_the_only_gateway_route_without_bearer_auth():
    from app.modules.plan3d.router import router

    open_routes = sorted(
        route.path
        for route in router.routes
        if not any(d.call is get_current_user for d in route.dependant.dependencies)
    )
    assert open_routes == ["/embed/{token}/{path:path}"]
    assert len(router.routes) == 16  # + POST /creator (admins only)


def test_embed_tokens_are_redacted_from_logs_and_responses_are_private(client, planto3d):
    import logging

    from app.modules.plan3d.router import RedactEmbedTokens

    job_id = upload(client)
    base = embed(client, job_id)["base_url"]
    r = client.get(f"{base}/web/edit.html")
    assert r.headers["cache-control"].startswith("private")
    assert r.headers["referrer-policy"] == "no-referrer"
    token = base.rsplit("/", 1)[-1]
    rec = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        '%s - "%s %s"',
        ("1.2.3.4", "GET", f"{base}/web/edit.html"),
        None,
    )
    RedactEmbedTokens().filter(rec)
    assert (
        token not in rec.getMessage()
        and "/api/v1/3d/embed/<redacted>/web/edit.html" in rec.getMessage()
    )


def test_furniture_requests_go_to_the_persons_own_set():
    mine, theirs = service.furniture_set("user-a"), service.furniture_set("user-b")
    assert len(mine) == 16 and mine != theirs and mine == service.furniture_set("user-a")
    # a page cannot name a set: whatever it sends is replaced by the person's own
    assert service.furniture_route("api/furniture", f"set={theirs}&x=1", mine) == (
        "api/furniture",
        f"x=1&set={mine}",
    )
    assert service.furniture_route("api/furniture/sofa", "", mine) == (
        "api/furniture/sofa",
        f"set={mine}",
    )
    assert service.furniture_route("thumbs/sofa.png", "", mine) == (f"thumbs/{mine}/sofa.png", "")
    assert service.furniture_route("web/view.js", "job=1", mine) == ("web/view.js", "job=1")


def test_a_video_tour_of_a_built_house(client, planto3d):
    job_id = upload(client)
    # not built yet: PlanTo3D refuses and the person is told why
    early = client.post(f"{API}/jobs/{job_id}/tour", json={"quality": "high"})
    assert early.status_code == 409, early.text
    planto3d.jobs[job_id].update(stage="done", quality="high", progress=100)
    r = client.post(f"{API}/jobs/{job_id}/tour", json={"quality": "ultra"})
    assert r.status_code == 200, r.text
    assert r.json()["stage"] == "queued" and planto3d.jobs[job_id]["asked_tour"] == "ultra"
    assert client.post(f"{API}/jobs/{job_id}/tour", json={"quality": "cinema"}).status_code == 422
    # a finished tour is listed with the job
    planto3d.jobs[job_id].update(
        stage="done", tours={"ultra": {"file": "tour_ultra.mp4", "seconds": 600}}
    )
    body = client.get(f"{API}/jobs/{job_id}").json()
    assert body["tours"] == {"ultra": {"file": "tour_ultra.mp4", "seconds": 600}}
