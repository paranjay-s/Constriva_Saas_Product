"""
=============================================================================
Construtiva Authentication Pydantic Schemas
=============================================================================
File: app/modules/auth/schemas.py
Purpose:
  Defines request and response schemas for user registration, login, and
  profile management, interfacing with Supabase Auth and the 'profiles' table.
  Includes whitespace trimming and case normalization on email fields.
=============================================================================
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class UserRegisterRequest(BaseModel):
    """
    Payload for creating a new user account.
    """
    email: str = Field(..., min_length=3, description="Valid user email address")
    password: str = Field(..., min_length=6, description="Account password (min 6 chars)")
    full_name: str = Field(..., min_length=2, description="User's full name or organization name")
    phone: Optional[str] = Field(None, description="Optional contact phone number")

    @field_validator("email", mode="before")
    @classmethod
    def sanitize_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class UserLoginRequest(BaseModel):
    """
    Payload for authenticating an existing user.
    """
    email: str = Field(..., min_length=3, description="Registered user email address")
    password: str = Field(..., min_length=1, description="Account password")

    @field_validator("email", mode="before")
    @classmethod
    def sanitize_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class UserProfileResponse(BaseModel):
    """
    User profile representation returned after authentication or on /auth/me.
    """
    id: str
    email: str
    full_name: str
    phone: Optional[str] = None


class AuthResponse(BaseModel):
    """
    Standard authentication response containing the Supabase JWT access token.
    """
    access_token: str
    token_type: str = "bearer"
    user: UserProfileResponse
