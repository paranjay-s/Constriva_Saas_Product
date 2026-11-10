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

import logging
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status, Response
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
        .select("plan_json")
        .eq("project_id", clean_proj_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    from app.modules.parsing.service import DEFAULT_VERIFIED_PLAN
    plan_json = plan_res.data[0]["plan_json"] if (plan_res.data and plan_res.data[0].get("plan_json")) else DEFAULT_VERIFIED_PLAN

    try:
        updated_sheet = SheetService.recalculate_from_plan(clean_proj_id, plan_json)
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
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Generates and downloads an architectural-grade PDF report containing
    the project title, formatted Bill of Materials table, and cost summary.
    """
    clean_proj_id = clean_uuid(project_id)
    if not clean_proj_id:
        from app.modules.parsing.router import get_or_create_default_project
        clean_proj_id = get_or_create_default_project(current_user.id)

    try:
        sheet = SheetService.get_or_create_sheet(clean_proj_id)
        pdf_bytes = generate_sheet_pdf(sheet, project_name=f"Pavilion Serena ({clean_proj_id[:8]})")

        filename = f"BOQ_Estimate_{clean_proj_id[:8]}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        logger.error(f"PDF export error for {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not generate PDF export: {str(e)}"
        )
