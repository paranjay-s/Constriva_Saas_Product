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
    Conversational assistant for querying floor plan details, suggesting material alterations,
    and explaining estimated construction costs.
    """
    return {
        "reply": f"Received architectural prompt: '{payload.message}'. AI advice: Recommend reviewing load-bearing wall alignments and ensuring 0.25m thickness on external facades.",
        "project_id": payload.project_id,
        "plan_id": payload.plan_id,
    }
