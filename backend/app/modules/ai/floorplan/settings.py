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

Building model, areas and drawing (pro run; values from docs/pro/2d/RULES.md, to be
confirmed against the Dubai Building Code by an engineer):
    FLOORPLAN_WALL_EXTERIOR_MM    200
    FLOORPLAN_WALL_INTERIOR_MM    150 (between rooms)
    FLOORPLAN_WALL_PARTITION_MM   100 (inside a suite: bath, dress, store, WC)
    FLOORPLAN_STOREY_HEIGHT_MM    3300 floor to floor (2.7 m clear + slab and finishes)
    FLOORPLAN_SETBACK_FRONT_M     3.0  road side
    FLOORPLAN_SETBACK_SIDE_M      1.5  left and right (DBC Table K.1 says 3 m)
    FLOORPLAN_SETBACK_REAR_M      1.5  (DBC Table K.1 says 3 m)
    FLOORPLAN_BUILT_UP_SHARE      0.70 built-up share of the plot when only the plot is known
    FLOORPLAN_BUILT_UP_MIN        0.65 / FLOORPLAN_BUILT_UP_MAX 0.75: the band kept unless asked
    FLOORPLAN_FULL_RESOLVE_S      30   time budget of a full re-solve ("start over")
    FLOORPLAN_SHEET               A3 (or A1)
    FLOORPLAN_FURNITURE           true: draw one minimal furniture set per room
    FLOORPLAN_SITE_RULES          true: apply setbacks and the built-up target (false: whole plot)
    FLOORPLAN_MODEL_SIGNING_KEY   signs the building model embedded in every exported PDF
                               (empty: derived from PLAN3D_EMBED_SECRET / SUPABASE_JWT_SECRET)
    FLOORPLAN_DWG_CONVERTER       path of the ODA File Converter (DWG export); empty = default paths

The API key is never stored here; it is read from the existing app settings
(GEMINI_API_KEY / LLM_API_KEY) at call time.
"""

from functools import lru_cache

from pydantic import SecretStr
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

    wall_exterior_mm: int = 200
    wall_interior_mm: int = 150
    wall_partition_mm: int = 100
    storey_height_mm: int = 3300
    setback_front_m: float = 3.0
    setback_side_m: float = 1.5
    setback_rear_m: float = 1.5
    built_up_share: float = 0.70
    built_up_min: float = 0.65
    built_up_max: float = 0.75
    full_resolve_s: float = 30.0
    site_rules: bool = True  # setbacks and built-up target; False lays out the whole plot
    model_signing_key: SecretStr = SecretStr("")  # signs the model embedded in PDFs
    dwg_converter: str = ""  # path of the ODA File Converter; "" = look in the usual places
    sheet: str = "A3"
    furniture: bool = True


@lru_cache
def get_settings() -> FloorplanSettings:
    return FloorplanSettings()
