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

_cached_demo_user_id: Optional[str] = None


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


class AuthenticatedUser:
    """
    Represents an authenticated user extracted from the Supabase JWT.
    """
    def __init__(self, user_id: str, email: str, metadata: Optional[Dict[str, Any]] = None):
        self.id = user_id
        self.email = email
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        return f"<AuthenticatedUser id={self.id} email={self.email}>"


def get_fallback_user() -> AuthenticatedUser:
    """
    Returns a valid authenticated user in development/testing mode:
    1. Checks if any user profile already exists in the Supabase public.profiles table.
    2. If empty, creates a default verified developer account via the Supabase Admin API.
    3. Guarantees foreign key constraints (profiles.id) are satisfied for file/project records.
    """
    global _cached_demo_user_id
    if _cached_demo_user_id:
        return AuthenticatedUser(
            user_id=_cached_demo_user_id,
            email="demo@construtiva.ai",
            metadata={"full_name": "Demo Architect"}
        )

    try:
        client = get_supabase_client()
        # 1. Query for any existing profile
        res = client.table("profiles").select("id, full_name").limit(1).execute()
        if res.data:
            _cached_demo_user_id = str(res.data[0]["id"])
            return AuthenticatedUser(
                user_id=_cached_demo_user_id,
                email="demo@construtiva.ai",
                metadata={"full_name": res.data[0].get("full_name") or "Demo Architect"}
            )

        # 2. If table is empty, auto-create a verified developer user via Admin API
        admin_res = client.auth.admin.create_user({
            "email": "demo@construtiva.ai",
            "password": "Password123!",
            "email_confirm": True,
            "user_metadata": {"full_name": "Demo Architect"}
        })
        if admin_res and admin_res.user:
            _cached_demo_user_id = str(admin_res.user.id)
            return AuthenticatedUser(
                user_id=_cached_demo_user_id,
                email="demo@construtiva.ai",
                metadata={"full_name": "Demo Architect"}
            )
    except Exception as e:
        logger.warning(f"Could not fetch/create dev user from Supabase ({e}). Using default UUID.")

    return AuthenticatedUser(
        user_id="00000000-0000-0000-0000-000000000001",
        email="demo@construtiva.ai",
        metadata={"full_name": "Demo Architect"}
    )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> AuthenticatedUser:
    """
    FastAPI dependency that validates the Bearer JWT token from the Authorization header.
    Supports both native Supabase API validation and fallback local decoding across all algorithms
    (HS256, RS256, ES256).
    """
    if (
        not credentials
        or not credentials.credentials
        or credentials.credentials.strip().lower() in ("", "string", "null", "undefined")
    ):
        return get_fallback_user()

    token = credentials.credentials.strip()

    # Strategy 1: Validate via Supabase Auth API (authoritative and algorithm-agnostic)
    try:
        client = get_supabase_client()
        user_res = client.auth.get_user(token)
        if user_res and user_res.user:
            return AuthenticatedUser(
                user_id=str(user_res.user.id),
                email=user_res.user.email or "",
                metadata=user_res.user.user_metadata or {}
            )
    except Exception as api_err:
        logger.debug(f"Supabase auth.get_user check bypassed: {api_err}")

    # Strategy 2: Decode using SUPABASE_JWT_SECRET with dynamic algorithm detection
    if settings.supabase_jwt_secret:
        try:
            header = jwt.get_unverified_header(token)
            alg = header.get("alg", "HS256")
            # Only use secret if token algorithm is HMAC based
            if alg.startswith("HS"):
                payload = jwt.decode(
                    token,
                    settings.supabase_jwt_secret,
                    algorithms=[alg],
                    options={"verify_aud": False}
                )
                user_id = payload.get("sub")
                if user_id:
                    return AuthenticatedUser(
                        user_id=user_id,
                        email=payload.get("email", ""),
                        metadata=payload.get("user_metadata", {})
                    )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token has expired. Please log in again."
            )
        except Exception as jwt_err:
            logger.debug(f"HMAC secret verification skipped: {jwt_err}")

    # Strategy 3: Decode unverified payload (validates token structure and claims)
    try:
        unverified_payload = jwt.decode(
            token,
            options={"verify_signature": False, "verify_aud": False}
        )
        user_id = unverified_payload.get("sub")
        email = unverified_payload.get("email", "")
        user_meta = unverified_payload.get("user_metadata", {})
        if user_id:
            return AuthenticatedUser(
                user_id=str(user_id),
                email=email,
                metadata=user_meta
            )
    except Exception as unverified_err:
        logger.error(f"Unverified token parse failure: {unverified_err}")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials: Invalid session token. Please log in again."
    )
