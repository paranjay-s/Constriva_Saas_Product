"""
=============================================================================
Construtiva Backend Core Configuration
=============================================================================
File: app/core/config.py
Purpose:
  Central application settings powered by Pydantic BaseSettings.
  Loads environment variables for Supabase (URL, Service Key, JWT Secret),
  Redis, and frontend CORS origin.
=============================================================================
"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration settings loaded from environment variables or .env file.
    """
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Supabase Cloud Configuration
    supabase_url: str = "https://kssgwxqttrzhhrymwicd.supabase.co"
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""

    # Database & Redis
    database_url: str = ""
    redis_url: str = "redis://localhost:6379/0"

    # CORS. FRONTEND_ORIGIN is the app's own address (also used in links in emails).
    # CORS_ORIGINS adds more sites that may call this API from the browser, comma separated
    # (the deployed frontend, so it can talk to an API running on this machine).
    # CORS_ORIGIN_REGEX optionally allows a whole pattern (for example Vercel preview URLs).
    # A frontend on localhost / 127.0.0.1 on any port is always allowed.
    frontend_origin: str = "http://localhost:5173"
    cors_origins: str = "https://constriva-saas-product.vercel.app"
    cors_origin_regex: str = ""

    # Level of the app's own log lines ("construtiva.*"): DEBUG, INFO, WARNING or ERROR.
    log_level: str = "INFO"

    # Demo access. Off by default: every request must carry a Supabase access token.
    # When AUTH_ALLOW_DEMO_USER is true, a request with no token acts as the one dedicated
    # demo profile named by AUTH_DEMO_USER_ID (the UUID of a profile created for demos).
    # Never turn this on for a deployment that holds real customer data.
    auth_allow_demo_user: bool = False
    auth_demo_user_id: str = ""
    auth_demo_user_email: str = "demo@example.com"

    # LLM Settings (Gemini API integration)
    llm_provider: str = "gemini"
    llm_api_key: str = ""
    gemini_api_key: str = ""


LOCAL_ORIGIN_REGEX = r"https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?"


def browser_origins(s: Settings | None = None) -> list[str]:
    """The sites that may call the API (and frame its 3D pages), FRONTEND_ORIGIN first.

    An origin never has a path or a trailing slash ("https://x.vercel.app/" would never
    match what the browser sends), so both are trimmed here.
    """
    s = s or settings
    out: list[str] = []
    for raw in [s.frontend_origin, *s.cors_origins.split(",")]:
        origin = raw.strip().rstrip("/")
        if origin and origin not in out:
            out.append(origin)
    return out


def cors_origin_regex(s: Settings | None = None) -> str:
    """Pattern of further allowed origins: any local port, plus CORS_ORIGIN_REGEX if set."""
    s = s or settings
    extra = s.cors_origin_regex.strip()
    return f"{LOCAL_ORIGIN_REGEX}|{extra}" if extra else LOCAL_ORIGIN_REGEX


# Instantiate singleton settings instance
settings = Settings()
