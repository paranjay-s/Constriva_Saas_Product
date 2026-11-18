"""Who may call the API: a Supabase access token, or nothing.

A request without a token gets 401 on every protected endpoint. The one exception is demo
access, which is off unless AUTH_ALLOW_DEMO_USER is set, and then uses the dedicated demo
profile named by AUTH_DEMO_USER_ID: never another user's profile, never a created account.
"""

import inspect
import re
import time

import jwt
import pytest
from fastapi.security import HTTPAuthorizationCredentials

from app.core import security
from app.core.config import settings
from app.core.security import (
    NOT_SIGNED_IN,
    AuthConfigError,
    check_auth_settings,
    demo_user,
    get_current_user,
)
from app.main import app

DEMO_ID = "11111111-2222-4333-8444-555555555555"
ANY_ID = "00000000-0000-4000-8000-000000000000"
BEARER = [{"HTTPBearer": []}]


def protected_operations() -> list[tuple[str, str]]:
    """(METHOD, path with ids filled in) of every operation that declares Bearer auth."""
    found = []
    for path, item in app.openapi()["paths"].items():
        for method, operation in item.items():
            if operation.get("security") == BEARER:
                found.append((method.upper(), re.sub(r"\{[^}]+\}", ANY_ID, path)))
    return sorted(found)


PROTECTED = protected_operations()


@pytest.fixture
def demo_access(monkeypatch):
    monkeypatch.setattr(settings, "auth_allow_demo_user", True)
    monkeypatch.setattr(settings, "auth_demo_user_id", DEMO_ID)
    monkeypatch.setattr(settings, "auth_demo_user_email", "demo@example.com")


def test_there_are_protected_operations_to_check():
    assert len(PROTECTED) > 40
    paths = {path for _, path in PROTECTED}
    assert "/api/v1/projects" in paths and "/api/v1/sheets/boq" in paths
    assert "/api/v1/parsing/process" in paths


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_no_token_is_401_on_every_protected_endpoint(unauthenticated_client, method, path):
    response = unauthenticated_client.request(method, path)
    assert response.status_code == 401, (method, path, response.text[:200])
    assert response.json()["detail"] == NOT_SIGNED_IN
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("placeholder", ["null", "undefined", "string", "", "  "])
def test_a_placeholder_instead_of_a_token_is_401(unauthenticated_client, placeholder):
    response = unauthenticated_client.get(
        "/api/v1/projects", headers={"Authorization": f"Bearer {placeholder}"}
    )
    assert response.status_code == 401


@pytest.mark.parametrize("token", ["not-a-jwt", "aaa.bbb.ccc"])
def test_a_bad_token_is_401_even_with_demo_access_on(unauthenticated_client, demo_access, token):
    response = unauthenticated_client.get(
        "/api/v1/projects", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid session. Please sign in again."


def test_demo_access_is_off_by_default():
    assert settings.auth_allow_demo_user is False
    assert demo_user() is None
    check_auth_settings()  # nothing to complain about


def test_demo_access_uses_the_dedicated_profile_only(unauthenticated_client, demo_access):
    user = demo_user()
    assert (user.id, user.email, user.token) == (DEMO_ID, "demo@example.com", None)
    # a request without a token now acts as that profile: authenticated, so 404 not 401
    response = unauthenticated_client.get("/api/v1/sheets/boq/jobs/unknown-job")
    assert response.status_code == 404
    check_auth_settings()


@pytest.mark.parametrize("bad_id", ["", "not-a-uuid", "null"])
def test_demo_access_without_a_profile_fails_at_startup_and_grants_nothing(
    unauthenticated_client, monkeypatch, bad_id
):
    monkeypatch.setattr(settings, "auth_allow_demo_user", True)
    monkeypatch.setattr(settings, "auth_demo_user_id", bad_id)
    with pytest.raises(AuthConfigError, match="AUTH_DEMO_USER_ID"):
        check_auth_settings()
    assert demo_user() is None
    assert unauthenticated_client.get("/api/v1/projects").status_code == 401


async def test_a_valid_supabase_token_is_the_user(monkeypatch):
    secret = "unit-test-signing-secret-of-enough-length"
    monkeypatch.setattr(settings, "supabase_jwt_secret", secret)
    claims = {"sub": ANY_ID, "email": "a@example.com", "exp": int(time.time()) + 600}
    token = jwt.encode(claims, secret, algorithm="HS256")
    user = await get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    assert (user.id, user.email, user.token) == (ANY_ID, "a@example.com", token)

    expired = jwt.encode({**claims, "exp": int(time.time()) - 600}, secret, algorithm="HS256")
    forged = jwt.encode(claims, "another-secret-of-enough-length-000000", algorithm="HS256")
    for bad in (expired, forged):
        with pytest.raises(Exception) as refused:
            await get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=bad))
        assert getattr(refused.value, "status_code", None) == 401


def test_no_account_is_created_and_no_password_lives_in_the_code():
    source = inspect.getsource(security)
    for forbidden in ("create_user", "password", "Password", "limit(1)", "get_fallback_user"):
        assert forbidden not in source, forbidden
