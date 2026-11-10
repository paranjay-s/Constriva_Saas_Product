"""
=============================================================================
Construtiva Projects Management API Router
=============================================================================
File: app/modules/projects/router.py
Purpose:
  Provides comprehensive CRUD REST endpoints for building/property projects:
  - POST   /api/v1/projects: Create a new project.
  - GET    /api/v1/projects: List all projects for current user.
  - GET    /api/v1/projects/all: Get all projects enriched with active 3D plans & total count.
  - GET    /api/v1/projects/{project_id}: Get project details and active plan reference.
  - PUT    /api/v1/projects/{project_id}: Edit project title, description, or status.
  - PATCH  /api/v1/projects/{project_id}: Partial inline edit of project attributes.
  - DELETE /api/v1/projects/{project_id}: Delete a project (cascades plans, files, sheets).
=============================================================================
"""

import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status

from app.core.supabase import get_supabase_client
from app.core.security import get_current_user, AuthenticatedUser, clean_uuid
from app.modules.projects.schemas import (
    CreateProjectRequest,
    UpdateProjectRequest,
    ProjectResponse,
    ProjectListResponse,
    DeleteProjectResponse,
)

logger = logging.getLogger("construtiva.projects")
router = APIRouter()


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new construction/property project"
)
async def create_project(
    payload: CreateProjectRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Creates a new project record in the Supabase 'projects' table linked to the authenticated user.

    Args:
        payload (CreateProjectRequest): Project name, description, and status ('active' or 'archived').
        current_user (AuthenticatedUser): Authenticated user session.

    Returns:
        ProjectResponse: The created project row.
    """
    supabase = get_supabase_client()
    project_id = str(uuid.uuid4())

    try:
        new_row = {
            "id": project_id,
            "user_id": current_user.id,
            "name": payload.name,
            "description": payload.description,
            "status": payload.status or "active",
        }

        res = supabase.table("projects").insert(new_row).execute()
        if not res.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create project in database."
            )

        logger.info(f"Project created successfully: {payload.name} ({project_id}) for user {current_user.id}")
        return res.data[0]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create project: {str(e)}"
        )


@router.get(
    "",
    response_model=List[ProjectResponse],
    summary="List all projects for the current user"
)
async def list_projects(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Returns all projects created by the authenticated user, ordered from newest to oldest.

    Args:
        current_user (AuthenticatedUser): Authenticated user session.

    Returns:
        List[ProjectResponse]: Collection of user projects.
    """
    supabase = get_supabase_client()

    try:
        res = (
            supabase.table("projects")
            .select("*")
            .eq("user_id", current_user.id)
            .order("created_at", desc=True)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error(f"Failed to fetch projects for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not retrieve projects: {str(e)}"
        )


@router.get(
    "/all",
    response_model=ProjectListResponse,
    summary="Get all projects with active plan details and total count"
)
async def get_all_projects(
    status: Optional[str] = None,
    limit: int = 100,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieves all projects owned by the authenticated user, enriched with their
    active 3D architectural plan reference, with optional status filtering ('active', 'archived').

    Args:
        status (Optional[str]): Optional filter by status ('active' or 'archived').
        limit (int): Maximum records to retrieve (default 100).
        current_user (AuthenticatedUser): Authenticated user session.

    Returns:
        ProjectListResponse: Collection of enriched projects and total count.
    """
    supabase = get_supabase_client()

    try:
        query = supabase.table("projects").select("*").eq("user_id", current_user.id)
        if status:
            query = query.eq("status", status)

        res = query.order("created_at", desc=True).limit(limit).execute()
        raw_projects = res.data or []

        enriched_projects = []
        for p in raw_projects:
            pid = p["id"]
            plan_res = (
                supabase.table("plans")
                .select("id, name, status, created_at, overall_confidence")
                .eq("project_id", pid)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            p["active_plan"] = plan_res.data[0] if plan_res.data else None
            enriched_projects.append(p)

        return ProjectListResponse(
            projects=enriched_projects,
            total_count=len(enriched_projects)
        )

    except Exception as e:
        logger.error(f"Failed to fetch all projects: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not retrieve all projects: {str(e)}"
        )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project details by project ID"
)
async def get_project(
    project_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieves project details, including the active architectural PlanJSON reference if one exists.

    Args:
        project_id (str): UUID of the project.
        current_user (AuthenticatedUser): Authenticated user session.

    Returns:
        ProjectResponse: Project details and attached active plan.
    """
    clean_pid = clean_uuid(project_id)
    if not clean_pid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID: '{project_id}' is not a valid project UUID."
        )

    supabase = get_supabase_client()

    try:
        res = supabase.table("projects").select("*").eq("id", clean_pid).execute()
        if not res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found."
            )

        project = res.data[0]

        # Fetch active plan if present
        plan_res = (
            supabase.table("plans")
            .select("id, name, status, created_at, overall_confidence")
            .eq("project_id", clean_pid)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        project["active_plan"] = plan_res.data[0] if plan_res.data else None

        return project

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not retrieve project: {str(e)}"
        )


@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Edit / update project details"
)
@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Edit / update project details (partial update)"
)
async def update_project(
    project_id: str,
    payload: UpdateProjectRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Updates editable fields of a project (name, description, status).
    Supports both PUT and PATCH HTTP methods.

    Args:
        project_id (str): UUID of project to edit.
        payload (UpdateProjectRequest): Fields to update.
        current_user (AuthenticatedUser): Authenticated user session.

    Returns:
        ProjectResponse: Updated project record.
    """
    clean_pid = clean_uuid(project_id)
    if not clean_pid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID: '{project_id}' is not a valid project UUID."
        )

    supabase = get_supabase_client()

    update_fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No update fields provided in request body."
        )

    try:
        res = (
            supabase.table("projects")
            .update(update_fields)
            .eq("id", clean_pid)
            .execute()
        )
        if not res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found."
            )

        logger.info(f"Project {clean_pid} updated successfully: {list(update_fields.keys())}")
        return res.data[0]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not update project: {str(e)}"
        )


@router.delete(
    "/{project_id}",
    response_model=DeleteProjectResponse,
    summary="Delete a project"
)
async def delete_project(
    project_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Permanently deletes a project and cascades deletions across associated plans, files, and sheets.

    Args:
        project_id (str): UUID of project to delete.
        current_user (AuthenticatedUser): Authenticated user session.

    Returns:
        DeleteProjectResponse: Deletion confirmation.
    """
    clean_pid = clean_uuid(project_id)
    if not clean_pid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID: '{project_id}' is not a valid project UUID."
        )

    supabase = get_supabase_client()

    try:
        res = supabase.table("projects").delete().eq("id", clean_pid).execute()
        logger.info(f"Project {clean_pid} deleted by user {current_user.id}")
        return DeleteProjectResponse(
            deleted=True,
            project_id=clean_pid,
            message="Project and all associated resources deleted successfully."
        )

    except Exception as e:
        logger.error(f"Failed to delete project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not delete project: {str(e)}"
        )
