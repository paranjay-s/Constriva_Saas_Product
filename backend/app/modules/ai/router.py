"""
=============================================================================
Construtiva AI Module API Router
=============================================================================
File: app/modules/ai/router.py
Purpose:
  Exposes REST endpoints for AI-driven construction vision and advisory:
  - POST /api/v1/ai/analyze-materials: Upload photo taken on site/phone to detect
    building materials and estimate installation cost.
  - POST /api/v1/ai/chat: AI architectural assistant for conversational modifications.
  - GET  /api/v1/ai/ping: Health check.
=============================================================================
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, status
from pydantic import BaseModel, Field

from app.core.security import get_current_user, AuthenticatedUser
from app.modules.ai.material_vision import analyze_construction_photo

logger = logging.getLogger("construtiva.ai.router")
router = APIRouter()


class AIChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Architectural modification prompt or query")
    project_id: Optional[str] = Field(None, description="Optional active project UUID context")
    plan_id: Optional[str] = Field(None, description="Optional active plan UUID context")
    plot_width: Optional[float] = Field(36.5, description="Plot width in feet")
    plot_length: Optional[float] = Field(55.0, description="Plot length in feet")
    goal: Optional[str] = Field("rental", description="Goal: 'rental', 'residence', 'commercial', etc.")
    config_type: Optional[str] = Field("dual_rental_2bhk", description="Configuration: '1_bhk', '2_bhk', '3_bhk', '4_bhk', 'dual_rental_2bhk'")
    facing: Optional[str] = Field("East", description="Plot orientation: 'East', 'North', 'West', 'South'")


class GeneratePlanRequest(BaseModel):
    project_id: Optional[str] = Field(None, description="Associated project UUID")
    plot_width: float = Field(36.5, ge=10.0, le=500.0, description="Plot width in feet (e.g. 36.5)")
    plot_length: float = Field(55.0, ge=10.0, le=500.0, description="Plot depth in feet (e.g. 55.0)")
    area_sqft: Optional[float] = Field(None, description="Optional total plot area in square feet")
    goal: str = Field("rental", description="Purpose: 'rental' (multi-tenant flats) or 'residence' (family home)")
    config_type: str = Field("dual_rental_2bhk", description="Room configuration ('1_bhk', '2_bhk', '3_bhk', '4_bhk', 'dual_rental_2bhk')")
    facing: str = Field("East", description="Direction facing ('East', 'North', 'West', 'South')")
    client_name: str = Field("SMT. GEETA GAUD", description="Client or owner name for title block")
    user_prompt: Optional[str] = Field(None, description="Detailed layout specifications (attached toilets, lawn, puja, etc.)")


@router.post(
    "/generate-plan",
    summary="Generate high-resolution 2D architectural working blueprint PNG & PlanJSON"
)
async def generate_plan_endpoint(
    payload: GeneratePlanRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Synthesizes a precision 2D working floor plan modeled after Vikas Patodi CAD standards:
    - Renders print-ready PNG (1600x2400) with engineering title block, columns, and hatch.
    - Constructs standards-compliant PlanJSON for 3D viewer & BOQ sheets.
    - Saves the generated plan record in Supabase database.
    """
    from app.modules.ai.floorplan_generator import generate_ai_floorplan

    # Compute width and length if area_sqft is given without explicit length
    w = payload.plot_width
    l = payload.plot_length
    if payload.area_sqft and (w <= 0 or l <= 0):
        w = round((payload.area_sqft * 0.66) ** 0.5, 1)
        l = round(payload.area_sqft / w, 1)

    result = generate_ai_floorplan(
        plot_width_ft=w,
        plot_length_ft=l,
        config_type=payload.config_type,
        goal=payload.goal,
        facing=payload.facing,
        user_prompt=payload.user_prompt or "",
        client_name=payload.client_name,
        project_id=payload.project_id or current_user.id,
    )
    return result


@router.get(
    "/ping",
    summary="AI Module Health Check"
)
async def ping() -> Dict[str, str]:
    return {"module": "ai", "status": "ok"}


@router.post(
    "/analyze-materials",
    summary="Upload site/room photograph to detect materials and estimate costs"
)
async def analyze_materials(
    file: UploadFile = File(..., description="Camera photo of room, wall, or site (JPG/PNG)"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Accepts an uploaded photograph of a construction site or interior room,
    runs multimodal Vision LLM analysis, and returns:
    - Detected materials (e.g. brickwork, vitrified tiles, plaster coat).
    - Estimated quantities and unit rates (INR).
    - Total estimated construction/renovation cost.
    - Engineering recommendations.
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file uploaded.")

    content_type = file.content_type or "image/jpeg"
    if not any(content_type.startswith(t) for t in ("image/jpeg", "image/png", "image/webp")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image format (JPEG, PNG, WEBP)."
        )

    try:
        image_bytes = await file.read()
        if len(image_bytes) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded image is empty.")

        report = analyze_construction_photo(image_bytes, mime_type=content_type)
        return {
            "status": "success",
            "filename": file.filename,
            "analysis": report
        }

    except Exception as e:
        logger.error(f"Error during material photo analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Material analysis failed: {str(e)}"
        )


@router.post(
    "/chat",
    summary="Architectural AI Assistant Chat"
)
async def ai_chat(
    payload: AIChatRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Conversational assistant for dynamically refining floor plans:
    takes user architectural requests (attached toilets, enlarge rooms, add lawn, swap locations),
    synthesizes the revised plan, and generates an updated 2D CAD blueprint PNG.
    """
    from app.modules.ai.floorplan_generator import generate_ai_floorplan

    plan_res = generate_ai_floorplan(
        plot_width_ft=payload.plot_width or 36.5,
        plot_length_ft=payload.plot_length or 55.0,
        config_type=payload.config_type or "dual_rental_2bhk",
        goal=payload.goal or "rental",
        facing=payload.facing or "East",
        user_prompt=payload.message,
        client_name="SMT. GEETA GAUD",
        project_id=payload.project_id or current_user.id,
    )

    return {
        "reply": plan_res["ai_commentary"],
        "plan_id": plan_res["plan_id"],
        "project_id": plan_res["project_id"],
        "plan": plan_res,
    }


@router.get(
    "/plans/{plan_id}/png",
    summary="Download 2D architectural working blueprint PNG (AI route)"
)
async def get_ai_plan_png(
    plan_id: str,
):
    """
    Direct route to fetch and download the high-resolution CAD working drawing PNG.
    """
    from app.modules.plans.router import download_plan_png
    return await download_plan_png(plan_id)
