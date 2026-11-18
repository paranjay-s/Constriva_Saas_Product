"""
=============================================================================
Construtiva Security & Authentication Middleware
=============================================================================
File: app/core/security.py
Purpose:
  Provides JWT verification for Supabase Auth tokens.
  Defines the `get_current_user` dependency for FastAPI routes to protect
  authenticated endpoints and retrieve user ID and email.
  Supports both symmetric (HS256) and asymmetric (RS256/ES256) Supabase tokens.
=============================================================================
"""

import uuid
import time
import logging
from typing import Optional, Dict, Any
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings
from app.core.supabase import get_supabase_client

logger = logging.getLogger("construtiva.security")

# HTTP Bearer token extractor
security_bearer = HTTPBearer(auto_error=False)

NOT_SIGNED_IN = "You are not signed in. Please sign in and try again."


def clean_uuid(value: Optional[str]) -> Optional[str]:
    """
    Cleanses and validates an optional UUID string.
    Returns None if value is None, empty, whitespace, or Swagger UI placeholder 'string'.

    Args:
        value (Optional[str]): Input string to validate.

    Returns:
        Optional[str]: Canonical UUID string if valid, else None.
    """
    if not value:
        return None
    val = str(value).strip()
    if val.lower() in ("", "string", "null", "undefined", "none"):
        return None
    try:
        return str(uuid.UUID(val))
    except (ValueError, AttributeError):
        return None


def resolve_project_uuid(value: Optional[str]) -> str:
    """
    Guarantees a 100% valid, canonical UUID string from any input:
    - If value is already a canonical UUID, returns it.
    - If value is a non-UUID slug (e.g. 'proj_s74wd6t' or user-generated tag),
      generates a deterministic, reproducible UUIDv5.
    - If value is None, empty, or placeholder ('null', 'undefined', 'string'),
      generates a fresh UUIDv4.
    PostgreSQL will NEVER receive 'null' or non-UUID syntax (code 22P02).
    """
    cleaned = clean_uuid(value)
    if cleaned:
        return cleaned
    val = str(value or "").strip()
    if val and val.lower() not in ("", "string", "null", "undefined", "none"):
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"project:{val}"))
    return str(uuid.uuid4())


class AuthenticatedUser:
    """
    Represents an authenticated user extracted from the Supabase JWT.
    """

    def __init__(
        self,
        user_id: str,
        email: str,
        metadata: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
    ):
        self.id = user_id
        self.email = email
        self.metadata = metadata or {}
        self.token = token

    def __repr__(self) -> str:
        return f"<AuthenticatedUser id={self.id} email={self.email}>"


class AuthConfigError(RuntimeError):
    """The demo-access settings are inconsistent. The message names the variable."""


def check_auth_settings() -> None:
    """Fail at startup when demo access is switched on without a demo profile.

    Raises AuthConfigError naming the variable to fix.
    """
    if not settings.auth_allow_demo_user:
        return
    if clean_uuid(settings.auth_demo_user_id) is None:
        raise AuthConfigError(
            "AUTH_ALLOW_DEMO_USER is true, so AUTH_DEMO_USER_ID must be the UUID of the "
            "dedicated demo profile. Set it, or turn AUTH_ALLOW_DEMO_USER off."
        )
    logger.warning(
        "Demo access is ON (AUTH_ALLOW_DEMO_USER): requests without a token act as the demo "
        "profile. Do not use this with real customer data."
    )


def demo_user() -> Optional[AuthenticatedUser]:
    """The dedicated demo profile, or None when demo access is off (the default).

    The profile is one an operator created for demos and named in AUTH_DEMO_USER_ID.
    Nothing is created here, and no other user's profile is ever borrowed.
    """
    if not settings.auth_allow_demo_user:
        return None
    user_id = clean_uuid(settings.auth_demo_user_id)
    if user_id is None:
        return None
    return AuthenticatedUser(
        user_id=user_id,
        email=settings.auth_demo_user_email,
        metadata={"full_name": "Demo user", "demo": True},
    )


# ---------------------------------------------------------------- token checks

SESSION_EXPIRED = "Your session has expired. Please sign in again."
CLOCK_LEEWAY_S = 60  # server clocks differ by a few seconds; a fresh token is not "from the future"
_jwks_client = None
_verified: dict[str, tuple[float, "AuthenticatedUser"]] = {}  # token -> (exp, user)
_VERIFIED_MAX = 2000


def _jwks():
    """Supabase's public signing keys (ES256 / RS256 projects), cached by PyJWT."""
    global _jwks_client
    if _jwks_client is None:
        url = settings.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
        _jwks_client = jwt.PyJWKClient(url, cache_keys=True, lifespan=3600, timeout=10)
    return _jwks_client


def _user_from_claims(claims: Dict[str, Any], token: str) -> "AuthenticatedUser":
    return AuthenticatedUser(
        user_id=str(claims["sub"]),
        email=claims.get("email", "") or "",
        metadata=claims.get("user_metadata", {}) or {},
        token=token,
    )


def _verify_locally(token: str) -> Optional[Dict[str, Any]]:
    """Verified claims (signature + expiry), or None if no key is available to check it.

    Raises jwt.ExpiredSignatureError for an expired token and jwt.InvalidTokenError for a
    forged or broken one.
    """
    alg = jwt.get_unverified_header(token).get("alg", "")
    options = {"verify_aud": False, "require": ["exp", "sub"]}
    if alg.startswith("HS"):
        if not settings.supabase_jwt_secret:
            return None
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=[alg],
            options=options,
            leeway=CLOCK_LEEWAY_S,
        )
    if alg.startswith(("ES", "RS", "PS", "Ed")):
        try:
            key = _jwks().get_signing_key_from_jwt(token)
        except jwt.PyJWKClientError as e:  # keys unreachable: let Supabase check it
            logger.warning(f"Could not load Supabase signing keys: {e}")
            return None
        return jwt.decode(token, key.key, algorithms=[alg], options=options, leeway=CLOCK_LEEWAY_S)
    raise jwt.InvalidTokenError(f"unsupported token algorithm {alg!r}")


def _verify_with_supabase(token: str) -> "AuthenticatedUser":
    """Ask Supabase Auth (used only when the token cannot be checked locally)."""
    try:
        res = get_supabase_client().auth.get_user(token)  # reads the token; no session is stored
    except Exception as e:
        text = str(e).lower()
        if "expired" in text:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, SESSION_EXPIRED) from e
        if any(w in text for w in ("invalid", "jwt", "401", "403", "bad_jwt", "not found")):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "Invalid session. Please sign in again."
            ) from e
        logger.error(f"Supabase Auth unreachable while checking a token: {e}")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Sign-in service is not reachable right now. Please try again in a moment.",
        ) from e
    if not res or not res.user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session. Please sign in again.")
    return AuthenticatedUser(
        user_id=str(res.user.id),
        email=res.user.email or "",
        metadata=res.user.user_metadata or {},
        token=token,
    )


def verify_token(token: str) -> "AuthenticatedUser":
    """The user of a Supabase access token, or HTTP 401 (expired / invalid).

    Verified locally (signature and expiry) whenever possible, so it is fast and does not
    depend on the network; a verified token is remembered until it expires. An expired or
    forged token is NEVER accepted (it used to be, which sent expired tokens to the
    database and surfaced as row-level security errors an hour after signing in).
    """
    now = time.time()
    hit = _verified.get(token)
    if hit and hit[0] > now + 5:
        return hit[1]
    try:
        claims = _verify_locally(token)
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, SESSION_EXPIRED) from e
    except jwt.InvalidTokenError as e:
        logger.info(f"Rejected an invalid token: {e}")
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid session. Please sign in again."
        ) from e
    if claims is not None:
        user = _user_from_claims(claims, token)
        if len(_verified) > _VERIFIED_MAX:
            for t in [t for t, (exp, _) in _verified.items() if exp <= now]:
                del _verified[t]
            if len(_verified) > _VERIFIED_MAX:
                _verified.clear()
        _verified[token] = (float(claims["exp"]), user)
        return user
    return _verify_with_supabase(token)


def bearer_token(credentials: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    """The token of an Authorization header, or None when the request carries none.

    The words "null" and "undefined" are what a browser sends when the page has no session;
    "string" is Swagger UI's placeholder. None of them is a token.
    """
    if not credentials or not credentials.credentials:
        return None
    token = credentials.credentials.strip()
    return None if token.lower() in ("", "string", "null", "undefined") else token


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> AuthenticatedUser:
    """
    FastAPI dependency: the signed-in user from the Bearer token.

    No token -> HTTP 401. (Only when demo access is switched on with AUTH_ALLOW_DEMO_USER,
    off by default, does such a request act as the dedicated demo profile.)
    A token that is expired, forged or unreadable -> HTTP 401, so the frontend can refresh
    the session or ask the person to sign in again.
    """
    token = bearer_token(credentials)
    if token is None:
        demo = demo_user()
        if demo is not None:
            return demo
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            NOT_SIGNED_IN,
            headers={"WWW-Authenticate": "Bearer"},
        )
    if token.count(".") != 2:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session. Please sign in again.")
    return verify_token(token)
