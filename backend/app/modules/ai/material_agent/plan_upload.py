"""A floor plan uploaded in the chat: parsed with the existing parser, kept on the
conversation only.

Nothing here writes to the project's `plans` table: an upload in the chat must never
overwrite the project's saved plan. The original file is stored (bucket `blueprints`, one `files` row)
so it can be found again; both are best effort.
"""

import io
import logging
import re
import uuid
from collections.abc import Callable

from PIL import Image, UnidentifiedImageError

logger = logging.getLogger("construtiva.ai.material.plan_upload")

PLAN_MIME = ("application/pdf", "image/png", "image/jpeg", "image/webp")

# (file bytes, mime) -> PlanJSON dict
PlanParser = Callable[[bytes, str], dict]


class PlanUploadError(ValueError):
    """Message is safe to show."""


def _to_png(data: bytes, mime: str) -> bytes:
    if mime == "application/pdf":
        from app.modules.parsing.pdf_to_image import convert_pdf_page_to_png

        png, _, _ = convert_pdf_page_to_png(data, page_number=0, dpi=200)
        return png
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as e:
        raise PlanUploadError("That file is not a readable plan image.") from e
    out = io.BytesIO()
    img.convert("RGB").save(out, format="PNG")
    return out.getvalue()


def default_parser(data: bytes, mime: str) -> dict:
    """Existing parser (parsing/llm_parser.py), accepting plans with 1+ rooms."""
    from app.modules.parsing.llm_parser import parse_blueprint_image_with_llm

    png = _to_png(data, mime)
    try:
        return parse_blueprint_image_with_llm(png, min_rooms=1)
    except ValueError as e:
        raise PlanUploadError(
            "I could not read rooms from that plan. You can type the room size instead."
        ) from e


def store_file(
    user_id: str, name: str, data: bytes, mime: str, project_id: str | None
) -> str | None:
    """Upload the original and add a `files` row (best effort). Returns the storage key."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:80] or "plan"
    file_id = str(uuid.uuid4())
    path = f"{user_id}/material_finder/{file_id}_{safe}"
    try:
        from app.core.supabase import get_supabase_client, upload_to_storage

        key = upload_to_storage("blueprints", path, data, mime)
        get_supabase_client().table("files").insert(
            {
                "id": file_id,
                "user_id": user_id,
                "project_id": project_id,
                "kind": "floor_plan_pdf" if mime == "application/pdf" else "floor_plan_image",
                "name": name[:200],
                "storage_key": key,
                "mime_type": mime,
                "size_bytes": len(data),
                "status": "uploaded",
            }
        ).execute()
        return key
    except Exception as e:  # storage is optional for the calculation
        logger.warning("uploaded plan not stored: %s", e)
        return None
