"""Material finder API, mounted at /api/v1/ai/material-analysis (see ai/router.py).

POST /                      multipart: 1-4 images, focus, optional space -> {report_id, job_id}
GET  /jobs/{job_id}         job state with all events so far
GET  /jobs/{job_id}/events  SSE progress (replays, then live)
GET  /{report_id}           materials, latest report, chat history
POST /{report_id}/recalculate   new size / wastage / coverage -> new report (no vision call)
POST /{report_id}/chat      multipart: message (+ optional plan file) -> answer / question / job

Sessions and jobs belong to the user who made them; other users get 404.
Identification and quantities only: there is no money anywhere in this API.
"""

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response, StreamingResponse
from pydantic import ValidationError

from app.core.security import AuthenticatedUser, get_current_user
from app.modules.ai.jobs_common import stream_events
from app.modules.ai.llm.client import GeminiClient, LLMClient, VisionLLMClient, api_key
from app.modules.ai.material_agent import service
from app.modules.ai.material_agent.jobs import JobManager, get_jobs
from app.modules.ai.material_agent.plan_upload import default_parser
from app.modules.ai.material_agent.projects import (
    MemoryProjectSource,
    ProjectSource,
    SupabaseProjectSource,
)
from app.modules.ai.material_agent.schemas import (
    AnalysisCreated,
    ChatReply,
    JobState,
    ManualSpace,
    RecalculateRequest,
    SessionSummary,
    SessionView,
)
from app.modules.ai.material_agent.settings import get_settings
from app.modules.ai.material_agent.store import SessionStore, get_store

logger = logging.getLogger("construtiva.ai.material.api")
router = APIRouter(tags=["material-analysis"])


def get_vision_llm() -> VisionLLMClient | None:
    key = api_key()
    if not key:
        return None
    s = get_settings()
    return GeminiClient(
        model=s.vision_model,
        fallback_model=s.vision_fallback_model,
        thinking=s.vision_thinking,
        fallback_timeout_s=s.fallback_timeout_s,
        temperature=0.1,
        timeout_s=s.llm_timeout_s,
        api_key=key,
    )


def get_text_llm() -> LLMClient | None:
    key = api_key()
    if not key:
        return None
    s = get_settings()
    return GeminiClient(
        model=s.text_model,
        fallback_model=s.text_fallback_model,
        temperature=0.1,
        timeout_s=s.text_timeout_s,
        fallback_timeout_s=s.text_timeout_s,
        api_key=key,
        thinking="low",
    )


_projects: ProjectSource | None = None


def get_projects() -> ProjectSource:
    global _projects
    if _projects is None:
        import os

        from app.core.config import settings

        configured = settings.supabase_url and settings.supabase_service_role_key
        _projects = (
            SupabaseProjectSource()
            if configured and os.environ.get("TESTING") != "1"
            else MemoryProjectSource()
        )
    return _projects


def get_deps(
    store: Annotated[SessionStore, Depends(get_store)],
    jobs: Annotated[JobManager, Depends(get_jobs)],
    projects: Annotated[ProjectSource, Depends(get_projects)],
    vision_llm: Annotated[VisionLLMClient | None, Depends(get_vision_llm)],
    text_llm: Annotated[LLMClient | None, Depends(get_text_llm)],
) -> service.Deps:
    import os

    return service.Deps(
        store=store,
        jobs=jobs,
        projects=projects,
        vision_llm=vision_llm,
        text_llm=text_llm,
        plan_parser=default_parser,
        vision_model=get_settings().vision_model,
        store_files=os.environ.get("TESTING") != "1",
    )


User = Annotated[AuthenticatedUser, Depends(get_current_user)]
Deps = Annotated[service.Deps, Depends(get_deps)]


def _own(deps: service.Deps, sid: str, user: AuthenticatedUser):
    s = service.own_session(deps, sid, user.id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
    return s


def _own_job(deps: service.Deps, job_id: str, user: AuthenticatedUser):
    job = deps.jobs.get(job_id)
    if job is None or job.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


@router.post("", response_model=AnalysisCreated, status_code=status.HTTP_202_ACCEPTED)
async def create_analysis(
    user: User,
    deps: Deps,
    images: Annotated[list[UploadFile], File(description="1-4 photos (JPG, PNG, WEBP)")],
    focus_areas: Annotated[
        str, Form(description="Comma-separated surfaces, e.g. 'wall,floor'")
    ] = "",
    focus: Annotated[
        str,
        Form(
            max_length=500,
            description="The prompt, e.g. 'analyze this interior design' or 'TV wall 12 x 10 ft'",
        ),
    ] = "",
    space: Annotated[str, Form(description="Optional ManualSpace as JSON")] = "",
    project_id: Annotated[str, Form(max_length=64)] = "",
    room: Annotated[str, Form(max_length=60)] = "",
) -> AnalysisCreated:
    manual = None
    if space.strip():
        try:
            manual = ManualSpace.model_validate(json.loads(space))
        except (ValueError, ValidationError) as e:
            raise HTTPException(422, f"Invalid space: {str(e)[:300]}") from e
    uploads = [
        service.Upload(
            data=await f.read(), mime=(f.content_type or "").split(";")[0], name=f.filename or ""
        )
        for f in images
    ]
    areas = [a.strip().lower() for a in focus_areas.split(",") if a.strip()]
    try:
        session, job = await run_in_threadpool(
            service.start_analysis,
            deps,
            user.id,
            uploads,
            areas,
            focus,
            manual,
            project_id or None,
            room,
        )
    except service.ServiceError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return AnalysisCreated(report_id=session.id, job_id=job.id)


@router.get("/jobs/{job_id}", response_model=JobState)
async def job_state(job_id: str, user: User, deps: Deps) -> JobState:
    return _own_job(deps, job_id, user).state()


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, user: User, deps: Deps) -> StreamingResponse:
    job = _own_job(deps, job_id, user)
    return StreamingResponse(
        stream_events(job),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("", response_model=list[SessionSummary])
async def list_analyses(user: User, deps: Deps) -> list[SessionSummary]:
    """History: the user's earlier analyses, newest first."""
    try:
        rows = await run_in_threadpool(deps.store.list_for, user.id)
    except Exception as e:
        logger.error("listing material sessions failed: %s", e)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Your earlier analyses could not be loaded right now. Please try again.",
        ) from e
    return [SessionSummary.model_validate(r) for r in rows]


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analysis(report_id: str, user: User, deps: Deps) -> Response:
    try:
        deleted = await run_in_threadpool(deps.store.delete, report_id, user.id)
    except Exception as e:
        logger.error("deleting material session failed: %s", e)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The analysis could not be deleted right now."
        ) from e
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{report_id}/image")
async def analysis_image(report_id: str, user: User, deps: Deps, n: int = 0) -> Response:
    """The analysed photo (downscaled copy kept by the server), for reopened sessions."""
    from app.modules.ai.material_agent import vision

    s = await run_in_threadpool(_own, deps, report_id, user)
    if not 0 <= n < len(s.image_hashes):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No photo kept for this analysis")
    data = await run_in_threadpool(vision.load_image, s.image_hashes[n])
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No photo kept for this analysis")
    return Response(
        content=data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"}
    )


@router.get("/{report_id}", response_model=SessionView)
async def get_analysis(report_id: str, user: User, deps: Deps) -> SessionView:
    return service.view(await run_in_threadpool(_own, deps, report_id, user))


@router.post("/{report_id}/recalculate", response_model=SessionView)
async def recalculate(
    report_id: str, body: RecalculateRequest, user: User, deps: Deps
) -> SessionView:
    s = await run_in_threadpool(_own, deps, report_id, user)
    try:
        s = await run_in_threadpool(service.recalculate, deps, s, body)
    except service.ServiceError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return service.view(s)


@router.post("/{report_id}/chat", response_model=ChatReply)
async def chat(
    report_id: str,
    user: User,
    deps: Deps,
    message: Annotated[str, Form(max_length=2000)] = "",
    file: Annotated[
        UploadFile | None, File(description="Optional floor plan: PDF, PNG or JPG")
    ] = None,
) -> ChatReply:
    s = await run_in_threadpool(_own, deps, report_id, user)
    upload = None
    if file is not None and file.filename:
        upload = service.Upload(
            data=await file.read(), mime=(file.content_type or "").split(";")[0], name=file.filename
        )
    if not message.strip() and upload is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Type a message or attach a plan.")
    return await run_in_threadpool(service.chat, deps, s, message, upload)
