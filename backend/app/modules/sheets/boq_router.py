"""BOQ endpoints, mounted at /api/v1/sheets/boq.

POST /                       multipart `file` (PDF, within the upload limits) -> 202 {job_id}
GET  /jobs/{job_id}          job state with every event so far
GET  /jobs/{job_id}/events   SSE progress (replays, then live): uploading, parsing, calculating
GET  /jobs/{job_id}/result   the BOQ once the job is done
POST /export/pdf             the rows of a result -> PDF
POST /export/xlsx            the rows of a result -> Excel

A job belongs to the user who started it; anyone else gets 404.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response, StreamingResponse

from app.core.security import AuthenticatedUser, get_current_user
from app.modules.ai.jobs_common import stream_events
from app.modules.parsing.service import read_plan_upload
from app.modules.sheets.boq_export import (
    PDF_MIME,
    XLSX_MIME,
    build_boq_pdf,
    build_boq_xlsx,
    export_filename,
)
from app.modules.sheets.boq_jobs import BoqJob, BoqJobManager, get_boq_jobs
from app.modules.sheets.boq_schemas import BoqExportRequest, BoqJobCreated, BoqJobState
from app.modules.sheets.boq_service import PlanPdfParser, default_pdf_parser, start_boq_job

router = APIRouter()


def get_pdf_parser() -> PlanPdfParser:
    return default_pdf_parser


User = Annotated[AuthenticatedUser, Depends(get_current_user)]
Jobs = Annotated[BoqJobManager, Depends(get_boq_jobs)]
Parser = Annotated[PlanPdfParser, Depends(get_pdf_parser)]


def _own_job(jobs: BoqJobManager, job_id: str, user: AuthenticatedUser) -> BoqJob:
    job = jobs.get(job_id)
    if job is None or job.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "BOQ job not found")
    return job


@router.post(
    "",
    response_model=BoqJobCreated,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a floor plan PDF and start its bill of quantities",
)
async def start_boq(
    user: User,
    jobs: Jobs,
    parse_pdf: Parser,
    file: Annotated[UploadFile, File(description="Floor plan PDF")],
) -> BoqJobCreated:
    # The same check as the 2D-to-3D import: PDF only, within the size and page limits.
    # A rejected upload starts no job and never reaches a model.
    try:
        pdf_bytes = await read_plan_upload(file)
    except ValueError as rejected:
        raise HTTPException(
            getattr(rejected, "http_status", status.HTTP_400_BAD_REQUEST), str(rejected)
        ) from rejected
    job = start_boq_job(jobs, user.id, file.filename or "plan.pdf", pdf_bytes, parse_pdf)
    return BoqJobCreated(job_id=job.id)


@router.get("/jobs/{job_id}", response_model=BoqJobState, summary="BOQ job state")
async def boq_job_state(job_id: str, user: User, jobs: Jobs) -> BoqJobState:
    return _own_job(jobs, job_id, user).state()


@router.get("/jobs/{job_id}/events", summary="BOQ job progress (SSE)")
async def boq_job_events(job_id: str, user: User, jobs: Jobs) -> StreamingResponse:
    job = _own_job(jobs, job_id, user)
    return StreamingResponse(
        stream_events(job),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/jobs/{job_id}/result", summary="The bill of quantities of a finished job")
async def boq_job_result(job_id: str, user: User, jobs: Jobs) -> dict[str, Any]:
    job = _own_job(jobs, job_id, user)
    if job.status == "failed":
        raise HTTPException(status.HTTP_409_CONFLICT, job.error or "The BOQ could not be prepared.")
    if job.result is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "The BOQ is not ready yet.")
    return job.result


def _file_response(content: bytes, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content)),
        },
    )


@router.post("/export/pdf", summary="Download a BOQ as PDF")
async def export_boq_pdf(payload: BoqExportRequest, user: User) -> Response:
    data = payload.model_dump()
    pdf = build_boq_pdf(
        data["items"], data["warnings"], data["geometry_summary"], data["project_metadata"]
    )
    return _file_response(pdf, PDF_MIME, export_filename(data["project_metadata"], "pdf"))


@router.post("/export/xlsx", summary="Download a BOQ as Excel")
async def export_boq_xlsx(payload: BoqExportRequest, user: User) -> Response:
    data = payload.model_dump()
    xlsx = build_boq_xlsx(
        data["items"], data["warnings"], data["geometry_summary"], data["project_metadata"]
    )
    return _file_response(xlsx, XLSX_MIME, export_filename(data["project_metadata"], "xlsx"))
