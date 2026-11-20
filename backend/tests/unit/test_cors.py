"""The deployed frontend (another origin, on the internet) calls this API on the user's machine.

Every answer it may read must carry Access-Control-Allow-Origin, including preflights with
Chrome's private-network header and unexpected 500s; other sites must not be allowed.
"""

import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.core.config import Settings, browser_origins, cors_origin_regex
from app.main import create_app

VERCEL = "https://constriva-saas-product.vercel.app"


def preflight(client, origin, method="POST", private=False, headers="authorization,content-type"):
    extra = {"Access-Control-Request-Private-Network": "true"} if private else {}
    return client.options(
        "/api/v1/projects/",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": headers,
            **extra,
        },
    )


@pytest.fixture
def client():
    app = create_app()

    @app.get("/boom")
    async def boom():
        raise RuntimeError("unexpected")

    return TestClient(app, raise_server_exceptions=False)


def test_the_deployed_frontend_is_allowed_by_default():
    assert VERCEL in browser_origins(Settings(_env_file=None))


@pytest.mark.parametrize("origin", [VERCEL, "http://localhost:5173", "http://127.0.0.1:4173",
                                    "http://localhost:3000"])
def test_preflight_from_allowed_origins(client, origin):
    response = preflight(client, origin)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    allowed = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed and "content-type" in allowed


def test_private_network_preflight_is_allowed(client):
    # Chrome sends this when a public site (Vercel) calls an API on localhost
    response = preflight(client, VERCEL, private=True)
    assert response.status_code == 200
    assert response.headers["access-control-allow-private-network"] == "true"
    assert response.headers["access-control-allow-origin"] == VERCEL


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
def test_every_method_is_allowed(client, method):
    assert preflight(client, VERCEL, method=method).status_code == 200


def test_simple_request_carries_the_origin_and_exposes_headers(client):
    response = client.get("/health", headers={"Origin": VERCEL})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == VERCEL
    assert response.headers["access-control-expose-headers"] == "*"  # Content-Disposition


def test_errors_carry_cors_headers_too(client):
    # a 401 / 404 from a route and an unexpected exception: the browser must see the status
    for path in ("/api/v1/projects/", "/no-such-route"):
        response = client.get(path, headers={"Origin": VERCEL})
        assert response.status_code in (401, 403, 404)
        assert response.headers["access-control-allow-origin"] == VERCEL
    response = client.get("/boom", headers={"Origin": VERCEL})
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert response.headers["access-control-allow-origin"] == VERCEL


def test_unhandled_errors_still_raise_for_the_server_log():
    app = create_app()

    @app.get("/boom")
    async def boom():
        raise RuntimeError("unexpected")

    with pytest.raises(RuntimeError):
        TestClient(app).get("/boom")


@pytest.mark.parametrize("origin", ["https://evil.example.com", f"{VERCEL}.evil.com",
                                    "http://localhost.evil.com", "null"])
def test_other_sites_are_refused(client, origin):
    assert preflight(client, origin).status_code == 400
    response = client.get("/health", headers={"Origin": origin})
    assert "access-control-allow-origin" not in response.headers


def test_origins_are_trimmed_and_extendable(monkeypatch):
    s = Settings(_env_file=None, frontend_origin="https://app.example.com/",
                 cors_origins=f" {VERCEL}/ , https://other.example.com,,")
    assert browser_origins(s) == ["https://app.example.com", VERCEL, "https://other.example.com"]

    s = Settings(_env_file=None, cors_origin_regex=r"https://constriva-saas-product-[a-z0-9-]+\.vercel\.app")
    monkeypatch.setattr(config, "settings", s)
    import app.main as main

    monkeypatch.setattr(main, "browser_origins", lambda: browser_origins(s))
    monkeypatch.setattr(main, "cors_origin_regex", lambda: cors_origin_regex(s))
    preview = "https://constriva-saas-product-git-feat-pro-team.vercel.app"
    response = preflight(TestClient(main.create_app()), preview)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == preview
