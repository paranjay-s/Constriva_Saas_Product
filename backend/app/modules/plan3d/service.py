"""Rules of the 3D gateway: quality names, job status, embed tokens and what a token may reach.

Pure functions: no HTTP and no database here, so every rule is tested on its own.
"""

import hashlib
import hmac
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

# Our names for a build -> PlanTo3D's. Two qualities (PART 2, C): Low, a quick draft for the
# walkthrough, and High, baked light (then photoreal stills and a video tour, run as tours).
# Jobs stored with the old "medium" are High.
QUALITY_TO_SERVICE = {"low": "draft", "high": "high"}
SERVICE_TO_QUALITY = {service: ours for ours, service in QUALITY_TO_SERVICE.items()}
LEGACY_QUALITY = {"medium": "high"}


def is_job_id(value: object) -> bool:
    return isinstance(value, str) and bool(JOB_ID.match(value))


def qualities(service_ready: bool) -> list[QualityInfo]:
    """The two qualities our pages name, and whether each can be built now."""
    not_ready = "" if service_ready else "The 3D builder is not set up yet."
    return [
        QualityInfo(
            id="low",
            label="Low",
            description="Fast: every room at its drawn size, furnished, to walk through.",
            available=service_ready,
            reason=not_ready,
        ),
        QualityInfo(
            id="high",
            label="High",
            description="Baked light and textures, then photoreal stills of every room and a "
            "video tour (you get an email when it is ready).",
            available=service_ready,
            reason=not_ready,
        ),
    ]


def job_status(
    row: dict[str, Any], service: dict[str, Any] | None, reading: str | None = None
) -> JobStatus:
    """Our view of a job: who owns it (the row) and how far PlanTo3D is with it. `reading`:
    what to say while another reader works on a plan PlanTo3D's detector could not read."""
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
    stored = LEGACY_QUALITY.get(row.get("quality"), row.get("quality"))
    asked = stored if stored in QUALITY_TO_SERVICE else None

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
        preview=building and service.get("preview") is True,
        tours={
            k: {"file": str(v.get("file")), "seconds": whole(v.get("seconds"))}
            for k, v in (service.get("tours") or {}).items()
            if k in ("high", "ultra") and isinstance(v, dict) and v.get("file")
        },
        created_at=row.get("created_at"),
        reader=str(service.get("reader") or ""),
        notice=str(service.get("notice") or ""),
    ).model_copy(
        update={"stage": "detecting", "progress": 60, "message": reading} if reading else {}
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
    {
        "edit.html",
        "edit.js",
        "view.html",
        "view.js",
        "walk.js",
        "furniture.html",
        "style.css",
        "rooms.json",
        "tour.js",
    }
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


# ------------------------------------------------------------------ share links
# A share link opens the walkthrough of one job for anyone who has it, read-only, until the
# owner revokes it. The token names the job and a share id; the job row keeps the current
# share id, so revoking (or making a new link) ends every older link at once. It reaches only
# what the walkthrough page loads: no review page, plan, drawing, build log or Blender file,
# and no writes.
SHARE_AUDIENCE = "plan3d-share"
SHARE_WEB_FILES = frozenset(
    {"view.html", "view.js", "walk.js", "tour.js", "style.css", "rooms.json"}
)
SHARE_JOB_FILE = re.compile(r"^(meta\.json|house\.glb|lm_[a-z0-9_]+\.webp|tour_(high|ultra)\.mp4)$")


def new_share_id() -> str:
    import secrets

    return secrets.token_hex(12)


def share_access(user_id: str, job_id: str, share_id: str) -> dict[str, Any]:
    ttl = max(3600, int(get_settings().share_ttl_s))
    token = sign(
        {"sub": user_id, "job": job_id, "share": share_id},
        audience=SHARE_AUDIENCE,
        secret=embed_secret(),
        ttl_s=ttl,
    )
    return {"url": f"{EMBED_PREFIX}/{token}/web/view.html?job={job_id}&shared", "expires_in": ttl}


def share_claims(token: str) -> dict[str, Any]:
    """Raises TokenError unless it is a share token for a job (the caller checks its share id)."""
    claims = verify(token, audience=SHARE_AUDIENCE, secret=embed_secret())
    if not isinstance(claims.get("sub"), str) or not is_job_id(claims.get("job", "")):
        raise TokenError("token names no job")
    if not isinstance(claims.get("share"), str) or not claims["share"]:
        raise TokenError("token names no share")
    return claims


def share_request_limit(method: str, path: str, job_id: str) -> int | None:
    """0 when a share link may GET this path (relative to the service root), else None."""
    if method != "GET" or not SAFE_PATH.match(path):
        return None
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None
    if parts[0] == "web":
        return 0 if len(parts) == 2 and parts[1] in SHARE_WEB_FILES else None
    if parts[0] == "three":
        return 0 if len(parts) >= 2 else None
    if parts[:2] == ["jobs", job_id] and len(parts) == 3 and SHARE_JOB_FILE.match(parts[2]):
        return 0
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


def furniture_set(user_id: str) -> str:
    """The name of the person's own furniture models on PlanTo3D: 16 hex characters derived from
    their id with the embed secret, so PlanTo3D never sees the id, and no page can name another
    person's set."""
    key = embed_secret()
    key = key if isinstance(key, bytes) else key.encode()
    mac = hmac.new(key, f"furniture:{user_id}".encode(), hashlib.sha256)
    return mac.hexdigest()[:16]


def furniture_route(path: str, query: str, fset: str) -> tuple[str, str]:
    """An embedded request's path and query with the person's furniture set put in: the models
    list and its changes get `set=` (any `set` the page sent is dropped), and a picture of an item
    comes from the set's own pictures."""
    parts = path.split("/")
    if parts[:2] == ["api", "furniture"]:
        kept = "&".join(q for q in query.split("&") if q and not q.startswith("set="))
        return path, (kept + "&" if kept else "") + f"set={fset}"
    if len(parts) == 2 and parts[0] == "thumbs":
        return f"thumbs/{fset}/{parts[1]}", query
    return path, query
