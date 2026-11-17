"""Floor plan generator settings (env prefix FLOORPLAN_, same .env files as the app).

    FLOORPLAN_LLM_PROVIDER     gemini (default)
    FLOORPLAN_LLM_MODEL        model name, default gemini-3.5-flash-lite
    FLOORPLAN_LLM_TEMPERATURE  default 0.1
    FLOORPLAN_LLM_FALLBACK_MODEL  used when the main model times out / is busy / is gone,
                               default gemini-3.5-flash; "" disables
    FLOORPLAN_LLM_TIMEOUT_S    seconds to wait for a reply, default 20
    FLOORPLAN_LLM_THINKING     model thinking level, default "low" (faster); "" = provider default
    FLOORPLAN_SOLVER_TIME_S    CP-SAT time limit per attempt, default 8
    FLOORPLAN_MAX_ATTEMPTS     layout retries with validator feedback, default 3
    FLOORPLAN_STORE            "memory" keeps plans in memory instead of the Supabase
                               `plans` table (default: Supabase when it is configured)

The API key is never stored here; it is read from the existing app settings
(GEMINI_API_KEY / LLM_API_KEY) at call time.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class FloorplanSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FLOORPLAN_",
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = "gemini"
    llm_model: str = "gemini-3.5-flash-lite"
    llm_temperature: float = 0.1
    llm_fallback_model: str = "gemini-3.5-flash"  # used only if the main model is down
    llm_timeout_s: float = 20.0
    llm_thinking: str = "low"  # model thinking level; "" sends none (provider default)
    solver_time_s: float = 8.0
    max_attempts: int = 3
    store: str = ""  # "memory" or "" (Supabase when configured)


@lru_cache
def get_settings() -> FloorplanSettings:
    return FloorplanSettings()
