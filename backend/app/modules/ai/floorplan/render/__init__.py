"""Renderers. The drawing itself lives in floorplan/drawing (one display list for SVG,
PDF and PNG); CAD files in render/cad_dxf.py, render/cad_ifc.py and render/dwg.py."""

from app.modules.ai.floorplan.schemas.plan import FloorPlan


def render_svg(plan: FloorPlan, *, furniture: bool | None = None) -> str:
    """The plan's sheet as SVG (the in-app preview of a plan without stored history)."""
    from app.modules.ai.floorplan.drawing.compose import compose_sheet
    from app.modules.ai.floorplan.drawing.emit import to_svg
    from app.modules.ai.floorplan.model.build import build_building

    building = build_building(plan, date="")
    return to_svg(compose_sheet(building, furniture=furniture), embed_font=True)


__all__ = ["render_svg"]
