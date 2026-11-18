"""Plan upload helpers, mounted at /api/v1/parsing.

GET  /upload-limits   the size and page limits every plan PDF must meet
POST /pdf-to-image    one PDF page as a PNG (a utility; signed-in users only)

Parsing a plan for the bill of quantities is /api/v1/sheets/boq, and building a 3D house
from a plan is /api/v1/3d. The earlier 2D-to-3D import endpoints (/process, /stream,
/job/{id}/image, /{project_id}/plan) were removed with the in-browser 3D viewer.
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response

from app.core.security import AuthenticatedUser, get_current_user
from app.modules.parsing.service import read_plan_upload, upload_limits

logger = logging.getLogger("construtiva.parsing.router")
router = APIRouter()


@router.get(
    "/upload-limits",
    summary="The size and page limits a plan PDF must meet"
)
async def get_upload_limits(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Returns the limits every plan upload is checked against, so a client can say them
    up front. They are set by PLAN_PARSER_MAX_PDF_MB and PLAN_PARSER_MAX_PDF_PAGES.
    """
    return upload_limits()


@router.post(
    "/pdf-to-image",
    summary="Directly rasterize uploaded PDF to high-resolution PNG image",
    response_class=Response,
)
async def rasterize_pdf_endpoint(
    file: UploadFile = File(..., description="Architectural floor plan PDF document"),
    dpi: int = 300,
    page_number: int = 0,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Directly converts an uploaded architectural PDF page into a crisp PNG image stream (300 DPI).
    Useful for testing, visual preview, and feeding directly into the Vision LLM.

    Args:
        file (UploadFile): The PDF file.
        dpi (int): Target DPI (default 300).
        page_number (int): Zero-based page index (default 0).

    Returns:
        Response: PNG image stream (image/png) with width/height headers.
    """
    # The same check as the plan uploads: PDF only, within the size and page limits.
    try:
        pdf_bytes = await read_plan_upload(file)
    except ValueError as rejected:
        raise HTTPException(
            status_code=getattr(rejected, "http_status", status.HTTP_400_BAD_REQUEST),
            detail=str(rejected),
        ) from rejected

    try:
        from app.modules.parsing.pdf_to_image import convert_pdf_page_to_png
        png_bytes, width, height = convert_pdf_page_to_png(pdf_bytes, page_number=page_number, dpi=dpi)

        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={
                "X-Image-Width": str(width),
                "X-Image-Height": str(height),
                "Content-Disposition": f'inline; filename="{file.filename}_page{page_number+1}.png"'
            }
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to rasterize PDF: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

