"""Rules of the 3D gateway: quality names, job status, embed tokens and what a token may reach.

Pure functions: no HTTP and no database here, so every rule is tested on its own.
"""

import re
from typing import Any
from urllib.parse import urlsplit

from app.core.config import settings as app_settings
from app.core.signed_token import TokenError, sign, verify
from app.modules.plan3d.schemas import EmbedAccess, JobStatus, QualityInfo
from app.modules.plan3d.settings import embed_secret, get_settings

EMBED_AUDIENCE = "plan3d-embed"
EMBED_PREFIX = "/api/v1/3d/embed"
JOB_ID = re.compile(r"^[a-f0-9]{12}$")

# Our names for a build -> PlanTo3D's. "high" (the cinema video tour) has no build quality
# in PlanTo3D: its tour renderer is a command-line tool that the service does not run.
QUALITY_TO_SERVICE = {"low": "draft", "medium": "high"}
SERVICE_TO_QUALITY = {service: ours for ours, service in QUALITY_TO_SERVICE.items()}
CINEMA_UNAVAILABLE = (
    "The cinema video tour is not built by the 3D service yet: PlanTo3D renders it with a "
    "command-line tool that needs a camera route written by hand."
)


def is_job_id(value: object) -> bool:
    return isinstance(value, str) and bool(JOB_ID.match(value))


def qualities(service_ready: bool) -> list[QualityInfo]:
    """The three qualities our pages name, and whether each can be built now."""
    not_ready = "" if service_ready else "The 3D builder is not set up yet."
    return [
        QualityInfo(
            id="low",
            label="Low",
            description="Draft: the fastest build, to check the plan and walk through it.",
            available=service_ready,
            reason=not_ready,
        ),
        QualityInfo(
            id="medium",
            label="Medium",
            description="High-quality light and textures for the walkthrough.",
            available=service_ready,
            reason=not_ready,
        ),
        QualityInfo(
            id="high",
            label="High",
            description="Cinema video tour of the house.",
            available=False,
            reason=CINEMA_UNAVAILABLE,
        ),
    ]


def job_status(row: dict[str, Any], service: dict[str, Any] | None) -> JobStatus:
    """Our view of a job: who owns it (the row) and how far PlanTo3D is with it."""
    if service is None:
        return JobStatus(
            job_id=row["id"],
            name=row.get("name") or "",
            project_id=row.get("project_id"),
            source=row.get("source") or "upload",
            stage="failed",
            message="This plan is no longer on the 3D builder. Please upload it again.",
            created_at=row.get("created_at"),
        )
    building = service.get("stage") in ("queued", "building")
    built = SERVICE_TO_QUALITY.get(str(service.get("quality") or ""))
    asked = row.get("quality") if row.get("quality") in QUALITY_TO_SERVICE else None

    def whole(value: object) -> int | None:
        return (
            int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
        )

    return JobStatus(
        job_id=row["id"],
        name=row.get("name") or str(service.get("name") or ""),
        project_id=row.get("project_id"),
        source=row.get("source") or "upload",
        stage=str(service.get("stage") or "uploaded"),
        progress=whole(service.get("progress")) or 0,
        message=str(service.get("message") or ""),
        floors=[str(name) for name in service.get("floors") or []],
        scale_source=service.get("scale_source"),
        eta_left=whole(service.get("eta_left")),
        queue_position=whole(service.get("queue_position")),
        quality=(asked or built) if building else (built or None),
        build_seconds=whole(service.get("build_seconds")),
        created_at=row.get("created_at"),
    )


# ------------------------------------------------------------------ embed tokens


def embed_access(user_id: str, job_id: str | None) -> EmbedAccess:
    """A signed token for one user and one job (or the furniture page alone), and the
    URLs of PlanTo3D's pages under it."""
    ttl = max(60, int(get_settings().embed_token_ttl_s))
    claims: dict[str, Any] = {"sub": user_id}
    if job_id:
        claims["job"] = job_id
    token = sign(claims, audience=EMBED_AUDIENCE, secret=embed_secret(), ttl_s=ttl)
    base = f"{EMBED_PREFIX}/{token}"
    return EmbedAccess(
        base_url=base,
        expires_in=ttl,
        review_url=f"{base}/web/edit.html?job={job_id}&embed" if job_id else None,
        walkthrough_url=f"{base}/web/view.html?job={job_id}&embed" if job_id else None,
        furniture_url=f"{base}/web/furniture.html?embed",
        files_url=f"{base}/jobs/{job_id}" if job_id else None,
    )


def embed_claims(token: str) -> dict[str, Any]:
    """Who and what a token was issued for. Raises TokenError when it is not valid."""
    claims = verify(token, audience=EMBED_AUDIENCE, secret=embed_secret())
    if not isinstance(claims.get("sub"), str) or not claims["sub"]:
        raise TokenError("token names no user")
    if "job" in claims and not is_job_id(claims["job"]):
        raise TokenError("token names no job")
    return claims


# What PlanTo3D's own pages need, and nothing else. A token never lists jobs, uploads,
# builds or deletes: those go through the signed-in API, which records them.
WEB_FILES = frozenset(
    {"edit.html", "edit.js", "view.html", "view.js", "walk.js", "furniture.html", "style.css"}
)
SAFE_PATH = re.compile(r"^[A-Za-z0-9._\-/]+$")
PRIVATE_JOB_FILES = frozenset({"build.log"})  # holds paths of the server
# Largest request body a token may send, by what it is for.
MAX_PLAN_BYTES = 10 * 1024 * 1024
MAX_MODEL_BYTES = 100 * 1024 * 1024
MAX_RECORDING_BYTES = 200 * 1024 * 1024


def embed_request_limit(method: str, path: str, job_id: str | None) -> int | None:
    """Whether a token for `job_id` may make this request: the largest body it may send
    (0 for a request without one), or None when the request is not allowed.

    `path` is relative to the service root, without a leading slash.
    """
    if not SAFE_PATH.match(path):
        return None
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None
    furniture_item = (
        len(parts) == 3 and parts[:2] == ["api", "furniture"] and re.fullmatch(r"\w+", parts[2])
    )
    furniture_changes = get_settings().allow_furniture_changes

    if method == "GET":
        if parts[0] == "web":
            return 0 if len(parts) == 2 and parts[1] in WEB_FILES else None
        if parts[0] == "three":
            return 0 if len(parts) >= 2 else None
        if parts[0] == "thumbs":
            return 0 if len(parts) == 2 and parts[1].endswith(".png") else None
        if path in ("api/system", "api/furniture"):
            return 0
        if job_id and parts[:2] == ["jobs", job_id] and len(parts) >= 3:
            return None if parts[-1] in PRIVATE_JOB_FILES else 0
        if job_id and path == f"api/jobs/{job_id}":
            return 0
        return None
    if method == "POST":
        if job_id and path == f"api/jobs/{job_id}/plan":
            return MAX_PLAN_BYTES
        if job_id and path == f"api/jobs/{job_id}/export":
            return 0
        if job_id and path == "api/mp4":
            return MAX_RECORDING_BYTES
        if furniture_item and furniture_changes:
            return MAX_MODEL_BYTES
        return None
    if method == "DELETE":
        return 0 if furniture_item and furniture_changes else None
    return None


def frame_ancestors() -> str:
    """Value of the frame-ancestors directive: only our own frontend may frame the pages."""
    origins = [app_settings.frontend_origin, *get_settings().frame_ancestors.split(",")]
    allowed = []
    for origin in (o.strip().rstrip("/") for o in origins):
        if origin and origin not in allowed:
            allowed.append(origin)
    # a frontend on this machine may run on any port (the same rule as the API's CORS)
    if any(urlsplit(o).hostname in ("localhost", "127.0.0.1") for o in allowed):
        for local in ("http://localhost:*", "http://127.0.0.1:*"):
            if local not in allowed:
                allowed.append(local)
    return " ".join(["'self'", *allowed])
