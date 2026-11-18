"""Deterministic PlanJSON normaliser. Pure Python, no model calls, no I/O.

Everything that must not depend on which LLM read the drawing happens here:

  * every length is converted to metres once, with one drawing-wide scale, and `units`
    becomes "m";
  * room polygons are cleaned (no repeated or closing point, at least three points,
    non-zero area, counter-clockwise, rounded to 3 decimals, canonical start vertex);
  * rooms, walls, openings and columns are sorted in a canonical order and given stable
    ids (`L0-R01`, `L0-W01`, `L0-O01`, `L0-C01`);
  * room `kind` and `boq_type`, wall `kind` / `is_exterior` and opening `type` are set
    by rule (`room.type` is the 3D adapter's key and is never read or written);
  * scale warnings are raised for implausible room sizes and for rooms whose printed size
    disagrees with the drawn polygon.

`normalise_plan` is the parser's stage. `upgrade_plan` only fills what an older stored
PlanJSON is missing and leaves its ids, order and geometry alone.

The same input always gives the same output.
"""

import logging
import math
import re
from collections import defaultdict
from typing import Any

from app.modules.parsing.validate import compute_plan_confidence, deduplicate_and_merge_walls
from app.modules.plans.room_kind import ROOM_KINDS, parser_room_kind
from app.modules.plans.room_types import resolve_boq_type, stored_or_derived_boq_type
from app.modules.plans.schemas import SCHEMA_VERSION, UNSTATED_WALL_HEIGHT_M, PlanJSON

logger = logging.getLogger("construtiva.parsing.normalise")

DECIMALS = 3
MIN_POLYGON_AREA_M2 = 1e-4
MIN_WALL_LENGTH_M = 0.01

MIN_PLAUSIBLE_ROOM_M2 = 1.0
MAX_PLAUSIBLE_ROOM_M2 = 500.0
STATED_AREA_TOLERANCE = 0.10
MAX_ROOM_WARNINGS = 20

MIN_STATED_WALL_HEIGHT_M = 2.0
MAX_STATED_WALL_HEIGHT_M = 8.0

DEFAULT_WALL_THICKNESS_M = 0.20
EXTERIOR_WALL_THICKNESS_M = 0.23
INTERIOR_WALL_THICKNESS_M = 0.12
DEFAULT_OPENING_WIDTH_M = 1.0
DEFAULT_DOOR_HEIGHT_M = 2.1
DEFAULT_WINDOW_HEIGHT_M = 1.2
DEFAULT_COLUMN_SIZE_M = 0.23
ROGUE_ROOM_MARGIN_M = 0.20
EXTERIOR_EDGE_TOLERANCE_M = 0.25

FT_TO_M = 0.3048
IN_TO_M = 0.0254
SQFT_TO_M2 = 0.092903

UNIT_SCALES: dict[str, float] = {
    "m": 1.0,
    "meter": 1.0,
    "meters": 1.0,
    "metre": 1.0,
    "metres": 1.0,
    "ft": FT_TO_M,
    "feet": FT_TO_M,
    "foot": FT_TO_M,
    "'": FT_TO_M,
    "in": IN_TO_M,
    "inch": IN_TO_M,
    "inches": IN_TO_M,
    '"': IN_TO_M,
    "mm": 0.001,
    "millimeter": 0.001,
    "millimeters": 0.001,
    "millimetre": 0.001,
    "millimetres": 0.001,
    "cm": 0.01,
    "centimeter": 0.01,
    "centimeters": 0.01,
    "centimetre": 0.01,
    "centimetres": 0.01,
}

SCALE_SOURCES = {
    "dimension_label",
    "scale_bar",
    "stated_scale",
    "assumed",
    "scale_text",
    "user_reference",
}

LEVEL_NAMES = ("Ground Floor", "First Floor", "Second Floor", "Third Floor", "Fourth Floor")

_FEET_INCHES = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*['′]\s*(?:-?\s*(\d+(?:\.\d+)?)\s*(?:\"|″|''|in)?)?\s*$"
)


# --------------------------------------------------------------------------- numbers


def unit_scale(units: Any) -> float | None:
    """Metres per drawing unit, or None when the unit is not recognised."""
    return UNIT_SCALES.get(str(units or "m").lower().strip())


def to_metres(value: Any, scale: float = 1.0) -> float | None:
    """A length in metres, or None when `value` is not a usable number.

    Numbers and numeric strings are multiplied by `scale`. A feet-and-inches string
    such as `12'6"` is converted directly, whatever the drawing unit is.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value) * scale
    elif isinstance(value, str):
        text = value.strip()
        imperial = _FEET_INCHES.match(text)
        if imperial:
            number = float(imperial.group(1)) * FT_TO_M + float(imperial.group(2) or 0.0) * IN_TO_M
        else:
            try:
                number = float(text) * scale
            except ValueError:
                return None
    else:
        return None
    if not math.isfinite(number):
        return None
    return round(number, DECIMALS)


def _point(raw: Any, scale: float) -> list[float] | None:
    if isinstance(raw, dict):
        raw = [raw.get("x"), raw.get("y")]
    if not isinstance(raw, (list, tuple)) or len(raw) < 2:
        return None
    x, y = to_metres(raw[0], scale), to_metres(raw[1], scale)
    if x is None or y is None:
        return None
    return [x + 0.0, y + 0.0]  # + 0.0 turns -0.0 into 0.0


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


# -------------------------------------------------------------------------- polygons


def signed_area(polygon: list[list[float]]) -> float:
    """Shoelace area in plan coordinates; positive when the points run counter-clockwise."""
    total = 0.0
    count = len(polygon)
    for i in range(count):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % count]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def clean_polygon(points: Any, scale: float = 1.0) -> list[list[float]] | None:
    """The canonical form of a room outline, or None when it is not a usable polygon."""
    if not isinstance(points, (list, tuple)):
        return None
    cleaned: list[list[float]] = []
    for raw in points:
        point = _point(raw, scale)
        if point is None:
            continue
        if cleaned and cleaned[-1] == point:
            continue
        cleaned.append(point)
    while len(cleaned) > 1 and cleaned[0] == cleaned[-1]:
        cleaned.pop()
    if len(cleaned) < 3:
        return None
    area = signed_area(cleaned)
    if abs(area) < MIN_POLYGON_AREA_M2:
        return None
    if area < 0:
        cleaned.reverse()
    start = min(range(len(cleaned)), key=lambda i: (cleaned[i][1], cleaned[i][0]))
    return cleaned[start:] + cleaned[:start]


# ------------------------------------------------------------------- printed room size

_AREA_LABEL = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(sq\.?\s*ft\.?|sqft|sft|s\.f\.t\.?|sq\.?\s*m\.?|sqm|m2|m²)", re.IGNORECASE
)
_IMPERIAL_DIMS = re.compile(
    r"(\d+)\s*['′]\s*-?\s*(\d+)?\s*(?:\"|″|'')?\s*[x×]\s*(\d+)\s*['′]\s*-?\s*(\d+)?", re.IGNORECASE
)
_METRIC_DIMS = re.compile(
    r"(?<![\d.'′])(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)(?![\d'′\"])", re.IGNORECASE
)


def stated_area_m2(label: str | None) -> float | None:
    """The room area printed in a label, in m2, or None when the label states no size.

    Reads an area ("120 sq.ft", "14.5 sqm"), feet-and-inches sides (`12'6" X 14'`) or
    plain metric sides ("3.5 x 4.2", "350 x 420", "3500 x 4200"). Plain numbers carry no
    unit, so their size decides it: both sides from 1000 up are millimetres, from 50 up
    centimetres, otherwise metres. This is used for warnings only, never for geometry.
    """
    text = str(label or "")
    area = _AREA_LABEL.search(text)
    if area:
        value = float(area.group(1).replace(",", ""))
        is_feet = "f" in area.group(2).lower()
        return round(value * SQFT_TO_M2 if is_feet else value, DECIMALS)
    imperial = _IMPERIAL_DIMS.search(text)
    if imperial:
        f1, i1, f2, i2 = imperial.groups()
        side_a = int(f1) * FT_TO_M + int(i1 or 0) * IN_TO_M
        side_b = int(f2) * FT_TO_M + int(i2 or 0) * IN_TO_M
        return round(side_a * side_b, DECIMALS)
    metric = _METRIC_DIMS.search(text)
    if metric:
        side_a, side_b = float(metric.group(1)), float(metric.group(2))
        smaller = min(side_a, side_b)
        factor = 0.001 if smaller >= 1000 else 0.01 if smaller >= 50 else 1.0
        return round(side_a * factor * side_b * factor, DECIMALS)
    return None


# ----------------------------------------------------------------------- classifiers


def normalise_opening_type(raw: Any, sill: float = 0.0, height: float | None = None) -> str:
    """ "door" or "window" for any label a model or an older plan may carry."""
    text = str(raw or "").lower().strip()
    if any(word in text for word in ("door", "gate", "entrance", "entry", "shutter")):
        return "door"
    if any(word in text for word in ("window", "win", "vent", "glaz", "louv")):
        return "window"
    if text in ("d", "dr"):
        return "door"
    if text in ("w", "v"):
        return "window"
    # No usable label: an opening that starts above the floor or is short is a window.
    if sill >= 0.3 or (height is not None and 0 < height < 1.6):
        return "window"
    return "door"


_APARTMENT_WORDS = re.compile(r"\b(apartments?|flats?|condos?|condominiums?)\b")
_VILLA_WORDS = re.compile(r"\b(villas?|houses?|bungalows?|duplex|residences?|homes?)\b")


def normalise_building_type(raw: Any) -> str:
    """Whole words only: a "warehouse" is not a house."""
    text = str(raw or "").lower()
    if _APARTMENT_WORDS.search(text):
        return "apartment"
    if _VILLA_WORDS.search(text):
        return "villa"
    return "other"


def normalise_scale_source(raw: Any) -> str:
    text = str(raw or "").lower().strip().replace(" ", "_").replace("-", "_")
    return text if text in SCALE_SOURCES else "assumed"


def _wall_kind(raw: dict, start: list[float], end: list[float], bounds: tuple | None) -> str:
    for key in ("kind", "type"):
        value = str(raw.get(key) or "").lower().strip()
        if value in ("exterior", "interior"):
            return value
    if isinstance(raw.get("is_exterior"), bool):
        return "exterior" if raw["is_exterior"] else "interior"
    if bounds is None:
        return "interior"
    min_x, min_y, max_x, max_y = bounds
    tol = EXTERIOR_EDGE_TOLERANCE_M
    on_edge = (
        (abs(start[0] - min_x) < tol and abs(end[0] - min_x) < tol)
        or (abs(start[0] - max_x) < tol and abs(end[0] - max_x) < tol)
        or (abs(start[1] - min_y) < tol and abs(end[1] - min_y) < tol)
        or (abs(start[1] - max_y) < tol and abs(end[1] - max_y) < tol)
    )
    return "exterior" if on_edge else "interior"


# ------------------------------------------------------------------- wall synthesis


def synthesize_interior_walls_if_missing(
    walls: list[dict[str, Any]], rooms: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Add the partition and boundary walls a sparse extraction left out.

    When a plan already has a reasonable set of walls it is returned unchanged. Otherwise
    every axis-aligned room edge that no wall covers gets one: 0.12 m between two indoor
    rooms, 0.23 m on an outside edge. Added walls are flagged `inferred`.
    """
    interior_count = sum(1 for w in walls if w.get("kind") == "interior")
    if interior_count >= 8 and len(walls) >= 15:
        return walls

    result_walls = list(walls)
    wall_id_set = {w["id"] for w in walls}
    existing_segs = []
    for w in walls:
        p1 = w.get("start", [0, 0])
        p2 = w.get("end", [0, 0])
        existing_segs.append(
            (min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1]))
        )

    def is_covered(x1: float, y1: float, x2: float, y2: float) -> bool:
        is_h = abs(y1 - y2) < 0.08
        is_v = abs(x1 - x2) < 0.08
        for ex1, ey1, ex2, ey2 in existing_segs:
            if is_h and abs(ey1 - ey2) < 0.08 and abs(y1 - ey1) < 0.18:
                if max(0, min(x2, ex2) - max(x1, ex1)) > 0.35:
                    return True
            elif is_v and abs(ex1 - ex2) < 0.08 and abs(x1 - ex1) < 0.18:
                if max(0, min(y2, ey2) - max(y1, ey1)) > 0.35:
                    return True
        return False

    h_groups: dict[float, list[dict[str, Any]]] = defaultdict(list)
    v_groups: dict[float, list[dict[str, Any]]] = defaultdict(list)

    for r in rooms:
        pts = r.get("polygon", [])
        if len(pts) < 3:
            continue
        rid = r.get("id", "")
        is_out = r.get("kind", "indoor") in ("outdoor", "void")
        n = len(pts)
        for i in range(n):
            p1 = pts[i]
            p2 = pts[(i + 1) % n]
            x1, y1 = round(float(p1[0]), 2), round(float(p1[1]), 2)
            x2, y2 = round(float(p2[0]), 2), round(float(p2[1]), 2)
            if abs(x1 - x2) < 0.05 and abs(y1 - y2) < 0.05:
                continue
            if abs(y1 - y2) < 0.08:
                h_groups[round((y1 + y2) / 2, 1)].append(
                    {
                        "start": (min(x1, x2), (y1 + y2) / 2),
                        "end": (max(x1, x2), (y1 + y2) / 2),
                        "room_id": rid,
                        "is_outdoor": is_out,
                    }
                )
            elif abs(x1 - x2) < 0.08:
                v_groups[round((x1 + x2) / 2, 1)].append(
                    {
                        "start": ((x1 + x2) / 2, min(y1, y2)),
                        "end": ((x1 + x2) / 2, max(y1, y2)),
                        "room_id": rid,
                        "is_outdoor": is_out,
                    }
                )

    counter = 1
    # Sorted group keys keep the order of synthesised walls independent of room order.
    for _, segs in sorted(h_groups.items()):
        xs = sorted({s["start"][0] for s in segs} | {s["end"][0] for s in segs})
        for i in range(len(xs) - 1):
            xa, xb = xs[i], xs[i + 1]
            if xb - xa < 0.25:
                continue
            mid = (xa + xb) / 2
            matching = [s for s in segs if s["start"][0] <= mid <= s["end"][0]]
            if not matching or all(m["is_outdoor"] for m in matching):
                continue
            y_mean = sum(m["start"][1] for m in matching) / len(matching)
            if is_covered(xa, y_mean, xb, y_mean):
                continue
            r_ids = sorted({m["room_id"] for m in matching})
            is_interior = len(r_ids) > 1 and not any(m["is_outdoor"] for m in matching)
            wid = f"w_syn_h_{counter}"
            counter += 1
            if wid not in wall_id_set:
                wall_id_set.add(wid)
                result_walls.append(
                    {
                        "id": wid,
                        "start": [round(xa, 2), round(y_mean, 2)],
                        "end": [round(xb, 2), round(y_mean, 2)],
                        "thickness": INTERIOR_WALL_THICKNESS_M
                        if is_interior
                        else EXTERIOR_WALL_THICKNESS_M,
                        "kind": "interior" if is_interior else "exterior",
                        "inferred": True,
                    }
                )
                existing_segs.append((xa, y_mean, xb, y_mean))

    for _, segs in sorted(v_groups.items()):
        ys = sorted({s["start"][1] for s in segs} | {s["end"][1] for s in segs})
        for i in range(len(ys) - 1):
            ya, yb = ys[i], ys[i + 1]
            if yb - ya < 0.25:
                continue
            mid = (ya + yb) / 2
            matching = [s for s in segs if s["start"][1] <= mid <= s["end"][1]]
            if not matching or all(m["is_outdoor"] for m in matching):
                continue
            x_mean = sum(m["start"][0] for m in matching) / len(matching)
            if is_covered(x_mean, ya, x_mean, yb):
                continue
            r_ids = sorted({m["room_id"] for m in matching})
            is_interior = len(r_ids) > 1 and not any(m["is_outdoor"] for m in matching)
            wid = f"w_syn_v_{counter}"
            counter += 1
            if wid not in wall_id_set:
                wall_id_set.add(wid)
                result_walls.append(
                    {
                        "id": wid,
                        "start": [round(x_mean, 2), round(ya, 2)],
                        "end": [round(x_mean, 2), round(yb, 2)],
                        "thickness": INTERIOR_WALL_THICKNESS_M
                        if is_interior
                        else EXTERIOR_WALL_THICKNESS_M,
                        "kind": "interior" if is_interior else "exterior",
                        "inferred": True,
                    }
                )
                existing_segs.append((x_mean, ya, x_mean, yb))

    return result_walls


# ------------------------------------------------------------------------- one level


def _wall_height(raw_level: dict, scale: float) -> tuple[float, str]:
    """(wall_height, source). An unstated height is written as UNSTATED_WALL_HEIGHT_M."""
    height = to_metres(raw_level.get("wall_height"), scale)
    source = str(raw_level.get("wall_height_source") or "").lower().strip()
    plausible = (
        height is not None and MIN_STATED_WALL_HEIGHT_M <= height <= MAX_STATED_WALL_HEIGHT_M
    )
    if not plausible or source == "default":
        return UNSTATED_WALL_HEIGHT_M, "default"
    if source == "stated":
        return height, "stated"
    # No source given (an older plan): the parser's own placeholder means "not stated".
    if abs(height - UNSTATED_WALL_HEIGHT_M) < 0.05:
        return UNSTATED_WALL_HEIGHT_M, "default"
    return height, "stated"


def _room_height(raw: dict, scale: float) -> float | None:
    value = raw.get("height_m")
    if value is None:
        value = raw.get("ceiling_height_override")
    height = to_metres(value, scale)
    return height if height is not None and 1.5 < height <= 20.0 else None


def _opening_position(wall: dict | None, offset: float) -> list[float] | None:
    if wall is None:
        return None
    (x1, y1), (x2, y2) = wall["start"], wall["end"]
    length = math.hypot(x2 - x1, y2 - y1)
    if length <= 0:
        return None
    t = max(0.0, min(length, offset)) / length
    return [round(x1 + (x2 - x1) * t, DECIMALS) + 0.0, round(y1 + (y2 - y1) * t, DECIMALS) + 0.0]


def _offset_from_position(wall: dict | None, position: list[float] | None) -> float | None:
    if wall is None or position is None:
        return None
    (x1, y1), (x2, y2) = wall["start"], wall["end"]
    length = math.hypot(x2 - x1, y2 - y1)
    if length <= 0:
        return None
    t = ((position[0] - x1) * (x2 - x1) + (position[1] - y1) * (y2 - y1)) / length
    return round(max(0.0, min(length, t)), DECIMALS)


def _normalise_level(
    raw: dict, position: int, scale: float, *, canonical: bool, warnings: list[str]
) -> dict:
    wall_height, height_source = _wall_height(raw, scale)
    name = _text(raw.get("name")) or (
        LEVEL_NAMES[position] if position < len(LEVEL_NAMES) else f"Level {position}"
    )

    # Each level gets its own frame with the origin at the top-left of what is drawn, so
    # the result does not depend on where the model happened to place the floor plan.
    origin = _level_origin(raw, scale) if canonical else (0.0, 0.0)

    def placed(raw_point: Any) -> list[float] | None:
        point = _point(raw_point, scale)
        if point is None:
            return None
        return [
            round(point[0] - origin[0], DECIMALS) + 0.0,
            round(point[1] - origin[1], DECIMALS) + 0.0,
        ]

    # Walls
    raw_walls = [w for w in (raw.get("walls") or []) if isinstance(w, dict)]
    points: list[tuple[dict, list[float], list[float]]] = []
    for w in raw_walls:
        start, end = placed(w.get("start")), placed(w.get("end"))
        if start is None or end is None:
            warnings.append(
                f"{name}: wall {w.get('id')!r} has unreadable end points and was dropped."
            )
            continue
        if math.hypot(end[0] - start[0], end[1] - start[1]) < MIN_WALL_LENGTH_M:
            if canonical:
                continue
        points.append((w, start, end))
    bounds = None
    if points:
        xs = [p[0] for _, s, e in points for p in (s, e)]
        ys = [p[1] for _, s, e in points for p in (s, e)]
        bounds = (min(xs), min(ys), max(xs), max(ys))

    walls: list[dict] = []
    seen_wall_ids: set[str] = set()
    for index, (w, start, end) in enumerate(points):
        wall_id = str(w.get("id") if w.get("id") is not None else f"w_{index}")
        if wall_id in seen_wall_ids:
            wall_id = f"{wall_id}__{index}"
        seen_wall_ids.add(wall_id)
        kind = _wall_kind(w, start, end, bounds)
        thickness = to_metres(w.get("thickness"), scale)
        if thickness is None or thickness <= 0:
            thickness = DEFAULT_WALL_THICKNESS_M
        wall = {
            "id": wall_id,
            "start": start,
            "end": end,
            "thickness": thickness,
            "kind": kind,
            "is_exterior": kind == "exterior",
            "inferred": bool(w.get("inferred", False)),
        }
        walls.append(wall if canonical else _with_extras(w, wall))

    # Openings (offsets are along the wall as the model drew it)
    wall_by_id = {w["id"]: w for w in walls}
    openings: list[dict] = []
    for index, op in enumerate(o for o in (raw.get("openings") or []) if isinstance(o, dict)):
        wall_id = str(op.get("wall_id"))
        wall = wall_by_id.get(wall_id)
        sill_raw = op.get("sill") if op.get("sill") is not None else op.get("sill_height")
        sill = to_metres(sill_raw, scale)
        sill = sill if sill is not None and sill >= 0 else 0.0
        height = to_metres(op.get("height"), scale)
        op_type = normalise_opening_type(op.get("type") or op.get("kind"), sill, height)
        if height is None or height <= 0:
            height = DEFAULT_DOOR_HEIGHT_M if op_type == "door" else DEFAULT_WINDOW_HEIGHT_M
        width = to_metres(op.get("width"), scale)
        if width is None or width <= 0:
            width = DEFAULT_OPENING_WIDTH_M
        offset = to_metres(op.get("offset"), scale)
        if offset is None:
            offset = _offset_from_position(wall, placed(op.get("position")))
        if offset is None or offset < 0:
            offset = 0.0
        opening = {
            "id": str(op.get("id") if op.get("id") is not None else f"op_{index}"),
            "wall_id": wall_id,
            "type": op_type,
            "offset": offset,
            "width": width,
            "height": height,
            "sill": sill,
            "sill_height": sill,
            "inferred": bool(op.get("inferred", False)),
        }
        openings.append(opening if canonical else _with_extras(op, opening))

    if canonical:
        walls, openings = deduplicate_and_merge_walls(walls, openings)

    # Rooms
    rooms: list[dict] = []
    for index, r in enumerate(room for room in (raw.get("rooms") or []) if isinstance(room, dict)):
        room_name = _text(r.get("name")) or "Room"
        if canonical:
            polygon = clean_polygon([placed(pt) for pt in _as_list(r.get("polygon"))])
        else:
            polygon = _plain_polygon(r, scale)
        if polygon is None:
            warnings.append(f"{name}: room '{room_name}' has no usable outline and was dropped.")
            continue
        if canonical and bounds is not None:
            cx = sum(p[0] for p in polygon) / len(polygon)
            cy = sum(p[1] for p in polygon) / len(polygon)
            m = ROGUE_ROOM_MARGIN_M
            if not (bounds[0] - m <= cx <= bounds[2] + m and bounds[1] - m <= cy <= bounds[3] + m):
                warnings.append(
                    f"{name}: room '{room_name}' lies outside the building outline and was dropped."
                )
                continue
        reported = str(r.get("kind") or "").lower().strip()
        if canonical:
            kind: str | None = parser_room_kind(room_name, reported)
        else:
            kind = reported if reported in ROOM_KINDS else None
        # Only indoor rooms are typed. A fresh parse applies the keyword rules, which win
        # unless they return OTHER; a stored plan keeps the type it already has.
        if kind != "indoor":
            boq_type = None
        elif canonical:
            boq_type = resolve_boq_type(room_name, r.get("boq_type"))
        else:
            boq_type = stored_or_derived_boq_type(room_name, r.get("boq_type"))
        room = {
            "id": str(r.get("id") if r.get("id") is not None else f"room_{index}"),
            "name": room_name,
            "kind": kind,
            "boq_type": boq_type,
            "polygon": polygon,
            "height_m": _room_height(r, scale),
            "is_double_height_void": bool(r.get("is_double_height_void", False)),
        }
        # Keys other readers own (`type` belongs to the 3D adapter) pass through as is.
        rooms.append(room if canonical else _with_extras(r, room))

    if canonical:
        walls = synthesize_interior_walls_if_missing(walls, rooms)
        for w in walls:
            w.setdefault("is_exterior", w.get("kind") == "exterior")

    # Columns
    columns: list[dict] = []
    for index, col in enumerate(c for c in (raw.get("columns") or []) if isinstance(c, dict)):
        position_pt = placed(col.get("position"))
        if position_pt is None:
            continue
        width = to_metres(col.get("width"), scale)
        depth = to_metres(col.get("depth"), scale)
        column = {
            "id": str(col.get("id") if col.get("id") is not None else f"col_{index}"),
            "position": position_pt,
            "width": width if width and width > 0 else DEFAULT_COLUMN_SIZE_M,
            "depth": depth if depth and depth > 0 else DEFAULT_COLUMN_SIZE_M,
        }
        columns.append(column if canonical else _with_extras(col, column))

    if canonical:
        walls, openings, rooms, columns = _canonical_order(
            position, walls, openings, rooms, columns
        )

    wall_by_id = {w["id"]: w for w in walls}
    for op in openings:
        op["position"] = _opening_position(wall_by_id.get(op["wall_id"]), op["offset"])
        if op["wall_id"] not in wall_by_id:
            warnings.append(f"{name}: opening {op['id']} refers to a wall that is not in the plan.")

    if canonical:
        _room_scale_warnings(name, rooms, warnings)

    elevation = to_metres(raw.get("elevation"), scale)
    level = {
        "index": position,
        "name": name,
        "elevation": elevation,  # filled by the caller when None
        "wall_height": wall_height,
        "wall_height_source": height_source,
        "walls": walls,
        "openings": openings,
        "rooms": rooms,
        "columns": columns,
    }
    return level if canonical else _with_extras(raw, level)


def _with_extras(original: dict, built: dict) -> dict:
    """`built`, plus every key of `original` that the normaliser does not manage."""
    return {**{k: v for k, v in original.items() if k not in built}, **built}


def _as_list(value: Any) -> list:
    return list(value) if isinstance(value, (list, tuple)) else []


def _level_origin(raw_level: dict, scale: float) -> tuple[float, float]:
    """Smallest x and y of everything drawn on a level, in metres."""
    xs: list[float] = []
    ys: list[float] = []

    def take(raw_point: Any) -> None:
        point = _point(raw_point, scale)
        if point is not None:
            xs.append(point[0])
            ys.append(point[1])

    for wall in _as_list(raw_level.get("walls")):
        if isinstance(wall, dict):
            take(wall.get("start"))
            take(wall.get("end"))
    for room in _as_list(raw_level.get("rooms")):
        if isinstance(room, dict):
            for raw_point in _as_list(room.get("polygon")):
                take(raw_point)
    for column in _as_list(raw_level.get("columns")):
        if isinstance(column, dict):
            take(column.get("position"))
    return (min(xs), min(ys)) if xs else (0.0, 0.0)


def _plain_polygon(room: dict, scale: float) -> list[list[float]] | None:
    """Upgrade mode: convert the points, keep their order and start vertex."""
    pts = [p for p in (_point(raw, scale) for raw in (room.get("polygon") or [])) if p is not None]
    return pts if len(pts) >= 3 else None


def _canonical_order(
    level: int, walls: list[dict], openings: list[dict], rooms: list[dict], columns: list[dict]
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Sort every element by its geometry and replace model-chosen ids with stable ones."""

    def wall_key(w: dict) -> tuple:
        lo, hi = sorted((tuple(reversed(w["start"])), tuple(reversed(w["end"]))))
        return (lo, hi, w["thickness"], w["kind"])

    walls = sorted(walls, key=wall_key)
    wall_ids = {}
    for number, w in enumerate(walls, start=1):
        wall_ids.setdefault(w["id"], f"L{level}-W{number:02d}")
        w["id"] = f"L{level}-W{number:02d}"
    wall_rank = {w["id"]: number for number, w in enumerate(walls)}

    for op in openings:
        op["wall_id"] = wall_ids.get(op["wall_id"], op["wall_id"])
    openings = sorted(
        openings,
        key=lambda o: (
            wall_rank.get(o["wall_id"], len(walls)),
            o["offset"],
            o["type"],
            o["width"],
            o["height"],
        ),
    )
    for number, op in enumerate(openings, start=1):
        op["id"] = f"L{level}-O{number:02d}"

    def room_key(r: dict) -> tuple:
        xs = [p[0] for p in r["polygon"]]
        ys = [p[1] for p in r["polygon"]]
        return (min(ys), min(xs), round(abs(signed_area(r["polygon"])), DECIMALS), r["name"])

    rooms = sorted(rooms, key=room_key)
    for number, r in enumerate(rooms, start=1):
        r["id"] = f"L{level}-R{number:02d}"

    columns = sorted(
        columns, key=lambda c: (c["position"][1], c["position"][0], c["width"], c["depth"])
    )
    for number, col in enumerate(columns, start=1):
        col["id"] = f"L{level}-C{number:02d}"
    return walls, openings, rooms, columns


def _room_scale_warnings(level_name: str, rooms: list[dict], warnings: list[str]) -> None:
    raised = 0
    hidden = 0

    def warn(message: str) -> None:
        nonlocal raised, hidden
        if raised < MAX_ROOM_WARNINGS:
            warnings.append(message)
            raised += 1
        else:
            hidden += 1

    for room in rooms:
        area = abs(signed_area(room["polygon"]))
        label = f"{level_name}: room '{room['name']}'"
        if room["kind"] in ("indoor", "semi_open"):
            if area < MIN_PLAUSIBLE_ROOM_M2:
                warn(f"{label} is only {area:.2f} m2. Check the drawing scale.")
            elif area > MAX_PLAUSIBLE_ROOM_M2:
                warn(f"{label} is {area:.2f} m2. Check the drawing scale.")
        stated = stated_area_m2(room["name"])
        if stated and stated > 0 and abs(area - stated) / stated > STATED_AREA_TOLERANCE:
            warn(
                f"{label} is drawn as {area:.2f} m2 but its label states {stated:.2f} m2 "
                f"({(area - stated) / stated:+.0%})."
            )
    if hidden:
        warnings.append(f"{level_name}: {hidden} more room size warning(s) not listed.")


# ------------------------------------------------------------------------ whole plan


def _run(raw: Any, *, canonical: bool) -> dict:
    if not isinstance(raw, dict):
        raise ValueError(f"A plan must be a JSON object, got {type(raw).__name__}.")
    if isinstance(raw.get("plan_json"), dict) and "levels" not in raw:
        raw = raw["plan_json"]  # a database row wrapping the plan
    raw_levels = raw.get("levels")
    if not isinstance(raw_levels, list) or not raw_levels:
        raise ValueError("PlanJSON is missing 'levels'.")

    warnings: list[str] = [str(w) for w in (raw.get("warnings") or []) if isinstance(w, str)]
    scale = unit_scale(raw.get("units"))
    if scale is None:
        warnings.append(f"Unknown drawing unit {raw.get('units')!r}; lengths were read as metres.")
        scale = 1.0

    ordered = [lvl for lvl in raw_levels if isinstance(lvl, dict)]
    if not ordered:
        raise ValueError("PlanJSON 'levels' holds no level objects.")
    if canonical:
        # Lowest floor first: by the index the source gave, then by its position.
        indexed = list(enumerate(ordered))
        indexed.sort(key=lambda item: (_level_rank(item[1], item[0]), item[0]))
        ordered = [lvl for _, lvl in indexed]

    levels = [
        _normalise_level(lvl, position, scale, canonical=canonical, warnings=warnings)
        for position, lvl in enumerate(ordered)
    ]
    # A level with no stated elevation sits on top of the one below it. In parser output
    # an upper level that repeats the elevation below it was not really given one.
    running = 0.0
    for position, level in enumerate(levels):
        stacked_wrongly = (
            canonical
            and position > 0
            and level["elevation"] is not None
            and (level["elevation"] <= levels[position - 1]["elevation"])
        )
        if level["elevation"] is None or stacked_wrongly:
            level["elevation"] = round(running, DECIMALS)
        running = level["elevation"] + level["wall_height"]

    plan = {
        "schema_version": SCHEMA_VERSION,
        "version": raw.get("version") if isinstance(raw.get("version"), int) else 1,
        "units": "m",
        "building_type": normalise_building_type(raw.get("building_type")),
        "scale_source": normalise_scale_source(raw.get("scale_source")),
        "project_title": _text(raw.get("project_title")),
        "subject": _text(raw.get("subject")),
        "client": _text(raw.get("client")),
        "architect": _text(raw.get("architect")),
        "levels": levels,
        "confidence": {},
        "warnings": [],
        "parser": raw.get("parser") if isinstance(raw.get("parser"), dict) else None,
    }

    if not canonical:
        plan = _with_extras(raw, plan)

    kept_confidence = raw.get("confidence")
    if not canonical and isinstance(kept_confidence, dict) and kept_confidence:
        plan["confidence"] = kept_confidence
    else:
        try:
            plan["confidence"] = compute_plan_confidence(plan)
        except Exception as e:  # scoring must never cost the user their parsed plan
            logger.warning("plan confidence could not be computed: %s", e)
            plan["confidence"] = {"overall": 0.0}
            warnings.append("The plan could not be scored for confidence; review it carefully.")

    seen: set[str] = set()
    plan["warnings"] = [w for w in warnings if not (w in seen or seen.add(w))]

    return PlanJSON.model_validate(plan).model_dump()


def _level_rank(level: dict, position: int) -> int:
    index = level.get("index")
    return index if isinstance(index, int) and not isinstance(index, bool) else position


def normalise_plan(raw: Any) -> dict:
    """Canonical PlanJSON 2.0 from parser output (or any plan-shaped dict).

    Raises ValueError when `raw` has no levels, and pydantic.ValidationError if the
    result still does not fit the schema.
    """
    return _run(raw, canonical=True)


def upgrade_plan(raw: Any) -> dict:
    """PlanJSON 2.0 from an older stored plan: defaults filled, nothing else changed.

    Ids, element order, polygons and walls stay exactly as stored, so anything that
    refers to the stored plan by id keeps working.
    """
    return _run(raw, canonical=False)
