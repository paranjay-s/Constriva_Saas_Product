"""
=============================================================================
Construtiva 3D Plans API Router
=============================================================================
File: app/modules/plans/router.py
Purpose:
  Provides endpoints for reading and updating active architectural PlanJSON coordinates:
  - GET /api/v1/plans/{plan_id}: Retrieve plan by plan ID.
  - GET /api/v1/plans/project/{project_id}: Get latest active plan for project.
  - PUT /api/v1/plans/{plan_id}: Update plan_json geometry (triggers automatic sheet invalidation).
=============================================================================
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from app.core.supabase import get_supabase_client
from app.core.security import get_current_user, AuthenticatedUser, clean_uuid

logger = logging.getLogger("construtiva.plans")
router = APIRouter()


class UpdatePlanRequest(BaseModel):
    name: str = Field(None, description="Optional revised plan title")
    plan_json: Dict[str, Any] = Field(..., description="Full updated PlanJSON geometry object")


@router.get(
    "/{plan_id}",
    summary="Get plan by Plan ID"
)
async def get_plan(
    plan_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieves the PlanJSON for a given plan ID.
    """
    clean_id = clean_uuid(plan_id)
    if not clean_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")

    supabase = get_supabase_client()
    try:
        res = supabase.table("plans").select("*").eq("id", clean_id).execute()
        if not res.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")
        return res.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving plan {plan_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/project/{project_id}",
    summary="Get active plan for a project"
)
async def get_project_plan(
    project_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Returns the most recent active PlanJSON for the given project.
    """
    clean_proj_id = clean_uuid(project_id)
    if not clean_proj_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active plan found for project '{project_id}'."
        )

    supabase = get_supabase_client()
    try:
        res = (
            supabase.table("plans")
            .select("*")
            .eq("project_id", clean_proj_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active plan found for project {project_id}."
            )
        return res.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching plan for project {project_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put(
    "/{plan_id}",
    summary="Update PlanJSON geometry (triggers automatic sheet invalidation)"
)
async def update_plan(
    plan_id: str,
    payload: UpdatePlanRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Updates the plan_json coordinates for a plan.
    Note: The PostgreSQL database trigger `trg_plans_mark_sheets_stale` will automatically
    mark any related sheets as `stale = true` so they can be recalculated.
    """
    clean_id = clean_uuid(plan_id)
    if not clean_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")

    supabase = get_supabase_client()
    try:
        update_data = {"plan_json": payload.plan_json}
        if payload.name:
            update_data["name"] = payload.name

        res = supabase.table("plans").update(update_data).eq("id", clean_id).execute()
        if not res.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")

        logger.info(f"Updated PlanJSON for plan {plan_id}. Sheets marked stale by DB trigger.")
        return res.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating plan {plan_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
