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

    # LLM Settings (Placeholders for future Gemini API integration)
    llm_provider: str = "gemini"
    llm_api_key: str = ""


# Instantiate singleton settings instance
settings = Settings()
