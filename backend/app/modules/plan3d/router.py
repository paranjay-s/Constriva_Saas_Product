"""3D gateway, mounted at /api/v1/3d. The only way a browser reaches PlanTo3D.

Signed-in API (Bearer token, and the job must be the user's own):

GET    /system                  is the 3D builder ready, and which qualities can be built
POST   /jobs                    multipart `file` (PDF, within the upload limits), optional
                                `project_id` -> 201 {job_id}; detection starts at once
POST   /jobs/sample             the same with PlanTo3D's sample plan
POST   /jobs/from-floorplan     {plan_id}: a plan of our floor plan generator, no detection
GET    /jobs                    the user's jobs, newest first (optional ?project_id=)
GET    /jobs/{job_id}           stage, progress, message, time left, queue position, and
                                which reader read the plan (fallback.py: no upload ends on
                                an error)
POST   /jobs/{job_id}/build     {quality: low | medium | high}
POST   /jobs/{job_id}/export    pack the Blender file -> {file}
POST   /jobs/{job_id}/embed     a signed token and the URLs of PlanTo3D's pages for an iframe
POST   /embed                   the same for the furniture models page alone
DELETE /jobs/{job_id}

Embedded pages and their files (no Bearer token: an iframe cannot send one):

GET | POST | DELETE /embed/{token}/{path}
    `token` is short-lived, signed, and names one user and one job. Only what PlanTo3D's
    own pages need is forwarded: its pages, three.js, the job's files and status, saving
    the reviewed plan, the Blender export, converting a recording, and the furniture
    models. Everything else is 404.
"""

import logging
import re
from collections.abc import AsyncIterator
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response, StreamingResponse
from starlette.background import BackgroundTask

from app.core.security import AuthenticatedUser, clean_uuid, get_current_user
from app.core.signed_token import TokenError
from app.modules.ai.floorplan import service as floorplan_service
from app.modules.parsing.service import read_plan_upload
from app.modules.plan3d import areas, creator, fallback, gapfill, notify, service, verify
from app.modules.plan3d.client import (
    Plan3dClient,
    Plan3dError,
    Plan3dUnavailable,
    get_plan3d_client,
)
from app.modules.plan3d.schemas import (
    BuildRequest,
    EmbedAccess,
    ExportReady,
    FromFloorplan,
    JobCreated,
    JobStatus,
    NotificationSettings,
    StillsRequest,
    SystemStatus,
    TourRequest,
)
from app.modules.plan3d.settings import get_settings
from app.modules.plan3d.store import JobStore, get_job_store
from app.modules.projects.service import user_owns_project

logger = logging.getLogger("construtiva.plan3d.router")


class RedactEmbedTokens(logging.Filter):
    """An embed token is a credential in the URL: access logs show /embed/<redacted>/..."""

    PATTERN = re.compile(r"(/api/v1/3d/embed/)[^/\s\"?]+")

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                self.PATTERN.sub(r"\1<redacted>", a) if isinstance(a, str) else a
                for a in record.args
            )
        if isinstance(record.msg, str):
            record.msg = self.PATTERN.sub(r"\1<redacted>", record.msg)
        return True


for _name in ("uvicorn.access", "uvicorn.error", "construtiva"):
    logging.getLogger(_name).addFilter(RedactEmbedTokens())
router = APIRouter()

User = Annotated[AuthenticatedUser, Depends(get_current_user)]
Service = Annotated[Plan3dClient, Depends(get_plan3d_client)]
Store = Annotated[JobStore, Depends(get_job_store)]
AiReader = Annotated[fallback.AiReader, Depends(fallback.get_ai_reader)]

NOT_FOUND = "3D job not found."


def _http_error(error: Plan3dError) -> HTTPException:
    return HTTPException(status_code=error.status, detail=error.message)


async def _own_job(store: JobStore, job_id: str, user: AuthenticatedUser) -> dict[str, Any]:
    """The job's row if it is the user's, else 404 (no hint whether it exists)."""
    if not service.is_job_id(job_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    row = await run_in_threadpool(store.get, job_id)
    if row is None or str(row.get("user_id")) != str(user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return row


async def _project_of(user: AuthenticatedUser, project_id: str | None) -> str | None:
    """A project id the user owns, or None when none was given. 404 for anyone else's."""
    if not project_id or not project_id.strip():
        return None
    clean = clean_uuid(project_id)
    if not clean or not await run_in_threadpool(user_owns_project, clean, user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    return clean


# ------------------------------------------------------------------ signed-in API


@router.get("/system", response_model=SystemStatus, summary="Is the 3D builder ready")
async def system_status(user: User, planto3d: Service) -> SystemStatus:
    try:
        checks = await planto3d.system()
    except Plan3dUnavailable as e:
        return SystemStatus(
            reachable=False, ready=False, qualities=service.qualities(False), detail=e.message
        )
    except Plan3dError as e:
        raise _http_error(e) from e
    ready = bool(checks.get("ready"))
    return SystemStatus(
        reachable=True,
        ready=ready,
        checks={k: v for k, v in checks.items() if k != "ready"},
        qualities=service.qualities(ready),
    )


async def _start(
    pdf_bytes: bytes,
    name: str,
    source: str,
    user: AuthenticatedUser,
    project_id: str | None,
    planto3d: Plan3dClient,
    store: JobStore,
    stored: dict[str, Any] | None = None,
) -> JobCreated:
    """Upload to PlanTo3D and record the owner. With `stored` (a plan of our floor plan
    generator) there is no detection: that plan is imported instead."""
    try:
        job_id = await planto3d.upload(pdf_bytes, name, detect=stored is None)
    except Plan3dError as e:
        raise _http_error(e) from e
    try:
        await run_in_threadpool(
            store.add, job_id, user.id, project_id=project_id, name=name, source=source
        )
    except Exception as e:
        # A job nobody owns could never be reached: take it off the builder again.
        logger.error("Could not record the owner of 3D job %s: %s", job_id, e)
        try:
            await planto3d.delete(job_id)
        except Plan3dError:
            logger.warning("3D job %s is left on the builder without an owner", job_id)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The plan could not be saved to your account. Please try again in a moment.",
        ) from e
    if stored is not None:
        converted = fallback.stored_plan(stored, name)
        try:
            if converted.usable:
                notice = fallback.STORED_NOTICE.format(
                    name=stored["name"], version=stored["version"]
                )
                await planto3d.import_plan(job_id, converted.plan, "stored", notice)
            else:
                notice = fallback.TRACE_NOTICE.format(why=f" ({converted.reason})")
                await planto3d.import_plan(job_id, None, "trace", notice)
        except Plan3dError as e:
            raise _http_error(e) from e
    return JobCreated(job_id=job_id)


@router.post(
    "/jobs",
    response_model=JobCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a floor plan PDF and start detecting it",
)
async def create_job(
    user: User,
    planto3d: Service,
    store: Store,
    file: Annotated[UploadFile, File(description="Floor plan PDF")],
    project_id: Annotated[str | None, Form()] = None,
) -> JobCreated:
    # The same check as every plan upload: PDF only, within the size and page limits.
    try:
        pdf_bytes = await read_plan_upload(file)
    except ValueError as rejected:
        raise HTTPException(
            getattr(rejected, "http_status", status.HTTP_400_BAD_REQUEST), str(rejected)
        ) from rejected
    project = await _project_of(user, project_id)
    # A PDF exported by our floor plan generator, uploaded by the plan's owner: use the plan.
    stored = await run_in_threadpool(floorplan_service.stored_plan_for_pdf, pdf_bytes, user.id)
    return await _start(
        pdf_bytes, file.filename or "plan.pdf", "upload", user, project, planto3d, store, stored
    )


@router.post(
    "/jobs/from-floorplan",
    response_model=JobCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Open a plan of the floor plan generator in 3D (no detection)",
)
async def create_job_from_floorplan(
    payload: FromFloorplan, user: User, planto3d: Service, store: Store
) -> JobCreated:
    stored = await run_in_threadpool(floorplan_service.plan_for_3d, payload.plan_id, user.id)
    if stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Floor plan not found")
    try:
        project = await _project_of(user, stored.get("project_id"))
    except HTTPException:
        project = None  # a plan kept under the default project: the 3D job has none
    name = f"{stored['name']}.pdf"
    return await _start(stored["pdf"], name, "floorplan", user, project, planto3d, store, stored)


@router.post(
    "/jobs/sample",
    response_model=JobCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Start a job with PlanTo3D's sample plan",
)
async def create_sample_job(
    user: User, planto3d: Service, store: Store, project_id: str | None = None
) -> JobCreated:
    project = await _project_of(user, project_id)
    try:
        pdf_bytes = await planto3d.sample_pdf()
    except Plan3dError as e:
        raise _http_error(e) from e
    return await _start(pdf_bytes, "sample_plan.pdf", "sample", user, project, planto3d, store)


@router.get("/jobs", response_model=list[JobStatus], summary="The user's 3D jobs")
async def list_jobs(
    user: User, planto3d: Service, store: Store, ai: AiReader, project_id: str | None = None
) -> list[JobStatus]:
    project = await _project_of(user, project_id)
    rows = await run_in_threadpool(store.list_for_user, user.id, project)
    jobs = []
    for row in rows[:30]:
        try:
            jobs.append(await _status(row, planto3d, ai))
        except Plan3dError as e:
            raise _http_error(e) from e
    return jobs


async def _status(row: dict[str, Any], planto3d: Plan3dClient, ai: fallback.AiReader) -> JobStatus:
    """The job's status; when PlanTo3D's detector has failed, the other readers start."""
    job_id = row["id"]
    found = await planto3d.job(job_id)
    notify.observe(job_id, found)
    if (found or {}).get("stage") == "detected":
        areas.start(job_id, planto3d)
        verify.start(job_id, planto3d)
        gapfill.start(job_id, planto3d)
    if fallback.detector_failed(found):
        name = row.get("name") or str((found or {}).get("name") or "plan.pdf")
        fallback.start(job_id, name, str((found or {}).get("message") or ""), planto3d, ai)
    return service.job_status(row, found, fallback.reading_message(job_id))


@router.get("/jobs/{job_id}", response_model=JobStatus, summary="Where a job is")
async def get_job(
    job_id: str, user: User, planto3d: Service, store: Store, ai: AiReader
) -> JobStatus:
    row = await _own_job(store, job_id, user)
    try:
        return await _status(row, planto3d, ai)
    except Plan3dError as e:
        raise _http_error(e) from e


@router.post("/jobs/{job_id}/build", response_model=JobStatus, summary="Build the 3D house")
async def build_job(
    job_id: str, payload: BuildRequest, user: User, planto3d: Service, store: Store
) -> JobStatus:
    row = await _own_job(store, job_id, user)
    service_quality = service.QUALITY_TO_SERVICE.get(payload.quality)
    if service_quality is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose Low or High.")
    try:
        await planto3d.build(job_id, service_quality, service.furniture_set(user.id))
        notify.watch(job_id, user.id, getattr(user, "email", "") or "", payload.quality)
        notify.start_poller(planto3d)
        await run_in_threadpool(store.set_quality, job_id, payload.quality)
        row["quality"] = payload.quality
        return service.job_status(row, await planto3d.job(job_id))
    except Plan3dError as e:
        raise _http_error(e) from e


@router.get("/notifications", summary="The user's build notifications, newest first")
async def notifications(user: User) -> dict:
    return {"email": notify.email_on(user.id), "items": notify.events(user.id)}


@router.put("/notifications/settings", summary="Turn build emails on or off")
async def notification_settings(payload: NotificationSettings, user: User) -> dict:
    notify.set_email(user.id, payload.email)
    return {"email": notify.email_on(user.id)}


@router.post("/jobs/{job_id}/tour", response_model=JobStatus, summary="Render a video tour")
async def render_tour(
    job_id: str, payload: TourRequest, user: User, planto3d: Service, store: Store
) -> JobStatus:
    """A video tour of the built house at 1080p: High (EEVEE) or Ultra (Cycles), in the evening
    (default) or by day, with room titles and a minimap. Rendered in chunks by PlanTo3D; the job
    reads as building, with frames done and time left, until the video is ready."""
    row = await _own_job(store, job_id, user)
    try:
        await planto3d.tour(job_id, payload.quality, payload.mode)
        notify.watch(job_id, user.id, getattr(user, "email", "") or "", payload.quality)
        notify.start_poller(planto3d)
        return service.job_status(row, await planto3d.job(job_id))
    except Plan3dError as e:
        raise _http_error(e) from e


@router.post("/jobs/{job_id}/stills", response_model=JobStatus, summary="Render High stills")
async def render_stills(
    job_id: str, payload: StillsRequest, user: User, planto3d: Service, store: Store
) -> JobStatus:
    """Photoreal stills (1920 px) of every room and four elevations, in the evening or by day, then
    a 1080p fast tour made from them. The job reads as building, with stills done and time left,
    until they are ready; the owner gets an email."""
    row = await _own_job(store, job_id, user)
    try:
        await planto3d.stills(job_id, payload.mode)
        notify.watch(job_id, user.id, getattr(user, "email", "") or "", "high")
        notify.start_poller(planto3d)
        return service.job_status(row, await planto3d.job(job_id))
    except Plan3dError as e:
        raise _http_error(e) from e


@router.post("/jobs/{job_id}/export", response_model=ExportReady, summary="Pack the Blender file")
async def export_job(job_id: str, user: User, planto3d: Service, store: Store) -> ExportReady:
    await _own_job(store, job_id, user)
    try:
        url = await planto3d.export(job_id)
    except Plan3dError as e:
        raise _http_error(e) from e
    return ExportReady(file=url.rsplit("/", 1)[-1])


@router.post("/jobs/{job_id}/embed", response_model=EmbedAccess, summary="Access for an iframe")
async def embed_job(job_id: str, user: User, store: Store) -> EmbedAccess:
    await _own_job(store, job_id, user)
    return service.embed_access(user.id, job_id)


@router.post("/embed", response_model=EmbedAccess, summary="Access for the furniture models page")
async def embed_furniture(user: User) -> EmbedAccess:
    return service.embed_access(user.id, None)


@router.post(
    "/jobs/{job_id}/share", summary="A share link to the walkthrough (replaces any older link)"
)
async def share_job(job_id: str, user: User, store: Store) -> dict[str, Any]:
    await _own_job(store, job_id, user)
    share_id = service.new_share_id()
    await run_in_threadpool(store.set_share, job_id, share_id)
    return service.share_access(str(user.id), job_id, share_id)


@router.delete(
    "/jobs/{job_id}/share",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the walkthrough's share link",
)
async def unshare_job(job_id: str, user: User, store: Store) -> Response:
    await _own_job(store, job_id, user)
    await run_in_threadpool(store.set_share, job_id, None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/creator", summary="Have the creator agent make a library asset (admins)")
async def run_creator(body: dict[str, Any], user: User) -> dict[str, Any]:
    """Off unless PLAN3D_CREATOR_AGENT, and only for the ids in PLAN3D_CREATOR_ADMINS. The asset is
    added to the library as unreviewed."""
    settings = get_settings()
    admins = {a.strip() for a in settings.creator_admins.split(",") if a.strip()}
    if not settings.creator_agent or str(user.id) not in admins:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The creator agent is not available.")
    area = str(body.get("area") or "")
    size = body.get("size_m")
    if not re.fullmatch(r"[a-z0-9_]{2,40}", area) or not (
        isinstance(size, list) and len(size) == 3 and all(isinstance(v, int | float) for v in size)
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "area and size_m [w, d, h] needed"
        )
    name = str(body.get("name") or area.replace("_", " "))[:80]
    description = str(body.get("description") or "")[:1000]
    return await run_in_threadpool(creator.run, area, name, description, [float(v) for v in size])


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a job")
async def delete_job(job_id: str, user: User, planto3d: Service, store: Store) -> Response:
    await _own_job(store, job_id, user)
    try:
        await planto3d.delete(job_id)  # 409 while it is being built
    except Plan3dError as e:
        raise _http_error(e) from e
    fallback.forget(job_id)
    await run_in_threadpool(store.delete, job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------ embedded pages and files

# Response headers of PlanTo3D that are passed on. Nothing else leaves the gateway.
PASSED_HEADERS = ("content-type", "content-length", "cache-control", "last-modified", "etag")


async def _limited(body: AsyncIterator[bytes], limit: int) -> AsyncIterator[bytes]:
    """The request body, cut off if it is longer than it said it would be."""
    sent = 0
    async for chunk in body:
        sent += len(chunk)
        if sent > limit:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "The file is too large.")
        yield chunk


@router.api_route(
    "/embed/{token}/{path:path}",
    methods=["GET", "POST", "DELETE"],
    summary="PlanTo3D's pages and files for an iframe (authorised by the signed token in the URL)",
    # Not an API for clients: it serves pages. Its rules are pinned in tests/unit/test_plan3d.py.
    include_in_schema=False,
)
async def embedded(
    token: str, path: str, request: Request, planto3d: Service, store: Store
) -> Response:
    try:
        claims = service.embed_claims(token)
        limit = service.embed_request_limit(request.method, path, claims.get("job"))
    except TokenError:
        # a share link: read-only walkthrough files, while the job still holds this share id
        try:
            claims = service.share_claims(token)
        except TokenError as refused:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "This link has expired. Please reload the page."
            ) from refused
        row = await run_in_threadpool(store.get, claims["job"])
        if not row or row.get("share_id") != claims["share"]:
            raise HTTPException(status.HTTP_410_GONE, "This share link was turned off.") from None
        limit = service.share_request_limit(request.method, path, claims["job"])
    if limit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")

    headers: dict[str, str] = {}
    content: AsyncIterator[bytes] | None = None
    if request.method == "POST":
        # PlanTo3D reads exactly Content-Length bytes, so a body must say how long it is.
        declared = request.headers.get("content-length")
        if declared is None and "transfer-encoding" not in request.headers:
            declared = "0"  # a POST without a body
        if declared is None or not declared.isdigit():
            raise HTTPException(status.HTTP_411_LENGTH_REQUIRED, "Content-Length is required.")
        if int(declared) > limit:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "The file is too large.")
        headers["Content-Length"] = declared
        if "content-type" in request.headers:
            headers["Content-Type"] = request.headers["content-type"]
        content = _limited(request.stream(), int(declared))

    # the person's own furniture models: PlanTo3D keeps them per set (service.furniture_set)
    path, query = service.furniture_route(
        path, request.url.query, service.furniture_set(claims["sub"])
    )
    try:
        upstream = await planto3d.http.send(
            planto3d.http.build_request(
                request.method,
                # the query goes on as it came: the pages read it themselves
                httpx.URL("/" + path, query=query.encode("ascii")),
                headers=headers,
                content=content,
                timeout=httpx.Timeout(900.0, connect=5.0),  # exports and conversions are slow
            ),
            stream=True,
        )
    except httpx.HTTPError as e:
        logger.warning("PlanTo3D %s /%s failed: %s", request.method, path, type(e).__name__)
        raise _http_error(Plan3dUnavailable(type(e).__name__)) from e

    passed = {name: upstream.headers[name] for name in PASSED_HEADERS if name in upstream.headers}
    # The token is in the URL: do not leak it in a Referer, and let only our frontend frame this.
    passed["Referrer-Policy"] = "no-referrer"
    # never kept by a shared cache (the URL carries the token), whatever PlanTo3D said
    upstream_cc = passed.get("cache-control", "")
    passed.pop("cache-control", None)
    passed["Cache-Control"] = "private" + (f", {upstream_cc}" if upstream_cc else "")
    passed["X-Content-Type-Options"] = "nosniff"
    passed["Content-Security-Policy"] = f"frame-ancestors {service.frame_ancestors()}"
    if path.endswith(".zip"):
        passed["Content-Disposition"] = 'attachment; filename="house-blender.zip"'
    return StreamingResponse(
        upstream.aiter_raw(),
        status_code=upstream.status_code,
        headers=passed,
        background=BackgroundTask(upstream.aclose),
    )
