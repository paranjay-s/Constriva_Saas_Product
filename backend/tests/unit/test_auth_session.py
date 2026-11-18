"""Regression tests for the "RLS error one hour after sign-in" incident.

Cause: sign-in ran on the shared admin Supabase client, which supabase-py then switched to
the user's token for every later database call; and expired / unverified tokens were
accepted and sent on to the database.
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException

from app.core import security
from app.core import supabase as sb


@pytest.fixture
def es256(monkeypatch):
    """A local ES256 key pair standing in for Supabase's signing key."""
    private = ec.generate_private_key(ec.SECP256R1())

    class FakeJwks:
        def get_signing_key_from_jwt(self, token):
            return type("K", (), {"key": private.public_key()})()

    monkeypatch.setattr(security, "_jwks", lambda: FakeJwks())
    security._verified.clear()

    def make(exp_in: int, sub: str = "user-1", iat_in: int = 0) -> str:
        now = int(time.time())
        claims = {
            "sub": sub,
            "email": "a@example.test",
            "exp": now + exp_in,
            "iat": now + iat_in,
            "role": "authenticated",
        }
        return jwt.encode(claims, private, algorithm="ES256")

    return make


def test_valid_token_is_accepted_and_cached(es256):
    token = es256(3600)
    user = security.verify_token(token)
    assert user.id == "user-1" and user.token == token
    assert token in security._verified


def test_expired_token_is_rejected_with_a_clear_401(es256):
    with pytest.raises(HTTPException) as e:
        security.verify_token(es256(-120))  # beyond the 60 s clock leeway
    assert e.value.status_code == 401 and "expired" in e.value.detail


def test_forged_token_is_rejected(es256):
    other = ec.generate_private_key(ec.SECP256R1())
    forged = jwt.encode(
        {"sub": "attacker", "exp": int(time.time()) + 3600}, other, algorithm="ES256"
    )
    with pytest.raises(HTTPException) as e:
        security.verify_token(forged)
    assert e.value.status_code == 401


def test_unsigned_token_is_rejected(es256):
    none_alg = jwt.encode({"sub": "x", "exp": int(time.time()) + 3600}, key=None, algorithm="none")
    with pytest.raises(HTTPException) as e:
        security.verify_token(none_alg)
    assert e.value.status_code == 401


def test_admin_client_never_keeps_a_user_session(monkeypatch):
    """Simulates supabase-py switching the shared client after a sign-in."""
    monkeypatch.setattr(sb.settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(sb.settings, "supabase_service_role_key", "sb_secret_test_key")
    monkeypatch.setattr(sb, "_supabase_client", None)
    first = sb.get_supabase_client()
    service_header = first.options.headers.get("Authorization")
    first.options.headers["Authorization"] = "Bearer some-user-access-token"  # what sign-in does
    second = sb.get_supabase_client()
    assert second is not first
    assert second.options.headers.get("Authorization") == service_header
    assert first is not sb.new_auth_client()  # sign-in gets its own client
    monkeypatch.setattr(sb, "_supabase_client", None)


def test_auth_router_never_signs_in_on_the_admin_client():
    import importlib
    import inspect

    src = inspect.getsource(importlib.import_module("app.modules.auth.router"))
    assert "supabase.auth.sign_in" not in src and "supabase.auth.refresh" not in src
    assert src.count("new_auth_client().auth.sign_in_with_password") >= 2


def test_token_from_a_clock_slightly_ahead_is_accepted(es256):
    """Supabase's clock was 2 s ahead of this server: a fresh token must still be valid."""
    assert security.verify_token(es256(3600, iat_in=5)).id == "user-1"
