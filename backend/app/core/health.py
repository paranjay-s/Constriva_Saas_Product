"""Pre-demo health check: GET /health/deep.

Checks, without changing any data:
  database      the service client can read `projects` (service key valid, tables reachable)
  admin_client  the shared admin client still uses the service key (not a user session)
  auth          Supabase Auth answers and its signing keys can be loaded (token checks)
  ai            a Gemini API key is configured
  planto3d      the private 3D service answers and has Blender, the PDF tools, the viewer
                library and the materials (its own GET /api/system)

Open it before a client meeting: every check should say "ok".
"""

import time

from fastapi.concurrency import run_in_threadpool


def _check(fn) -> dict:
    started = time.perf_counter()
    try:
        detail = fn() or "ok"
        return {
            "status": "ok",
            "detail": detail,
            "ms": round((time.perf_counter() - started) * 1000),
        }
    except Exception as e:  # report, never raise
        return {
            "status": "fail",
            "detail": str(e)[:300],
            "ms": round((time.perf_counter() - started) * 1000),
        }


def _database() -> str:
    from app.core.supabase import get_supabase_client

    get_supabase_client().table("projects").select("id").limit(1).execute()
    return "ok"


def _admin_client() -> str:
    from app.core import supabase as sb

    client = sb.get_supabase_client()
    if client.options.headers.get("Authorization") != sb._service_auth_header:
        raise RuntimeError("admin client is not using the service key")
    return "ok"


def _auth() -> str:
    from app.core.security import _jwks

    keys = _jwks().get_jwk_set().keys
    return f"ok ({len(keys)} signing key(s))"


def _ai() -> str:
    from app.modules.ai.llm.client import api_key

    if not api_key():
        raise RuntimeError("GEMINI_API_KEY / LLM_API_KEY is not set")
    return "ok"


def _planto3d() -> str:
    import httpx

    from app.modules.plan3d.settings import get_settings

    try:
        url = get_settings().service_url.rstrip("/") + "/api/system"
        system = httpx.get(url, timeout=70).json()
    except httpx.HTTPError as e:
        raise RuntimeError(f"the 3D service is not reachable ({type(e).__name__})") from e
    missing = [
        name
        for name in ("blender", "pdf_tools", "viewer", "materials")
        if not (system.get(name) or {}).get("ok")
    ]
    if missing:
        raise RuntimeError("the 3D service is missing: " + ", ".join(missing))
    return f"ok (Blender {(system.get('blender') or {}).get('version') or '?'})"


async def deep_health() -> dict:
    checks = {}
    for name, fn in (
        ("database", _database),
        ("admin_client", _admin_client),
        ("auth", _auth),
        ("ai", _ai),
        ("planto3d", _planto3d),
    ):
        checks[name] = await run_in_threadpool(_check, fn)
    ok = all(c["status"] == "ok" for c in checks.values())
    return {"status": "ok" if ok else "fail", "checks": checks}
