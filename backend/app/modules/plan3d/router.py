"""3D gateway, mounted at /api/v1/3d. The only way a browser reaches PlanTo3D.

Signed-in API (Bearer token, and the job must be the user's own):

GET    /system                  is the 3D builder ready, and which qualities can be built
POST   /jobs                    multipart `file` (PDF, within the upload limits), optional
                                `project_id` -> 201 {job_id}; detection starts at once
POST   /jobs/sample             the same with PlanTo3D's sample plan
GET    /jobs                    the user's jobs, newest first (optional ?project_id=)
GET    /jobs/{job_id}           stage, progress, message, time left, queue position
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
from collections.abc import AsyncIterator
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response, StreamingResponse
from starlette.background import BackgroundTask

from app.core.security import AuthenticatedUser, clean_uuid, get_current_user
from app.core.signed_token import TokenError
from app.modules.parsing.service import read_plan_upload
from app.modules.plan3d import service
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
    JobCreated,
    JobStatus,
    SystemStatus,
)
from app.modules.plan3d.store import JobStore, get_job_store
from app.modules.projects.service import user_owns_project

logger = logging.getLogger("construtiva.plan3d.router")
router = APIRouter()

User = Annotated[AuthenticatedUser, Depends(get_current_user)]
Service = Annotated[Plan3dClient, Depends(get_plan3d_client)]
Store = Annotated[JobStore, Depends(get_job_store)]

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
) -> JobCreated:
    try:
        job_id = await planto3d.upload(pdf_bytes, name)
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
    return await _start(
        pdf_bytes, file.filename or "plan.pdf", "upload", user, project, planto3d, store
    )


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
    user: User, planto3d: Service, store: Store, project_id: str | None = None
) -> list[JobStatus]:
    project = await _project_of(user, project_id)
    rows = await run_in_threadpool(store.list_for_user, user.id, project)
    jobs = []
    for row in rows[:30]:
        try:
            jobs.append(service.job_status(row, await planto3d.job(row["id"])))
        except Plan3dError as e:
            raise _http_error(e) from e
    return jobs


@router.get("/jobs/{job_id}", response_model=JobStatus, summary="Where a job is")
async def get_job(job_id: str, user: User, planto3d: Service, store: Store) -> JobStatus:
    row = await _own_job(store, job_id, user)
    try:
        return service.job_status(row, await planto3d.job(job_id))
    except Plan3dError as e:
        raise _http_error(e) from e


@router.post("/jobs/{job_id}/build", response_model=JobStatus, summary="Build the 3D house")
async def build_job(
    job_id: str, payload: BuildRequest, user: User, planto3d: Service, store: Store
) -> JobStatus:
    row = await _own_job(store, job_id, user)
    service_quality = service.QUALITY_TO_SERVICE.get(payload.quality)
    if service_quality is None:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, service.CINEMA_UNAVAILABLE)
    try:
        await planto3d.build(job_id, service_quality)
        await run_in_threadpool(store.set_quality, job_id, payload.quality)
        row["quality"] = payload.quality
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


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a job")
async def delete_job(job_id: str, user: User, planto3d: Service, store: Store) -> Response:
    await _own_job(store, job_id, user)
    try:
        await planto3d.delete(job_id)  # 409 while it is being built
    except Plan3dError as e:
        raise _http_error(e) from e
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
async def embedded(token: str, path: str, request: Request, planto3d: Service) -> Response:
    try:
        claims = service.embed_claims(token)
    except TokenError as refused:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "This link has expired. Please reload the page."
        ) from refused

    limit = service.embed_request_limit(request.method, path, claims.get("job"))
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

    try:
        upstream = await planto3d.http.send(
            planto3d.http.build_request(
                request.method,
                # the query goes on as it came: the pages read it themselves
                httpx.URL("/" + path, query=request.url.query.encode("ascii")),
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
