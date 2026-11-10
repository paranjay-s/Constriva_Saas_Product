"""
=============================================================================
Construtiva 2D Blueprint Parsing & SSE Progress Streaming API Router
=============================================================================
File: app/modules/parsing/router.py
Purpose:
  Provides endpoints for uploading and converting 2D floor plan PDFs into 3D PlanJSON:
  - POST /api/v1/parsing/process: Upload PDF blueprint, rasterize to 300 DPI PNG, extract geometry.
  - GET  /api/v1/parsing/stream/{task_id}: Server-Sent Events (SSE) streaming real-time progress.
  - GET  /api/v1/parsing/{project_id}/plan: Retrieve the active PlanJSON for the 3D Three.js viewer.
=============================================================================
"""

import json
import uuid
import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from app.core.supabase import get_supabase_client
from app.core.security import get_current_user, AuthenticatedUser, clean_uuid
from app.modules.parsing.service import ParsingService

logger = logging.getLogger("construtiva.parsing.router")
router = APIRouter()


def get_or_create_default_project(user_id: str, filename: Optional[str] = None) -> str:
    """
    Finds the user's latest project or auto-creates a default project so blueprint
    uploads in Swagger UI (with placeholder 'string') never fail UUID validation.
    """
    supabase = get_supabase_client()
    try:
        res = (
            supabase.table("projects")
            .select("id")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]["id"]

        new_id = str(uuid.uuid4())
        safe_title = filename.replace(".pdf", "").replace("_", " ").title() if filename else "Default Property"
        supabase.table("projects").insert({
            "id": new_id,
            "user_id": user_id,
            "name": f"Project: {safe_title}",
            "project_type": "Residential",
            "status": "active",
        }).execute()
        return new_id
    except Exception as e:
        logger.warning(f"Could not resolve or auto-create project for user {user_id}: {e}")
        return str(uuid.uuid4())


@router.post(
    "/process",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload architectural PDF blueprint and trigger 3D extraction"
)
async def process_blueprint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Architectural floor plan PDF document"),
    project_id: Optional[str] = Form(None, description="UUID of the parent project (optional: auto-created if omitted)"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Accepts a 2D architectural PDF blueprint, initializes a progress tracking job,
    and runs the conversion pipeline in the background.

    Args:
        file (UploadFile): PDF floor plan.
        project_id (Optional[str]): Target project UUID. If omitted or 'string', auto-resolves a project.
        current_user (AuthenticatedUser): Authenticated user session.

    Returns:
        dict: task_id, status, and SSE stream URL to listen to progress.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded document must be in PDF format (.pdf)."
        )

    try:
        pdf_bytes = await file.read()
        if len(pdf_bytes) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

        # Cleanse project_id (handles Swagger UI default placeholder 'string')
        target_project_id = clean_uuid(project_id)
        if not target_project_id:
            target_project_id = get_or_create_default_project(current_user.id, file.filename)

        task_id = str(uuid.uuid4())
        supabase = get_supabase_client()

        # Initialize job record in Supabase 'jobs' table
        supabase.table("jobs").insert({
            "id": task_id,
            "project_id": target_project_id,
            "user_id": current_user.id,
            "type": "parse_plan",
            "status": "queued",
            "progress": 0,
            "step": "Queueing architectural PDF blueprint for analysis...",
            "input": {"filename": file.filename, "size_bytes": len(pdf_bytes)},
        }).execute()

        # Dispatch to Celery + Redis worker if available, otherwise fallback to in-process BackgroundTasks
        dispatched_to_celery = False
        try:
            from app.workers.tasks.parse_plan import process_blueprint_task
            process_blueprint_task.apply_async(
                args=[pdf_bytes.hex(), file.filename, target_project_id, current_user.id, task_id],
                queue="parsing"
            )
            dispatched_to_celery = True
            logger.info(f"Task {task_id} successfully queued on Celery 'parsing' queue via Redis.")
        except Exception as queue_err:
            logger.info(f"Celery worker queue unavailable ({queue_err}). Falling back to FastAPI BackgroundTasks.")

        if not dispatched_to_celery:
            background_tasks.add_task(
                ParsingService.process_blueprint_pdf,
                pdf_bytes=pdf_bytes,
                filename=file.filename,
                project_id=target_project_id,
                user_id=current_user.id,
                job_id=task_id,
            )

        return {
            "task_id": task_id,
            "project_id": target_project_id,
            "status": "queued",
            "stream_url": f"/api/v1/parsing/stream/{task_id}",
            "message": "Blueprint upload received. Connect to SSE stream_url for real-time progress.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initiate blueprint processing: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/stream/{task_id}",
    summary="Subscribe to Server-Sent Events (SSE) for blueprint extraction progress"
)
async def stream_parsing_progress(task_id: str):
    """
    Streams Server-Sent Events (SSE) reporting the real-time progress of a parsing job
    (0% to 100%) to drive the frontend upload progress bar.

    Args:
        task_id (str): UUID of the background parsing job.
    """
    supabase = get_supabase_client()

    async def event_generator():
        last_progress = -1
        retry_count = 0

        while True:
            try:
                res = supabase.table("jobs").select("*").eq("id", task_id).execute()
                if not res.data:
                    yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"
                    break

                job = res.data[0]
                progress = job.get("progress", 0)
                step = job.get("step", "")
                status_val = job.get("status", "running")

                if progress != last_progress or status_val in ("done", "failed"):
                    last_progress = progress
                    payload = {
                        "task_id": task_id,
                        "status": status_val,
                        "progress": progress,
                        "step": step,
                        "result": job.get("result"),
                    }

                    if status_val == "done":
                        yield f"event: complete\ndata: {json.dumps(payload)}\n\n"
                        break
                    elif status_val == "failed":
                        yield f"event: failed\ndata: {json.dumps(payload)}\n\n"
                        break
                    else:
                        yield f"event: progress\ndata: {json.dumps(payload)}\n\n"

                await asyncio.sleep(0.7)

            except Exception as e:
                logger.error(f"SSE stream error on job {task_id}: {e}")
                retry_count += 1
                if retry_count > 5:
                    yield f"event: error\ndata: {json.dumps({'error': 'Lost connection to job updates'})}\n\n"
                    break
                await asyncio.sleep(1.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get(
    "/{project_id}/plan",
    summary="Retrieve active PlanJSON for 3D Three.js viewer"
)
async def get_project_plan(
    project_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Fetches the active architectural PlanJSON (walls, doors, windows, room polygons)
    for a given project to render in the Three.js 3D workspace.

    Args:
        project_id (str): Project UUID.

    Returns:
        dict: Complete PlanJSON object.
    """
    supabase = get_supabase_client()

    try:
        res = (
            supabase.table("plans")
            .select("id, name, plan_json, status, created_at, overall_confidence")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if not res.data:
            # Fallback to default verified plan if no custom plan exists yet
            from app.modules.parsing.service import DEFAULT_VERIFIED_PLAN
            return {
                "id": "default_verified_plan",
                "project_id": project_id,
                "plan_json": DEFAULT_VERIFIED_PLAN,
                "is_fallback": True,
            }

        row = res.data[0]
        return {
            "id": row["id"],
            "project_id": project_id,
            "name": row["name"],
            "plan_json": row["plan_json"],
            "status": row["status"],
            "overall_confidence": row.get("overall_confidence", 0.95),
            "is_fallback": False,
        }

    except Exception as e:
        logger.error(f"Error fetching plan for project {project_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
