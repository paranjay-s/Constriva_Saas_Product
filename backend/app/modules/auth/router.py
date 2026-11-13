"""
=============================================================================
Construtiva Authentication API Router
=============================================================================
File: app/modules/auth/router.py
Purpose:
  Provides authentication endpoints with zero email confirmation gates:
  - POST /api/v1/auth/signup: Admin creation with email_confirm=True (no verification email needed).
  - POST /api/v1/auth/login: Email/password authentication returning a Supabase JWT.
    Automatically auto-confirms unconfirmed accounts in the background if encountered.
  - GET  /api/v1/auth/me: Retrieve the currently logged-in user's profile.
=============================================================================
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from app.core.supabase import get_supabase_client
from app.core.security import get_current_user, AuthenticatedUser
from app.modules.auth.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    AuthResponse,
    UserProfileResponse,
)

logger = logging.getLogger("construtiva.auth")
router = APIRouter()


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account (instant access, no email confirmation needed)"
)
async def signup(payload: UserRegisterRequest):
    """
    Registers a new user in Supabase Auth with automatic email confirmation enabled.
    Users do not need to click any email verification links and are logged in immediately.

    Args:
        payload (UserRegisterRequest): User email, password, full name, and optional phone.

    Returns:
        AuthResponse: Access token and created user profile data.
    """
    supabase = get_supabase_client()
    user_id: Optional[str] = None

    try:
        # Step 1: Create user directly via Supabase Admin API with email_confirm=True
        try:
            admin_res = supabase.auth.admin.create_user({
                "email": payload.email,
                "password": payload.password,
                "email_confirm": True,  # Pre-confirm email: No email sent, no link required!
                "user_metadata": {
                    "full_name": payload.full_name,
                    "phone": payload.phone,
                }
            })
            if admin_res and admin_res.user:
                user_id = str(admin_res.user.id)
        except Exception as create_err:
            # If user already registered in Supabase Auth, auto-confirm and update password
            err_msg = str(create_err).lower()
            if "already registered" in err_msg or "already exists" in err_msg:
                logger.info(f"User {payload.email} already registered. Auto-confirming and updating credentials...")
                users_list = supabase.auth.admin.list_users()
                user_objs = getattr(users_list, "users", users_list) if not isinstance(users_list, list) else users_list
                match = next((u for u in user_objs if getattr(u, "email", "").lower() == payload.email.lower()), None)
                if match:
                    user_id = str(match.id)
                    supabase.auth.admin.update_user_by_id(user_id, {
                        "email_confirm": True,
                        "password": payload.password,
                        "user_metadata": {
                            "full_name": payload.full_name,
                            "phone": payload.phone,
                        }
                    })
            else:
                raise create_err

        # Step 2: Ensure profile row exists in public.profiles table
        if user_id:
            supabase.table("profiles").upsert({
                "id": user_id,
                "full_name": payload.full_name,
                "phone": payload.phone,
            }).execute()

        # Step 3: Sign in immediately to generate access token
        login_res = supabase.auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password,
        })

        if not login_res.session:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User account provisioned, but could not establish active session."
            )

        session_token = login_res.session.access_token
        actual_uid = str(login_res.user.id)

        user_profile = UserProfileResponse(
            id=actual_uid,
            email=payload.email,
            full_name=payload.full_name,
            phone=payload.phone,
        )

        return AuthResponse(
            access_token=session_token,
            token_type="bearer",
            user=user_profile,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup error for {payload.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}"
        )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Sign in with email and password"
)
async def login(payload: UserLoginRequest):
    """
    Authenticates an existing user using Supabase Auth and returns an access token.
    Automatically confirms unconfirmed accounts if encountered.

    Args:
        payload (UserLoginRequest): User email and password.

    Returns:
        AuthResponse: Valid JWT access token and user profile.
    """
    supabase = get_supabase_client()

    try:
        # Authenticate via Supabase Auth
        try:
            auth_res = supabase.auth.sign_in_with_password({
                "email": payload.email,
                "password": payload.password,
            })
        except Exception as auth_err:
            err_text = str(auth_err).lower()
            # If Supabase reports email is unconfirmed, auto-confirm via Admin API and retry
            if "not confirmed" in err_text or "unconfirmed" in err_text:
                logger.info(f"Auto-confirming email for {payload.email}...")
                users_list = supabase.auth.admin.list_users()
                user_objs = getattr(users_list, "users", users_list) if not isinstance(users_list, list) else users_list
                match = next((u for u in user_objs if getattr(u, "email", "").lower() == payload.email.lower()), None)
                if match:
                    supabase.auth.admin.update_user_by_id(str(match.id), {"email_confirm": True})
                    auth_res = supabase.auth.sign_in_with_password({
                        "email": payload.email,
                        "password": payload.password,
                    })
                else:
                    raise auth_err
            else:
                raise auth_err

        if not auth_res.user or not auth_res.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )

        user_id = str(auth_res.user.id)
        token = auth_res.session.access_token

        # Fetch profile details from public.profiles table
        prof_res = supabase.table("profiles").select("full_name, phone").eq("id", user_id).execute()
        full_name = "User"
        phone = None

        if prof_res.data:
            full_name = prof_res.data[0].get("full_name") or "User"
            phone = prof_res.data[0].get("phone")
        else:
            # Fallback to user metadata
            meta = auth_res.user.user_metadata or {}
            full_name = meta.get("full_name") or "User"
            phone = meta.get("phone")

        user_profile = UserProfileResponse(
            id=user_id,
            email=payload.email,
            full_name=full_name,
            phone=phone,
        )

        return AuthResponse(
            access_token=token,
            token_type="bearer",
            user=user_profile,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error for {payload.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Retrieve current user profile"
)
async def get_current_user_profile(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Returns the authenticated user's profile information.

    Args:
        current_user (AuthenticatedUser): Extracted from Bearer JWT.

    Returns:
        UserProfileResponse: User id, email, full name, phone.
    """
    from app.core.supabase import get_user_supabase_client
    supabase = get_user_supabase_client(current_user.token)

    try:
        prof_res = supabase.table("profiles").select("*").eq("id", current_user.id).execute()
        if prof_res.data:
            row = prof_res.data[0]
            return UserProfileResponse(
                id=current_user.id,
                email=current_user.email,
                full_name=row.get("full_name") or current_user.metadata.get("full_name", "User"),
                phone=row.get("phone"),
            )

        return UserProfileResponse(
            id=current_user.id,
            email=current_user.email,
            full_name=current_user.metadata.get("full_name", "User"),
            phone=None,
        )
    except Exception as e:
        logger.warning(f"Could not fetch profile from Supabase for {current_user.id}: {e}")
        return UserProfileResponse(
            id=current_user.id,
            email=current_user.email,
            full_name=current_user.metadata.get("full_name") or "Architect User",
            phone=None,
        )
