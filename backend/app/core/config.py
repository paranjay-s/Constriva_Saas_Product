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

    # CORS
    frontend_origin: str = "http://localhost:5173"

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


# Instantiate singleton settings instance
settings = Settings()
