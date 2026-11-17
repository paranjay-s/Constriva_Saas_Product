"""Every download comes from the same FloorPlan JSON.

svg  vector drawing (the on-screen view)
pdf  vector PDF of that SVG (lines stay sharp at any zoom, prints to scale)
png  raster image of that SVG (dpi selectable)
dxf  CAD drawing in cm with layers, blocks and real dimensions (render/dxf_renderer.py)
"""

import re
from dataclasses import dataclass
from typing import Literal

import pymupdf

from app.modules.ai.floorplan.render.dxf_renderer import render_dxf
from app.modules.ai.floorplan.render.svg_renderer import render_svg
from app.modules.ai.floorplan.schemas.plan import FloorPlan

ExportFormat = Literal["svg", "pdf", "png", "dxf"]
FORMATS: tuple[str, ...] = ("svg", "pdf", "png", "dxf")
MEDIA_TYPES = {
    "svg": "image/svg+xml",
    "pdf": "application/pdf",
    "png": "image/png",
    "dxf": "application/dxf",
}


@dataclass(frozen=True)
class Export:
    data: bytes
    media_type: str
    filename: str


def export_plan(plan: FloorPlan, fmt: ExportFormat, *, dpi: int = 150) -> Export:
    if fmt not in FORMATS:
        raise ValueError(f"unknown export format {fmt!r}; use one of {', '.join(FORMATS)}")
    if fmt == "dxf":
        data = render_dxf(plan)
    else:
        svg = render_svg(plan)
        if fmt == "svg":
            data = svg.encode("utf-8")
        else:
            doc = pymupdf.open(stream=svg.encode("utf-8"), filetype="svg")
            if fmt == "pdf":
                data = doc.convert_to_pdf()
            else:
                data = doc[0].get_pixmap(dpi=max(50, min(dpi, 600))).tobytes("png")
    return Export(data, MEDIA_TYPES[fmt], f"{_basename(plan)}.{fmt}")


def _basename(plan: FloorPlan) -> str:
    """File name from the user's project name (or the plan id); safe on every OS."""
    name = plan.meta.project.strip() or plan.id
    slug = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return (slug or "floor-plan")[:60]
