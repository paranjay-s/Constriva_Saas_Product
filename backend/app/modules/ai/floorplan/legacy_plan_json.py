"""FloorPlan (cm) -> the app's existing PlanJSON (metres), for the 3D viewer and BOQ sheets.

The `plans.plan_json` column is read by the 3D workspace, the plan editor and the
material sheets, so a generated plan is stored there in that shape:

    levels[0].walls     centre-line segments with thickness (0.23 exterior, 0.12 interior)
    levels[0].openings  doors/windows hosted on a wall, offset from the wall start (m)
    levels[0].rooms     rectangles as polygons, with name, tag and kind (indoor/outdoor)

The FloorPlan itself (the source of truth) is stored next to it in generation_metadata.
"""

from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge, unary_union

from app.modules.ai.floorplan.geometry import (
    door_span,
    enclosed_union,
    split_wall_edges,
    window_span,
)
from app.modules.ai.floorplan.rules import WALL_EXTERIOR_CM, WALL_INTERIOR_CM
from app.modules.ai.floorplan.schemas.plan import FloorPlan, Room
from app.modules.ai.floorplan.units import fmt_size

WALL_HEIGHT_M = 2.8
DOOR_HEIGHT_M = 2.1
WINDOW_HEIGHT_M = 1.2
WINDOW_SILL_M = 0.9


def _m(cm: float) -> float:
    return round(cm / 100, 3)


def _segments(lines: list[LineString]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Merge overlapping/collinear pieces into maximal straight segments."""
    if not lines:
        return []
    merged = linemerge(unary_union(lines))
    parts = list(merged.geoms) if isinstance(merged, MultiLineString) else [merged]
    out = []
    for part in parts:
        coords = list(part.coords)
        # split polylines at corners so every wall is straight
        start = coords[0]
        for i in range(1, len(coords)):
            a, b = coords[i - 1], coords[i]
            nxt = coords[i + 1] if i + 1 < len(coords) else None
            same_dir = nxt is not None and ((a[0] == b[0] == nxt[0]) or (a[1] == b[1] == nxt[1]))
            if not same_dir:
                out.append((start, b))
                start = b
    return [s for s in out if LineString(s).length >= 10]


def _rooms_beside(plan: FloorPlan, seg) -> list[str]:
    (x1, y1), (x2, y2) = seg
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    probes = [(mx, my - 2), (mx, my + 2)] if y1 == y2 else [(mx - 2, my), (mx + 2, my)]
    ids = []
    for px, py in probes:
        for r in plan.rooms:
            if r.x < px < r.x2 and r.y < py < r.y2:
                ids.append(r.id)
                break
    return ids


def _kind(r: Room) -> str:
    if r.type == "shaft":
        return "outdoor" if r.part_of else "void"
    return "outdoor" if r.is_open else "indoor"


def to_legacy_plan_json(plan: FloorPlan) -> dict:
    exterior, interior = split_wall_edges(plan)
    walls = []
    n = 0
    for lines, kind, thick in (
        (exterior, "exterior", WALL_EXTERIOR_CM),
        (interior, "interior", WALL_INTERIOR_CM),
    ):
        for seg in _segments(lines):
            n += 1
            (x1, y1), (x2, y2) = seg
            walls.append(
                {
                    "id": f"w_{n:03d}",
                    "start": [_m(x1), _m(y1)],
                    "end": [_m(x2), _m(y2)],
                    "thickness": _m(thick),
                    "height": WALL_HEIGHT_M,
                    "kind": kind,
                    "type": kind,
                    "length": _m(LineString(seg).length),
                    "inferred": False,
                    "rooms": _rooms_beside(plan, seg),
                }
            )

    def host(span) -> tuple[dict, float] | None:
        (sx, sy), (ex, ey) = span.start, span.end
        for w in walls:
            (wx1, wy1), (wx2, wy2) = (
                (w["start"][0] * 100, w["start"][1] * 100),
                (w["end"][0] * 100, w["end"][1] * 100),
            )
            if span.horizontal and abs(wy1 - sy) < 1 and abs(wy2 - sy) < 1:
                lo, hi = sorted((wx1, wx2))
                if lo - 1 <= min(sx, ex) and max(sx, ex) <= hi + 1:
                    return w, _m(min(sx, ex) - wx1 if wx1 <= wx2 else wx1 - max(sx, ex))
            if not span.horizontal and abs(wx1 - sx) < 1 and abs(wx2 - sx) < 1:
                lo, hi = sorted((wy1, wy2))
                if lo - 1 <= min(sy, ey) and max(sy, ey) <= hi + 1:
                    return w, _m(min(sy, ey) - wy1 if wy1 <= wy2 else wy1 - max(sy, ey))
        return None

    openings = []
    for d in plan.doors:
        found = host(door_span(plan, d))
        if found:
            w, off = found
            openings.append(
                {
                    "id": d.id,
                    "wall_id": w["id"],
                    "type": "door",
                    "offset": max(0.0, off),
                    "width": _m(d.width),
                    "height": DOOR_HEIGHT_M,
                    "sill": 0.0,
                    "inferred": False,
                }
            )
    for win in plan.windows:
        found = host(window_span(plan, win))
        if found:
            w, off = found
            openings.append(
                {
                    "id": win.id,
                    "wall_id": w["id"],
                    "type": "window",
                    "offset": max(0.0, off),
                    "width": _m(win.width),
                    "height": WINDOW_HEIGHT_M,
                    "sill": WINDOW_SILL_M,
                    "inferred": False,
                }
            )

    unit = plan.meta.unit_display
    rooms = [
        {
            "id": r.id,
            "name": r.label,
            "category": r.zone,
            "kind": _kind(r),
            "polygon": [
                [_m(r.x), _m(r.y)],
                [_m(r.x2), _m(r.y)],
                [_m(r.x2), _m(r.y2)],
                [_m(r.x), _m(r.y2)],
            ],
            "tag": r.type,
            "dimensions": fmt_size(r.w, r.h, unit),
        }
        for r in plan.rooms
    ]
    built = enclosed_union(plan)
    return {
        "version": 1,
        "units": "m",
        "scale_source": "dimension_label",
        "project_title": plan.meta.project or "",
        "client": plan.meta.owner or "",
        "levels": [
            {
                "elevation": 0.0,
                "wall_height": WALL_HEIGHT_M,
                "walls": walls,
                "openings": openings,
                "rooms": rooms,
                "columns": [],
            }
        ],
        "confidence": {"overall": 1.0},
        "plot": {"width": _m(plan.plot.width), "depth": _m(plan.plot.depth)},
        "built_area_m2": round(built.area / 10_000, 1),
    }
