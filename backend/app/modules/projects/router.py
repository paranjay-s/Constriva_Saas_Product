"""
=============================================================================
Construtiva Projects Management API Router
=============================================================================
File: app/modules/projects/router.py
Purpose:
  CRUD REST endpoints for building/property projects:
  - POST   /api/v1/projects: Create a new project.
  - GET    /api/v1/projects: List all projects for current user.
  - GET    /api/v1/projects/all: Get all projects enriched with active 3D plans & total count.
  - GET    /api/v1/projects/{project_id}: Get project details and active plan reference.
  - PUT    /api/v1/projects/{project_id}: Edit project title, description, or status.
  - PATCH  /api/v1/projects/{project_id}: Partial inline edit of project attributes.
  - DELETE /api/v1/projects/{project_id}: Delete a project (cascades plans, files, sheets).

How access works: get_current_user has already verified the person (signature + expiry),
so the database is used through the service client and EVERY query is scoped to that
person's user_id here. This does not depend on a user token reaching the database, so an
expiring session can no longer surface as a row-level security error, and one user can
never read, change or delete another user's project.

If the database cannot be reached, the endpoint returns HTTP 503 with a clear message
instead of pretending (an in-memory "saved" project vanished on restart and broke later
steps such as uploads and plans).
=============================================================================
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import AuthenticatedUser, clean_uuid, get_current_user, resolve_project_uuid
from app.core.supabase import get_supabase_client
from app.modules.projects.schemas import (
    CreateProjectRequest,
    DeleteProjectResponse,
    ProjectListResponse,
    ProjectResponse,
    UpdateProjectRequest,
)

logger = logging.getLogger("construtiva.projects")
router = APIRouter()

# Kept for the parsing module, which records projects it auto-creates while the database is
# unreachable. The projects API itself no longer serves from it.
FALLBACK_PROJECTS: Dict[str, Dict[str, Any]] = {}

DB_UNAVAILABLE = "The project database is not reachable right now. Please try again in a moment."


def _db_error(action: str, e: Exception) -> HTTPException:
    logger.error(f"Project {action} failed: {e}")
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=DB_UNAVAILABLE)


def _active_plan(supabase, project_id: str) -> Optional[Dict[str, Any]]:
    try:
        res = (
            supabase.table("plans")
            .select("id, name, status, created_at, overall_confidence")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        logger.warning(f"Could not read the active plan of project {project_id}: {e}")
        return None


def _own_project(supabase, project_id: str, user_id: str) -> Dict[str, Any]:
    """The project if it belongs to the user, else 404 (no hint whether it exists)."""
    try:
        res = (
            supabase.table("projects")
            .select("*")
            .eq("id", project_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as e:
        raise _db_error("read", e) from e
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return res.data[0]


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new construction/property project",
)
async def create_project(
    payload: CreateProjectRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Creates a project owned by the signed-in user."""
    supabase = get_supabase_client()
    row = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "name": payload.name,
        "description": payload.description,
        "status": payload.status or "active",
    }
    try:
        res = supabase.table("projects").insert(row).execute()
    except Exception as e:
        raise _db_error("create", e) from e
    if not res.data:
        raise _db_error("create", RuntimeError("insert returned no row"))
    logger.info(f"Project created: {payload.name} ({row['id']}) for user {current_user.id}")
    return res.data[0]


@router.get(
    "",
    response_model=List[ProjectResponse],
    summary="List all projects for the current user",
)
async def list_projects(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """The signed-in user's projects, newest first (never another user's)."""
    supabase = get_supabase_client()
    try:
        res = (
            supabase.table("projects")
            .select("*")
            .eq("user_id", current_user.id)
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as e:
        raise _db_error("list", e) from e
    return res.data or []


@router.get(
    "/all",
    response_model=ProjectListResponse,
    summary="Get all projects with active plan details and total count",
)
async def get_all_projects(
    status: Optional[str] = None,  # existing query parameter name (shadows the module here)
    limit: int = 100,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """The user's projects with their latest plan, optionally filtered by status."""
    wanted = status
    supabase = get_supabase_client()
    try:
        query = supabase.table("projects").select("*").eq("user_id", current_user.id)
        if wanted:
            query = query.eq("status", wanted)
        res = query.order("created_at", desc=True).limit(max(1, min(limit, 500))).execute()
    except Exception as e:
        raise _db_error("list", e) from e
    projects = res.data or []
    for p in projects:
        p["active_plan"] = _active_plan(supabase, p["id"])
    return ProjectListResponse(projects=projects, total_count=len(projects))


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project details by project ID",
)
async def get_project(
    project_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Project details with the active plan reference (404 if not the user's)."""
    supabase = get_supabase_client()
    project = _own_project(supabase, resolve_project_uuid(project_id), current_user.id)
    project["active_plan"] = _active_plan(supabase, project["id"])
    return project


@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Edit / update project details",
)
@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Edit / update project details (partial update)",
)
async def update_project(
    project_id: str,
    payload: UpdateProjectRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Updates name, description or status of one of the user's projects."""
    clean_pid = clean_uuid(project_id)
    if not clean_pid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID: '{project_id}' is not a valid project UUID.",
        )
    update_fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No update fields provided in request body.",
        )
    supabase = get_supabase_client()
    _own_project(supabase, clean_pid, current_user.id)
    try:
        res = (
            supabase.table("projects")
            .update(update_fields)
            .eq("id", clean_pid)
            .eq("user_id", current_user.id)
            .execute()
        )
    except Exception as e:
        raise _db_error("update", e) from e
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    logger.info(f"Project {clean_pid} updated: {list(update_fields)}")
    return res.data[0]


@router.delete(
    "/{project_id}",
    response_model=DeleteProjectResponse,
    summary="Delete a project",
)
async def delete_project(
    project_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Deletes one of the user's projects (database cascades plans, files, sheets)."""
    clean_pid = clean_uuid(project_id)
    if not clean_pid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID: '{project_id}' is not a valid project UUID.",
        )
    supabase = get_supabase_client()
    _own_project(supabase, clean_pid, current_user.id)
    try:
        supabase.table("projects").delete().eq("id", clean_pid).eq(
            "user_id", current_user.id
        ).execute()
    except Exception as e:
        raise _db_error("delete", e) from e
    logger.info(f"Project {clean_pid} deleted by user {current_user.id}")
    return DeleteProjectResponse(
        deleted=True,
        project_id=clean_pid,
        message="Project and all associated resources deleted successfully.",
    )
