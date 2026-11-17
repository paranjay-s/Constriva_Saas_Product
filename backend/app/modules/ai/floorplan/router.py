"""Floor plan API, mounted at /api/v1/ai/floorplans (see ai/router.py).

POST /brief/parse            form + description -> Brief for the confirmation card
POST /generate               confirmed Brief -> {job_id} (runs in the background)
GET  /jobs/{job_id}          current job state with all events so far
GET  /jobs/{job_id}/events   SSE stream of progress events (replays, then live)
GET  /{plan_id}              plan JSON + SVG + chat history
POST /{plan_id}/edit         chat edit -> new version (or why not)
GET  /{plan_id}/export       ?format=svg|pdf|png|dxf[&dpi=]

Every plan and job belongs to the user who made it; other users get 404.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response, StreamingResponse

from app.core.security import AuthenticatedUser, get_current_user
from app.modules.ai.floorplan import service
from app.modules.ai.floorplan.jobs import JobManager, get_jobs, stream_events
from app.modules.ai.floorplan.pipeline.brief_parser import missing_required
from app.modules.ai.floorplan.render.exports import ExportFormat, export_plan
from app.modules.ai.floorplan.schemas.api import (
    EditRequest,
    EditResponse,
    GenerateRequest,
    JobCreated,
    JobState,
    ParseBriefRequest,
    ParseBriefResponse,
    PlanResponse,
)
from app.modules.ai.floorplan.store import PlanStore, StoredPlan, get_store
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


User = Annotated[AuthenticatedUser, Depends(get_current_user)]
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
) -> JobCreated:
    missing = missing_required(payload.brief)
    if missing:
        raise HTTPException(422, "Missing before generating: " + ", ".join(missing))
    job = jobs.submit(
        user.id,
        lambda j: service.run_generation(j, payload.brief, payload.project_id, llm, store),
    )
    return JobCreated(job_id=job.id)


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


@router.get("/{plan_id}/export")
async def export_endpoint(
    plan_id: str,
    user: User,
    store: Store,
    format: Annotated[ExportFormat, Query()] = "svg",
    dpi: Annotated[int, Query(ge=50, le=600)] = 150,
) -> Response:
    sp = await run_in_threadpool(_own_plan, store, plan_id, user)
    exp = await run_in_threadpool(export_plan, sp.plan, format, dpi=dpi)
    return Response(
        content=exp.data,
        media_type=exp.media_type,
        headers={"Content-Disposition": f'attachment; filename="{exp.filename}"'},
    )
