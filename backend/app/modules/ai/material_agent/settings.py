"""Material Finder settings (env prefix MATERIAL_, same .env files as the app).

    MATERIAL_VISION_MODEL          photo analysis model, default gemini-3.5-flash-lite
                                   (measured ~5 s per photo; gemini-3.5-flash took 60-150 s)
    MATERIAL_VISION_FALLBACK_MODEL used when the vision model is down, default gemini-3.5-flash
    MATERIAL_TEXT_MODEL            chat interpretation + explanation, default gemini-3.5-flash-lite
    MATERIAL_TEXT_FALLBACK_MODEL   default gemini-3.5-flash
    MATERIAL_VISION_THINKING       thinking level, default "low" (faster); "" = provider default
    MATERIAL_LLM_TIMEOUT_S         seconds to wait for the vision model, default 30
    MATERIAL_FALLBACK_TIMEOUT_S    seconds to wait for the fallback model, default 40
    MATERIAL_TEXT_TIMEOUT_S        seconds for chat / summary calls, default 15 (then keywords)
    MATERIAL_MAX_IMAGES            images per analysis, default 4
    MATERIAL_MAX_IMAGE_MB          per image, default 10
    MATERIAL_MAX_PLAN_MB           uploaded plan file, default 20
    MATERIAL_STORE                 "memory" keeps sessions in memory (default: Supabase
                                   conversations/messages when configured)
    MATERIAL_CACHE_DIR             vision result cache, default backend/.tmp/material_cache

The API key is never stored here; it is read from GEMINI_API_KEY / LLM_API_KEY.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[4]


class MaterialSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MATERIAL_",
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    vision_model: str = "gemini-3.5-flash-lite"
    vision_fallback_model: str = "gemini-3.5-flash"
    text_model: str = "gemini-3.5-flash-lite"
    text_fallback_model: str = "gemini-3.5-flash"
    vision_thinking: str = "low"
    llm_timeout_s: float = 30.0
    fallback_timeout_s: float = 40.0
    text_timeout_s: float = 15.0
    max_images: int = 4
    max_image_mb: float = 10.0
    max_plan_mb: float = 20.0
    store: str = ""
    cache_dir: str = ""

    @property
    def cache_path(self) -> Path:
        return Path(self.cache_dir) if self.cache_dir else BACKEND_DIR / ".tmp" / "material_cache"


@lru_cache
def get_settings() -> MaterialSettings:
    return MaterialSettings()
