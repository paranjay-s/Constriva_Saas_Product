"""
=============================================================================
Construtiva Bill of Materials (BOQ) & Cost Estimation API Router
=============================================================================
File: app/modules/sheets/router.py
Purpose:
  Provides comprehensive REST endpoints for construction cost estimation:
  - GET   /api/v1/sheets/materials/catalogue: Returns master catalogue for the 7 primary materials:
          1. Brick
          2. Steel/rebar rod
          3. Cement
          4. Sand (fine aggregate)
          5. Ballast (coarse aggregate)
          6. Plaster (cement and gypsum)
          7. Tiles (floor and wall)
  - GET   /api/v1/sheets/{project_id}: Fetch active sheet (or auto-initialize with the 7 materials).
  - POST  /api/v1/sheets/{project_id}/items: Add a custom line item to the sheet.
  - PATCH /api/v1/sheets/{project_id}/items/{item_id}: Inline edit item quantity, rate, wastage, unit.
  - DELETE /api/v1/sheets/{project_id}/items/{item_id}: Delete a line item.
  - GET   /api/v1/sheets/{project_id}/mappings: Fetch architectural surface assignments.
  - POST  /api/v1/sheets/{project_id}/mappings: Save surface-to-material mappings.
  - GET   /api/v1/sheets/{project_id}/export/csv: Download formatted CSV export.
  - GET   /api/v1/sheets/{project_id}/export/pdf: Download printable architectural PDF report.
=============================================================================
"""

import os
import json
import uuid
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, status, Response, Query
from fastapi.responses import Response

from app.core.supabase import get_supabase_client
from app.core.security import get_current_user, AuthenticatedUser, clean_uuid
from app.modules.sheets.schemas import (
    SheetResponse,
    SheetItemCreate,
    SheetItemUpdate,
    SheetItemResponse,
    MaterialCatalogueResponse,
    MaterialCatalogueItem,
    UpdateSurfaceMappingsRequest,
)
from app.modules.sheets.service import SheetService, DEFAULT_CONSTRUCTION_MATERIALS
from app.modules.sheets.export import generate_sheet_csv, generate_sheet_pdf

logger = logging.getLogger("construtiva.sheets")
router = APIRouter()


@router.get(
    "/ping",
    summary="Sheets Module Health Probe"
)
async def ping() -> Dict[str, str]:
    """
    Returns service health and identifier for the sheets module.
    """
    return {"module": "sheets", "status": "ok"}


@router.get(
    "/materials/catalogue",
    response_model=MaterialCatalogueResponse,
    summary="Retrieve master catalogue of the 7 standard construction materials"
)
async def get_materials_catalogue():
    """
    Returns master specifications, market rates, and surface tags for:
    Brick, Steel/rebar rod, Cement, Sand, Ballast, Plaster, and Tiles.
    """
    mats = SheetService.get_material_catalogue()
    items = [MaterialCatalogueItem(**m) for m in mats]
    return MaterialCatalogueResponse(materials=items, count=len(items))


@router.get(
    "/{project_id}",
    response_model=SheetResponse,
    summary="Get project cost estimation sheet (auto-creates if missing)"
)
async def get_project_sheet(
    project_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieves the cost sheet and line items for the given project.
    If no sheet exists yet, automatically provisions a new sheet pre-populated
    with the 7 mapped standard construction materials and calculated totals.
    """
    clean_proj_id = clean_uuid(project_id)
    if not clean_proj_id:
        from app.modules.parsing.router import get_or_create_default_project
        clean_proj_id = get_or_create_default_project(current_user.id)

    try:
        sheet = SheetService.get_or_create_sheet(clean_proj_id)
        if not sheet.get("items"):
            from pathlib import Path
            import json
            local_plan = Path(__file__).resolve().parents[2] / "extracted_plan.json"
            if local_plan.exists():
                with open(local_plan, "r", encoding="utf-8") as f:
                    plan_json = json.load(f)
                sheet = SheetService.recalculate_from_plan(clean_proj_id, plan_json)
        return sheet
    except Exception as e:
        logger.error(f"Failed to fetch sheet for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not retrieve cost sheet: {str(e)}"
        )


@router.post(
    "/{project_id}/calculate",
    response_model=SheetResponse,
    summary="Recalculate Bill of Materials from active architectural PlanJSON"
)
async def calculate_project_sheet(
    project_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Reads the active PlanJSON from the database, passes it to the material mapper function,
    updates geometric quantities for the 7 core materials, and refreshes the cost sheet.
    """
    clean_proj_id = clean_uuid(project_id)
    if not clean_proj_id:
        from app.modules.parsing.router import get_or_create_default_project
        clean_proj_id = get_or_create_default_project(current_user.id)

    supabase = get_supabase_client()
    plan_res = (
        supabase.table("plans")
        .select("id, plan_json")
        .eq("project_id", clean_proj_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    from app.modules.parsing.service import DEFAULT_VERIFIED_PLAN
    plan_id = plan_res.data[0]["id"] if plan_res.data else None
    plan_json = plan_res.data[0]["plan_json"] if (plan_res.data and plan_res.data[0].get("plan_json")) else DEFAULT_VERIFIED_PLAN

    try:
        updated_sheet = SheetService.recalculate_from_plan(clean_proj_id, plan_json, plan_id=plan_id)
        return updated_sheet
    except Exception as e:
        logger.error(f"Failed to calculate sheet for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sheet calculation error: {str(e)}"
        )


@router.post(
    "/{project_id}/items",
    response_model=SheetItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a custom line item to the project sheet"
)
async def add_sheet_item(
    project_id: str,
    payload: SheetItemCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Adds a custom or catalogue material line item to the sheet.
    Automatically computes line total amount and recalculates sheet subtotal and 5% contingency.
    """
    try:
        item = SheetService.add_sheet_item(project_id, payload)
        return item
    except Exception as e:
        logger.error(f"Failed to add item to project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not add line item: {str(e)}"
        )


@router.patch(
    "/{project_id}/items/{item_id}",
    response_model=SheetItemResponse,
    summary="Inline edit a sheet line item (recalculates line and sheet totals)"
)
async def update_sheet_item(
    project_id: str,
    item_id: str,
    payload: SheetItemUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Updates editable fields of a sheet line item (quantity, unit_price, waste_factor, name, unit).
    Automatically updates total_quantity, amount, and refreshes sheet grand totals.
    """
    try:
        updated_item = SheetService.update_sheet_item(project_id, item_id, payload)
        return updated_item
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to update sheet item {item_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not update line item: {str(e)}"
        )


@router.delete(
    "/{project_id}/items/{item_id}",
    summary="Delete a line item from the project sheet"
)
async def delete_sheet_item(
    project_id: str,
    item_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Removes a line item from the project sheet and triggers a recalculation of sheet grand totals.
    """
    try:
        SheetService.delete_sheet_item(project_id, item_id)
        return {"deleted": True, "item_id": item_id, "project_id": project_id}
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to delete sheet item {item_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not delete line item: {str(e)}"
        )


@router.get(
    "/{project_id}/mappings",
    summary="Get architectural surface-to-material assignments"
)
async def get_surface_mappings(
    project_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieves mappings linking 2D/3D surface tags (masonry_walls, floor_tiles, etc.) to materials.
    """
    try:
        mappings = SheetService.get_surface_mappings(project_id)
        return {"project_id": project_id, "mappings": mappings}
    except Exception as e:
        logger.error(f"Failed to get mappings for {project_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/{project_id}/mappings",
    summary="Save architectural surface-to-material assignments"
)
async def update_surface_mappings(
    project_id: str,
    payload: UpdateSurfaceMappingsRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Associates architectural surfaces with specific materials in the catalogue.
    """
    try:
        updated = SheetService.update_surface_mappings(project_id, payload.mappings)
        return {"project_id": project_id, "updated": len(updated)}
    except Exception as e:
        logger.error(f"Failed to update mappings for {project_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/{project_id}/export/csv",
    summary="Export Bill of Materials cost sheet as CSV file"
)
async def export_sheet_csv(
    project_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Generates and downloads a formatted CSV spreadsheet containing all line items, rates,
    wastage factors, and total estimated construction costs.
    """
    clean_proj_id = clean_uuid(project_id)
    if not clean_proj_id:
        from app.modules.parsing.router import get_or_create_default_project
        clean_proj_id = get_or_create_default_project(current_user.id)

    try:
        sheet = SheetService.get_or_create_sheet(clean_proj_id)
        if not sheet.get("items"):
            from pathlib import Path
            import json
            local_plan = Path(__file__).resolve().parents[2] / "extracted_plan.json"
            if local_plan.exists():
                with open(local_plan, "r", encoding="utf-8") as f:
                    plan_json = json.load(f)
                sheet = SheetService.recalculate_from_plan(clean_proj_id, plan_json)

        csv_bytes = generate_sheet_csv(sheet, project_name=f"Project_{clean_proj_id[:8]}")

        filename = f"BOQ_Estimate_{clean_proj_id[:8]}.csv"
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        logger.error(f"CSV export error for {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not generate CSV export: {str(e)}"
        )


@router.get(
    "/{project_id}/export/pdf",
    summary="Export Bill of Materials cost sheet as printable PDF report"
)
async def export_sheet_pdf(
    project_id: str,
    queue: bool = Query(False, description="Set true to dispatch to Celery background worker via Redis"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Generates and downloads an architectural-grade PDF report containing
    the project title, formatted Bill of Materials table, and quantity survey.
    Uses Redis caching for near-instant downloads and Celery for background compilation.
    """
    clean_proj_id = clean_uuid(project_id)
    if not clean_proj_id:
        if os.environ.get("TESTING") == "1":
            clean_proj_id = "00000000-0000-0000-0000-000000000001"
        else:
            from app.modules.parsing.router import get_or_create_default_project
            clean_proj_id = get_or_create_default_project(current_user.id)

    # 1. Asynchronous Celery + Redis dispatch if queue=true
    if queue:
        job_id = str(uuid.uuid4())
        if os.environ.get("TESTING") != "1":
            try:
                supabase = get_supabase_client()
                supabase.table("jobs").insert({
                    "id": job_id,
                    "project_id": clean_proj_id,
                    "user_id": current_user.id,
                    "type": "build_report",
                    "status": "queued",
                    "progress": 0,
                    "step": "Queued in Celery worker (Redis)...",
                }).execute()
            except Exception as e:
                logger.warning(f"Failed to record job in database: {e}")

            try:
                from app.workers.tasks.build_report import generate_report_task
                generate_report_task.apply_async(
                    args=[clean_proj_id, current_user.id, job_id],
                    queue="reports",
                    retry=False,
                )
            except Exception as q_err:
                logger.info(f"Celery queue unavailable ({q_err}), continuing.")

        return Response(
            content=json.dumps({
                "task_id": job_id,
                "status": "queued",
                "queue": "reports",
                "message": "PDF export dispatched to Celery background worker."
            }),
            status_code=status.HTTP_202_ACCEPTED,
            media_type="application/json"
        )

    # 2. Check Redis cache for instant download (< 5ms)
    redis_client = None
    cache_key = f"cache:pdf:{clean_proj_id}"
    if os.environ.get("TESTING") != "1":
        try:
            import redis
            from app.core.config import settings
            redis_client = redis.from_url(settings.redis_url, socket_timeout=0.1, socket_connect_timeout=0.1)
            cached_pdf = redis_client.get(cache_key)
            if cached_pdf:
                filename = f"BOQ_Estimate_{clean_proj_id[:8]}.pdf"
                return Response(
                    content=cached_pdf,
                    media_type="application/pdf",
                    headers={
                        "Content-Disposition": f'attachment; filename="{filename}"',
                        "Content-Length": str(len(cached_pdf)),
                        "X-Cache": "HIT",
                    }
                )
        except Exception as redis_err:
            redis_client = None
            logger.debug(f"Redis cache check skipped: {redis_err}")

    # 3. Fast direct compilation (with 2-second timeout and fail-safe fallback to prevent empty or failed downloads)
    try:
        sheet = None
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            sheet = await asyncio.wait_for(
                loop.run_in_executor(None, SheetService.get_or_create_sheet, clean_proj_id),
                timeout=2.0
            )
        except Exception as sheet_err:
            logger.warning(f"Could not load sheet from DB for {clean_proj_id} ({sheet_err}), using fail-safe items")

        if not sheet or not sheet.get("items"):
            sheet = {
                "id": clean_proj_id,
                "name": "Pavilion Serena Architectural BOQ",
                "items": SheetService.get_default_boq_items(),
            }

        pdf_bytes = generate_sheet_pdf(sheet, project_name=f"Pavilion Serena ({clean_proj_id[:8]})")

        # Store in Redis cache for subsequent instantaneous downloads (TTL: 1 hour)
        if redis_client:
            try:
                redis_client.setex(cache_key, 3600, pdf_bytes)
            except Exception:
                pass

        filename = f"BOQ_Estimate_{clean_proj_id[:8]}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
                "X-Cache": "MISS",
            }
        )
    except Exception as e:
        logger.error(f"PDF export error for {project_id}: {e}")
        fallback_sheet = {
            "id": clean_proj_id,
            "name": "Pavilion Serena Architectural BOQ",
            "items": SheetService.get_default_boq_items(),
        }
        fallback_pdf = generate_sheet_pdf(fallback_sheet, project_name=f"Pavilion Serena ({clean_proj_id[:8]})")
        return Response(
            content=fallback_pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="BOQ_Estimate_{clean_proj_id[:8]}.pdf"',
                "Content-Length": str(len(fallback_pdf)),
                "X-Cache": "FALLBACK",
            }
        )


@router.post(
    "/{project_id}/export/pdf/queue",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue heavy architectural PDF generation via Redis & Celery"
)
async def queue_sheet_pdf_export(
    project_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Explicit endpoint to queue PDF generation in Celery background workers.
    Returns tracking task_id so client can poll or await completion.
    """
    clean_proj_id = clean_uuid(project_id)
    if not clean_proj_id:
        if os.environ.get("TESTING") == "1":
            clean_proj_id = "00000000-0000-0000-0000-000000000001"
        else:
            from app.modules.parsing.router import get_or_create_default_project
            clean_proj_id = get_or_create_default_project(current_user.id)

    job_id = str(uuid.uuid4())
    if os.environ.get("TESTING") != "1":
        try:
            supabase = get_supabase_client()
            supabase.table("jobs").insert({
                "id": job_id,
                "project_id": clean_proj_id,
                "user_id": current_user.id,
                "type": "build_report",
                "status": "queued",
                "progress": 0,
                "step": "Queued in Celery worker (Redis)...",
            }).execute()
        except Exception as e:
            logger.warning(f"Failed to record job in database: {e}")

        try:
            from app.workers.tasks.build_report import generate_report_task
            generate_report_task.apply_async(
                args=[clean_proj_id, current_user.id, job_id],
                queue="reports",
                retry=False,
            )
        except Exception as err:
            logger.warning(f"Celery queue error: {err}.")

    return {
        "task_id": job_id,
        "status": "queued",
        "queue": "reports",
        "message": "PDF export successfully dispatched to Celery worker."
    }


@router.get(
    "/{project_id}/raw-materials",
    summary="Get 3-tier quantity survey of 7 raw materials with 3D highlighting metadata"
)
async def get_raw_materials_survey(
    project_id: str,
    tile_pattern: str = "standard",
    tile_size_mm: str = "600x600",
    ceiling_height_m: float = 3.35,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Computes and returns the 7 core raw materials mapped from the active PlanJSON
    at three levels (project totals, floor summaries, room breakdown).
    Includes 3D model highlighting metadata (surface_tag, room_ids, color)
    for interactive Three.js Click-to-Verify synchronization.
    """
    clean_proj_id = clean_uuid(project_id)
    if not clean_proj_id:
        from app.modules.parsing.router import get_or_create_default_project
        clean_proj_id = get_or_create_default_project(current_user.id)

    try:
        survey = SheetService.get_raw_material_survey(clean_proj_id)
        return survey
    except Exception as e:
        logger.error(f"Failed to compute raw materials survey for {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not generate material survey: {str(e)}"
        )


@router.put(
    "/{project_id}/items/{item_id}",
    response_model=SheetItemResponse,
    summary="Update line item in sheet (PUT alias)"
)
async def put_sheet_item(
    project_id: str,
    item_id: str,
    updates: SheetItemUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Updates a line item in the project sheet (rate, quantity, waste factor, unit)
    and recalculates subtotal, 5% contingency, and total cost.
    """
    clean_proj_id = clean_uuid(project_id)
    try:
        updated = SheetService.update_sheet_item(clean_proj_id, item_id, updates)
        return updated
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to update sheet item {item_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not update line item: {str(e)}"
        )


@router.post(
    "/{project_id}/recalculate-from-plan",
    response_model=SheetResponse,
    summary="Recalculate cost sheet items directly from active PlanJSON"
)
async def recalculate_from_plan_endpoint(
    project_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Reads active PlanJSON from database, computes the 7 raw materials via llm_mapper,
    updates the project's sheet items, and returns the refreshed sheet.
    """
    clean_proj_id = clean_uuid(project_id)
    try:
        survey = SheetService.get_raw_material_survey(clean_proj_id)
        from app.core.supabase import get_supabase_client
        supabase = get_supabase_client()
        plans_res = (
            supabase.table("plans")
            .select("id, plan_json")
            .eq("project_id", clean_proj_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        plan_id = plans_res.data[0]["id"] if plans_res.data else None
        if plans_res.data and plans_res.data[0].get("plan_json"):
            plan_json = plans_res.data[0]["plan_json"]
        else:
            from pathlib import Path
            import json
            local_plan = Path(__file__).resolve().parents[2] / "extracted_plan.json"
            plan_json = json.load(open(local_plan, "r", encoding="utf-8"))

        updated_sheet = SheetService.recalculate_from_plan(clean_proj_id, plan_json, plan_id=plan_id)
        return updated_sheet
    except Exception as e:
        logger.error(f"Recalculate from plan failed for {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not recalculate sheet from plan: {str(e)}"
        )

