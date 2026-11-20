"""Every download comes from the same FloorPlan JSON.

svg  vector drawing (the on-screen view)
pdf  vector PDF of that SVG (lines stay sharp at any zoom, prints to scale)
png  raster image of that SVG (dpi selectable)
dxf  CAD drawing in cm with layers, blocks and real dimensions (render/dxf_renderer.py)

The PDF names the plan it was made from in its document information (Keywords), so
that when its owner uploads it to the 3D builder the stored plan is used instead of
reading the drawing back. The reference is not a secret and proves nothing: whoever
reads it must still check that the plan belongs to the user (read_plan_reference).
"""

import re
from dataclasses import dataclass
from typing import Literal

import pymupdf

from app.modules.ai.floorplan.schemas.plan import FloorPlan

ExportFormat = Literal["svg", "pdf", "png", "dxf", "dwg", "ifc"]
FORMATS: tuple[str, ...] = ("svg", "pdf", "png", "dxf", "dwg", "ifc")
MEDIA_TYPES = {
    "svg": "image/svg+xml",
    "pdf": "application/pdf",
    "png": "image/png",
    "dxf": "application/dxf",
    "dwg": "application/acad",
    "ifc": "application/x-step",
}


PDF_CREATOR = "Constriva floor plan generator"
_PLAN_REF = re.compile(
    r"\bconstriva-plan:([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
    r"(?:;v=(\d{1,6}))?(?![\w-])"
)
_MAX_KEYWORDS = 2000  # a longer Keywords entry is not ours


@dataclass(frozen=True)
class Export:
    data: bytes
    media_type: str
    filename: str


@dataclass(frozen=True)
class PlanReference:
    """The plan a PDF says it was exported from. `version` is None when it does not say."""

    plan_id: str
    version: int | None = None


def plan_reference(plan_id: str, version: int | None = None) -> str:
    """The text written to the PDF's Keywords; empty when the id is not a UUID."""
    text = f"constriva-plan:{plan_id.strip().lower()}"
    if version is not None and 0 < version < 1_000_000:
        text += f";v={version}"
    return text if _PLAN_REF.fullmatch(text) else ""


def read_plan_reference(pdf_bytes: bytes) -> PlanReference | None:
    """The plan reference in an uploaded PDF's document information, or None.

    Never raises: the bytes come from a user. The result only says what the file
    claims; the caller checks that the plan exists and belongs to the user.
    """
    try:
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
            keywords = (doc.metadata or {}).get("keywords") or ""
    except Exception:  # an unreadable PDF simply has no reference
        return None
    if not isinstance(keywords, str) or len(keywords) > _MAX_KEYWORDS:
        return None
    found = _PLAN_REF.search(keywords.lower())
    if not found:
        return None
    return PlanReference(found.group(1), int(found.group(2)) if found.group(2) else None)


def _with_reference(pdf: bytes, plan: FloorPlan, version: int | None) -> bytes:
    reference = plan_reference(plan.id, version)
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        doc.set_metadata(
            {
                "title": plan.meta.project.strip() or "Floor plan",
                "creator": PDF_CREATOR,
                "producer": PDF_CREATOR,
                "keywords": reference,
            }
        )
        return doc.tobytes(garbage=3, deflate=True)


def export_plan(
    plan: FloorPlan,
    fmt: ExportFormat,
    *,
    dpi: int = 150,
    version: int | None = None,
    building=None,
    furniture: bool | None = None,
    sheet: str | None = None,
    view: str = "engineering",
) -> Export:
    """Every format from the building model (drawing/ for SVG, PDF and PNG). `building`
    carries the revision list and model of a stored plan; without it the plan's own
    model is built. `view` "presentation" draws the colour presentation plan for SVG, PDF
    and PNG (drawing/presentation.py; the PDF carries the signed model as well); DXF, DWG
    and IFC are always the engineering drawing."""
    if fmt not in FORMATS:
        raise ValueError(f"unknown export format {fmt!r}; use one of {', '.join(FORMATS)}")
    from app.modules.ai.floorplan.model.build import build_building

    b = building or build_building(plan, version=version or 1)
    if fmt in ("dxf", "dwg"):
        from app.modules.ai.floorplan.render.cad_dxf import building_dxf

        data = building_dxf(b, sheet=sheet, furniture=furniture)
        if fmt == "dwg":
            from app.modules.ai.floorplan.render.dwg import dxf_to_dwg

            data = dxf_to_dwg(data)
    elif fmt == "ifc":
        from app.modules.ai.floorplan.render.cad_ifc import building_ifc

        data = building_ifc(b)
    else:
        from app.modules.ai.floorplan.drawing.compose import compose_sheet
        from app.modules.ai.floorplan.drawing.emit import to_pdf, to_png, to_svg
        from app.modules.ai.floorplan.model.embed import embed_model

        if view == "presentation":
            from app.modules.ai.floorplan.drawing.presentation import compose_presentation

            drawn = compose_presentation(b, sheet=sheet, furniture=furniture)
        else:
            drawn = compose_sheet(b, sheet=sheet, furniture=furniture)
        if fmt == "svg":
            data = to_svg(drawn, embed_font=True).encode("utf-8")
        else:
            pdf = to_pdf(
                drawn,
                title=plan.meta.project.strip() or "Floor plan",
                keywords=plan_reference(plan.id, version),
            )
            data = embed_model(pdf, b) if fmt == "pdf" else to_png(pdf, dpi)
    suffix = "-presentation" if view == "presentation" and fmt in ("svg", "pdf", "png") else ""
    return Export(data, MEDIA_TYPES[fmt], f"{_basename(plan)}{suffix}.{fmt}")


def _basename(plan: FloorPlan) -> str:
    """File name from the user's project name (or the plan id); safe on every OS."""
    name = plan.meta.project.strip() or plan.id
    slug = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return (slug or "floor-plan")[:60]
