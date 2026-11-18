"""Plan drawings, mounted at /api/v1/plans.

GET /{plan_id}/download-png   the PNG working drawing stored with a generated plan, for the
                              owner of the plan's project only

The endpoints that read and updated a plan's PlanJSON for the in-browser 3D viewer
(GET /{plan_id}, GET /project/{project_id}, PUT /{plan_id}) were removed with that viewer.
The PlanJSON model itself is in schemas.py and is unchanged.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import AuthenticatedUser, clean_uuid, get_current_user
from app.core.supabase import get_supabase_client

logger = logging.getLogger("construtiva.plans")
router = APIRouter()


@router.get(
    "/{plan_id}/download-png",
    summary="Download high-resolution 2D architectural working blueprint PNG"
)
async def download_plan_png(
    plan_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Returns the printable, high-resolution CAD working drawing PNG image
    for the specified plan ID.

    Only the owner of the plan's project can download it. Someone else's plan and a plan
    that does not exist both give the same 404.
    """
    import base64
    from fastapi.responses import Response

    from app.modules.projects.service import user_owns_project

    clean_id = clean_uuid(plan_id)
    plan_name = "Architectural_Working_Plan"
    png_bytes = None

    if clean_id:
        try:
            supabase = get_supabase_client()
            res = (
                supabase.table("plans")
                .select("name, project_id, generation_metadata")
                .eq("id", clean_id)
                .execute()
            )
            row = res.data[0] if res.data else None
            if row and user_owns_project(row.get("project_id"), current_user.id):
                plan_name = row.get("name") or plan_name
                meta = row.get("generation_metadata") or {}
                b64_str = meta.get("png_base64")
                if b64_str:
                    png_bytes = base64.b64decode(b64_str)
        except Exception as e:
            logger.warning(f"Could not load PNG from DB for plan {plan_id}: {e}")

    # A plan without a stored drawing has none to download. Another plan's drawing is
    # never returned in its place.
    if not png_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This plan has no downloadable drawing.",
        )

    clean_filename = "".join(c for c in plan_name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="{clean_filename}.png"',
            "Content-Length": str(len(png_bytes)),
        }
    )
