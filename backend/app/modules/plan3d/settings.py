"""Settings of the 3D gateway. Environment prefix: PLAN3D_.

PLAN3D_SERVICE_URL            where the private PlanTo3D service listens (default
                              http://127.0.0.1:8080). It must not be reachable from
                              outside: browsers only ever talk to this backend.
PLAN3D_EMBED_SECRET           secret that signs the tokens of embedded pages. Set it in
                              production. When empty, a random one is made at start, so
                              tokens stop working at a restart and with several workers.
PLAN3D_EMBED_TOKEN_TTL_S      lifetime of such a token in seconds (default 3600)
PLAN3D_STORE                  "supabase" (the plan3d_jobs table, default) or "memory"
                              (lost at restart; for local work before the migration is run)
PLAN3D_TIMEOUT_S              timeout of a call to the service (default 30)
PLAN3D_ALLOW_FURNITURE_CHANGES  let signed-in users replace furniture models (default
                              false: PlanTo3D keeps one set of models for everyone until
                              models are per user).
PLAN3D_FRAME_ANCESTORS        extra origins allowed to frame the pages, comma separated.
                              FRONTEND_ORIGIN and CORS_ORIGINS are always allowed.
"""

import secrets
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Plan3dSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PLAN3D_",
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_url: str = "http://127.0.0.1:8080"
    embed_secret: SecretStr = SecretStr("")
    embed_token_ttl_s: int = 3600
    # how long a share link of a walkthrough works (the owner can revoke it sooner)
    share_ttl_s: int = 30 * 24 * 3600
    store: str = "supabase"
    timeout_s: float = 30.0
    allow_furniture_changes: bool = False
    # an AI second look at every read plan (one call each; differences go to Needs checking)
    ai_verify: bool = False
    # an AI photo editor's look at finished High stills; the stills it names are rendered again
    ai_polish: bool = False
    # Scans: the OpenCV + OCR reader before the AI reader (scan_reader.py); no AI calls
    scan_reader: bool = True
    # Scans read by the scan reader: room names and types from the AI reader (one cached call)
    scan_ai_names: bool = True
    # the AI gap-filler: one call per read plan fills what the readers missed (gapfill.py)
    ai_gapfill: bool = False
    # the creator agent: designs a library asset for an area no kit serves (creator.py)
    creator_agent: bool = False
    # user ids (comma-separated) allowed to run it; empty means nobody
    creator_admins: str = ""
    frame_ancestors: str = ""


@lru_cache
def get_settings() -> Plan3dSettings:
    return Plan3dSettings()


@lru_cache
def embed_secret() -> bytes:
    """The signing secret: the configured one, or one made for this process."""
    configured = get_settings().embed_secret.get_secret_value()
    return configured.encode("utf-8") if configured else secrets.token_bytes(32)
