"""Plan parser settings (env prefix PLAN_PARSER_, same .env files as the app).

    PLAN_PARSER_LLM_PROVIDER   which vendor reads the drawings: gemini (default) or anthropic
    PLAN_PARSER_LLM_MODEL      the model name at that vendor (required)
    PLAN_PARSER_LLM_API_KEY    the API key for that vendor (required)
    PLAN_PARSER_LLM_TIMEOUT_S  seconds to wait on one model call, default 300
    PLAN_PARSER_MAX_PDF_MB     largest PDF accepted, default 20
    PLAN_PARSER_MAX_PDF_PAGES  most pages a PDF may have, default 10
    PLAN_PARSER_CACHE          "off" disables the parsed-plan cache
    PLAN_PARSER_CACHE_DIR      cache folder, default backend/.tmp/plan_cache

Switching model or vendor is a change of these values only. No variable is named after a
vendor, and no code outside the vendor's adapter changes.

Backward compatibility, for Gemini only: when the provider is gemini and
PLAN_PARSER_LLM_API_KEY is empty, the key falls back to the app's existing LLM_API_KEY and
then GEMINI_API_KEY. No other provider has a fallback, and one provider never stands in
for another.

The key is held as a SecretStr so it cannot be printed or logged by accident.
"""

from dataclasses import dataclass, field
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_PROVIDER = "gemini"


class PlanParserConfigError(RuntimeError):
    """The plan parser's settings are unusable. The message names the variable to fix."""


class PlanParserSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PLAN_PARSER_",
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = DEFAULT_PROVIDER
    llm_model: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout_s: float = 300.0
    max_pdf_mb: float = 20.0
    max_pdf_pages: int = 10
    cache: str = "on"
    cache_dir: str = ""

    @property
    def max_pdf_bytes(self) -> int:
        return int(self.max_pdf_mb * 1024 * 1024)


@lru_cache
def get_settings() -> PlanParserSettings:
    return PlanParserSettings()


@dataclass(frozen=True)
class LLMConfig:
    """A validated provider, model and key. The key never appears in its repr."""

    provider: str
    model: str
    api_key: str = field(repr=False)
    timeout_s: float = 300.0


def _legacy_gemini_key() -> str:
    """The app's older key variables, read through the app settings loader."""
    from app.core.config import settings as app_settings

    return app_settings.llm_api_key or app_settings.gemini_api_key or ""


def resolve_llm_config(settings: PlanParserSettings | None = None) -> LLMConfig:
    """The provider, model and key to use, or one PlanParserConfigError naming the variable."""
    from app.modules.ai.llm.json_client import known_providers

    settings = settings or get_settings()
    provider = (settings.llm_provider or DEFAULT_PROVIDER).strip().lower()
    if provider not in known_providers():
        raise PlanParserConfigError(
            f"PLAN_PARSER_LLM_PROVIDER is {settings.llm_provider!r}, which is not a supported "
            f"provider. Set it to one of: {', '.join(known_providers())}."
        )

    model = settings.llm_model.strip()
    if not model:
        raise PlanParserConfigError(
            f"PLAN_PARSER_LLM_MODEL is not set. Set it to the {provider} model that should "
            "read the drawings."
        )

    api_key = settings.llm_api_key.get_secret_value().strip()
    if not api_key and provider == "gemini":
        api_key = _legacy_gemini_key().strip()
    if not api_key:
        hint = " (or LLM_API_KEY / GEMINI_API_KEY)" if provider == "gemini" else ""
        raise PlanParserConfigError(
            f"PLAN_PARSER_LLM_API_KEY is not set{hint}. Set it to the {provider} API key."
        )

    if settings.max_pdf_mb <= 0:
        raise PlanParserConfigError("PLAN_PARSER_MAX_PDF_MB must be greater than 0.")
    if settings.max_pdf_pages < 1:
        raise PlanParserConfigError("PLAN_PARSER_MAX_PDF_PAGES must be at least 1.")

    return LLMConfig(
        provider=provider, model=model, api_key=api_key, timeout_s=settings.llm_timeout_s
    )
