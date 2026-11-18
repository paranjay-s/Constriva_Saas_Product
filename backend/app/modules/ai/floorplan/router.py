"""Floor plan API, mounted at /api/v1/ai/floorplans (see ai/router.py).

POST /brief/parse            form + description -> Brief for the confirmation card
GET  ?project_id=            the user's floor plans (summaries), optionally of one project
POST /generate               confirmed Brief + project -> {job_id} (runs in the background)
GET  /jobs/{job_id}          current job state with all events so far
GET  /jobs/{job_id}/events   SSE stream of progress events (replays, then live)
GET  /{plan_id}              plan JSON + SVG + chat history
POST /{plan_id}/edit         chat edit -> new version (or why not)
POST /{plan_id}/revert       undo / go back to an earlier version
GET  /{plan_id}/export       ?format=svg|pdf|png|dxf[&dpi=]

Every plan and job belongs to the user who made it; other users get 404. A plan is
always made inside one of the user's own projects (so it shows in their project list).
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response, StreamingResponse

from app.core.security import AuthenticatedUser, clean_uuid, get_current_user
from app.modules.ai.floorplan import service
from app.modules.ai.floorplan.jobs import JobManager, get_jobs, stream_events
from app.modules.ai.floorplan.pipeline.brief_parser import missing_required
from app.modules.ai.floorplan.render.exports import ExportFormat, export_plan
from app.modules.ai.floorplan.schemas.api import (
    EditRequest,
    EditResponse,
    FloorplanSummary,
    GenerateRequest,
    JobCreated,
    JobState,
    ParseBriefRequest,
    ParseBriefResponse,
    PlanResponse,
    RevertRequest,
)
from app.modules.ai.floorplan.store import PlanStore, StoredPlan, _use_memory, get_store
from app.modules.ai.llm.client import LLMClient, LLMError, get_llm

logger = logging.getLogger("construtiva.ai.floorplan.api")
router = APIRouter(tags=["floorplans"])


def get_floorplan_llm() -> LLMClient | None:
    """The configured LLM, or None (the form alone is used; chat edits are refused)."""
    try:
        return get_llm()
    except LLMError as e:
        logger.warning("floor plan LLM unavailable: %s", e)
        return None


NO_PROJECT = "Create or choose a project first; every floor plan is saved inside a project."


def get_project_checker():
    """(project_id, user_id) -> True if the project exists and belongs to the user.

    Uses the service client scoped by user_id (same as the projects API). Without a
    database (memory mode) any well-formed project id is accepted."""
    if _use_memory():
        return lambda project_id, user_id: True

    def check(project_id: str, user_id: str) -> bool:
        from app.core.supabase import get_supabase_client

        try:
            res = (
                get_supabase_client()
                .table("projects")
                .select("id")
                .eq("id", project_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
        except Exception as e:
            logger.error("project check failed: %s", e)
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "The project database is not reachable right now. Please try again.",
            ) from e
        return bool(res.data)

    return check


User = Annotated[AuthenticatedUser, Depends(get_current_user)]
ProjectChecker = Annotated[object, Depends(get_project_checker)]
Llm = Annotated[LLMClient | None, Depends(get_floorplan_llm)]
Store = Annotated[PlanStore, Depends(get_store)]
Jobs = Annotated[JobManager, Depends(get_jobs)]


def _own_plan(store: PlanStore, plan_id: str, user: AuthenticatedUser) -> StoredPlan:
    sp = store.get(plan_id)
    if sp is None or sp.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Floor plan not found")
    return sp


def _own_job(jobs: JobManager, job_id: str, user: AuthenticatedUser):
    job = jobs.get(job_id)
    if job is None or job.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


@router.post("/brief/parse", response_model=ParseBriefResponse)
async def parse_brief_endpoint(
    payload: ParseBriefRequest,
    user: User,
    llm: Llm,
) -> ParseBriefResponse:
    return await run_in_threadpool(service.parse, payload, llm)


@router.post("/generate", response_model=JobCreated, status_code=status.HTTP_202_ACCEPTED)
async def generate_endpoint(
    payload: GenerateRequest,
    user: User,
    llm: Llm,
    store: Store,
    jobs: Jobs,
    owns_project: ProjectChecker,
) -> JobCreated:
    project_id = clean_uuid(payload.project_id)
    if not project_id:
        raise HTTPException(422, NO_PROJECT)
    if not await run_in_threadpool(owns_project, project_id, user.id):
        raise HTTPException(404, "That project was not found in your account. " + NO_PROJECT)
    missing = missing_required(payload.brief)
    if missing:
        raise HTTPException(422, "Missing before generating: " + ", ".join(missing))
    job = jobs.submit(
        user.id,
        lambda j: service.run_generation(j, payload.brief, project_id, llm, store),
    )
    return JobCreated(job_id=job.id)


@router.get("", response_model=list[FloorplanSummary])
async def list_plans(
    user: User,
    store: Store,
    project_id: Annotated[str | None, Query(max_length=64)] = None,
) -> list[FloorplanSummary]:
    pid = clean_uuid(project_id) if project_id else None
    if project_id and not pid:
        return []
    try:
        return await run_in_threadpool(service.list_plans, store, user.id, pid)
    except Exception as e:
        logger.error("listing floor plans failed: %s", e)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Floor plans could not be loaded right now. Please try again.",
        ) from e


@router.get("/jobs/{job_id}", response_model=JobState)
async def job_state(
    job_id: str,
    user: User,
    jobs: Jobs,
) -> JobState:
    return _own_job(jobs, job_id, user).state()


@router.get("/jobs/{job_id}/events")
async def job_events(
    job_id: str,
    user: User,
    jobs: Jobs,
) -> StreamingResponse:
    job = _own_job(jobs, job_id, user)
    return StreamingResponse(
        stream_events(job),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: str,
    user: User,
    store: Store,
) -> PlanResponse:
    sp = await run_in_threadpool(_own_plan, store, plan_id, user)
    return await run_in_threadpool(service.to_response, sp)


@router.post("/{plan_id}/edit", response_model=EditResponse)
async def edit_endpoint(
    plan_id: str,
    payload: EditRequest,
    user: User,
    llm: Llm,
    store: Store,
) -> EditResponse:
    sp = await run_in_threadpool(_own_plan, store, plan_id, user)
    if payload.version is not None and payload.version != sp.version:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"The plan changed (now version {sp.version}). Reload it and try again.",
        )
    return await run_in_threadpool(service.edit, sp, payload, llm, store)


@router.post("/{plan_id}/revert", response_model=EditResponse)
async def revert_endpoint(
    plan_id: str,
    payload: RevertRequest,
    user: User,
    store: Store,
) -> EditResponse:
    sp = await run_in_threadpool(_own_plan, store, plan_id, user)
    return await run_in_threadpool(service.restore, sp, payload.version, store)


@router.get("/{plan_id}/export")
async def export_endpoint(
    plan_id: str,
    user: User,
    store: Store,
    format: Annotated[ExportFormat, Query()] = "svg",
    dpi: Annotated[int, Query(ge=50, le=600)] = 150,
) -> Response:
    sp = await run_in_threadpool(_own_plan, store, plan_id, user)
    exp = await run_in_threadpool(export_plan, sp.plan, format, dpi=dpi, version=sp.version)
    return Response(
        content=exp.data,
        media_type=exp.media_type,
        headers={"Content-Disposition": f'attachment; filename="{exp.filename}"'},
    )
