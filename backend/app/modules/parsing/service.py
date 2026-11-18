"""Shared pieces of plan uploads.

`read_plan_upload` and `upload_limits` are the one place where an uploaded plan PDF is
checked (PDF only, size and page limits): the BOQ and the 3D gateway both call them before
anything is parsed or built. `get_default_verified_plan` is the empty plan the older
per-project sheet endpoints fall back to.

The 2D-to-3D import that used to live here (parse with the plan parser, store the plan,
feed the in-browser viewer) was replaced by the PlanTo3D service behind /api/v1/3d.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict
from app.modules.parsing.errors import FileTooLargeError, NotAPdfError
from app.modules.parsing.pdf_input import check_plan_pdf
from app.modules.parsing.settings import get_settings

logger = logging.getLogger("construtiva.parsing")


# Load verified plan from extracted_plan.json as singleton default
DEFAULT_VERIFIED_PLAN: Dict[str, Any] = {}
_extracted_plan_path = Path(__file__).resolve().parents[2] / "extracted_plan.json"
if _extracted_plan_path.exists():
    try:
        with open(_extracted_plan_path, "r", encoding="utf-8") as _f:
            DEFAULT_VERIFIED_PLAN = json.load(_f)
    except Exception as _e:
        logger.warning(f"Could not load extracted_plan.json: {_e}")

if not DEFAULT_VERIFIED_PLAN:
    DEFAULT_VERIFIED_PLAN = {
        "metadata": {"name": "Precision Architectural Floor Plan (36'6\" x 55')", "scale": 1.0, "units": "meters"},
        "walls": [],
        "rooms": [],
        "doors": [],
        "windows": [],
    }


def get_default_verified_plan() -> Dict[str, Any]:
    if hasattr(DEFAULT_VERIFIED_PLAN, "model_dump"):
        return DEFAULT_VERIFIED_PLAN.model_dump()
    return DEFAULT_VERIFIED_PLAN


def upload_limits() -> Dict[str, Any]:
    """The limits every plan upload is held to (PLAN_PARSER_MAX_PDF_MB / _PAGES)."""
    settings = get_settings()
    return {"max_pdf_mb": settings.max_pdf_mb, "max_pdf_pages": settings.max_pdf_pages}


async def read_plan_upload(upload: Any) -> bytes:
    """
    Reads an uploaded plan and checks it before anything else happens to it:
    PDF only, within the size limit, opens as a PDF, within the page limit.

    Used by every flow that accepts a plan PDF. Raises a PlanParseError subclass whose
    message can be shown to the user and whose `http_status` an endpoint can answer with.
    Nothing is stored and no model is called for a rejected upload. At most one byte more
    than the size limit is read into memory.
    """
    limit = get_settings().max_pdf_bytes
    name = upload.filename or ""
    if not name.lower().endswith(".pdf"):
        raise NotAPdfError("Please upload the floor plan as a PDF file.")
    declared = getattr(upload, "size", None)
    if isinstance(declared, int) and declared > limit:
        raise FileTooLargeError(
            f"This PDF is {declared / 1048576:.1f} MB. "
            f"The largest file accepted is {limit / 1048576:g} MB."
        )
    data = await upload.read(limit + 1)
    check_plan_pdf(data, name)
    return data
