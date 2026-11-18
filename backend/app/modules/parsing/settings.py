"""Plan parser settings (env prefix PLAN_PARSER_, same .env files as the app).

    PLAN_PARSER_LLM_PROVIDER         provider name; default: LLM_PROVIDER, else "gemini"
    PLAN_PARSER_LLM_MODEL            model name; default: the provider adapter's default
    PLAN_PARSER_LLM_FALLBACK_MODELS  comma-separated models tried when the main one is
                                     down; unset = the adapter's default list, "none" = no
                                     fallback
    PLAN_PARSER_LLM_TIMEOUT_S        seconds to wait for one reply, default 120
    PLAN_PARSER_MAX_PAGES            PDF pages sent to the model, default 4
    PLAN_PARSER_CACHE                "off" disables the parsed-plan cache
    PLAN_PARSER_CACHE_DIR            cache folder, default backend/.tmp/plan_cache

The API key is not stored here. The adapter reads it from the app's existing key
variables (GEMINI_API_KEY / LLM_API_KEY for Gemini).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class PlanParserSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PLAN_PARSER_",
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = ""
    llm_model: str = ""
    llm_fallback_models: str = ""
    llm_timeout_s: float = 120.0
    max_pages: int = 4
    cache: str = "on"
    cache_dir: str = ""

    def provider(self) -> str:
        if self.llm_provider:
            return self.llm_provider
        from app.core.config import settings as app_settings

        return app_settings.llm_provider or "gemini"

    def fallback_models(self) -> list[str] | None:
        """None = adapter default; [] = no fallback."""
        raw = self.llm_fallback_models.strip()
        if not raw:
            return None
        if raw.lower() == "none":
            return []
        return [m.strip() for m in raw.split(",") if m.strip()]


@lru_cache
def get_settings() -> PlanParserSettings:
    return PlanParserSettings()
