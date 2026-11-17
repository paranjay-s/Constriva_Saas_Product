"""The space we measure: typed dimensions, or rooms of a saved / uploaded PlanJSON.

PlanJSON (metres) -> RoomGeom (feet): area from the room polygon, its sides in order,
doors and windows from the plan walls placed on the side they touch, ceiling height from
the level's wall_height.

Room matching: exact name, then the same room kind via data/room_aliases.json
("modular kitchen" = "kitchen", "washroom" = "bathroom"). Several matches -> one
question with the options; none -> the list of rooms.
"""

import re
from dataclasses import dataclass, field

from app.modules.ai.material_agent.data_files import application_rules, room_aliases
from app.modules.ai.material_agent.geometry import rect_room
from app.modules.ai.material_agent.schemas import (
    ManualSpace,
    OpeningGeom,
    RoomGeom,
    SideGeom,
    TargetSpace,
    WallGeom,
)
from app.modules.ai.material_agent.units import fmt, m_to_ft, to_ft

ON_SIDE_TOL_M = 0.35  # an opening this close to a room side is on that side (wall thickness)
DIRECTIONS = {0: "south", 1: "east", 2: "north", 3: "west"}


# ----------------------------------------------------------------- manual


def manual_target(space: ManualSpace) -> TargetSpace:
    rules = application_rules()
    unit = space.unit
    if space.kind == "wall":
        width = to_ft(space.length, unit)
        if space.height is None:
            raise ValueError("A wall needs a width and a height.")
        height = to_ft(space.height, unit)
        label = space.label or "Wall"
        openings = [
            OpeningGeom(
                kind="door",
                width_ft=float(rules["door_width_ft"]),
                height_ft=float(rules["door_height_ft"]),
            )
            for _ in range(space.doors)
        ] + [
            OpeningGeom(
                kind="window",
                width_ft=float(rules["window_width_ft"]),
                height_ft=float(rules["window_height_ft"]),
            )
            for _ in range(space.windows)
        ]
        return TargetSpace(
            source="manual",
            label=f"{label}, {fmt(width)} × {fmt(height)} ft",
            wall=WallGeom(width_ft=width, height_ft=height, label=label, openings=openings),
        )
    if space.width is None:
        raise ValueError("A room needs a length and a width.")
    length, width = to_ft(space.length, unit), to_ft(space.width, unit)
    height = (
        to_ft(space.height, unit) if space.height else float(rules["default_ceiling_height_ft"])
    )
    name = space.label or "Room"
    room = rect_room(
        name,
        length,
        width,
        height,
        kind=room_kind(name) or "",
        doors=space.doors,
        windows=space.windows,
    )
    h_txt = f" × {fmt(height)}" if space.height else ""
    return TargetSpace(
        source="manual", label=f"{name}, {fmt(length)} × {fmt(width)}{h_txt} ft", room=room
    )


# -------------------------------------------------------------- plan rooms

_DIM_TEXT = re.compile(
    r"\d+\s*['′]\s*-?\s*\d*\s*(\"|″)?\s*[x×X]\s*\d+\s*['′]?\s*-?\s*\d*\s*(\"|″)?"
)
_NUMBERS_X = re.compile(r"\d+(\.\d+)?\s*[x×X]\s*\d+(\.\d+)?")


def clean_name(name: str) -> str:
    """'KITCHEN 10\\'0 X 8\\'0' -> 'Kitchen'."""
    s = _DIM_TEXT.sub(" ", name or "")
    s = _NUMBERS_X.sub(" ", s)
    s = re.sub(r"[_\s]+", " ", s).strip(" -,:")
    return s.title() if s.isupper() or s.islower() else s


def _poly_area(pts: list[list[float]]) -> float:
    return (
        abs(
            sum(
                pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                for i in range(len(pts))
            )
        )
        / 2
    )


def _dist_point_segment(
    p: tuple[float, float], a: list[float], b: list[float]
) -> tuple[float, float]:
    """(distance, position along a->b in 0..1)."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    ln2 = dx * dx + dy * dy
    if ln2 == 0:
        return ((p[0] - ax) ** 2 + (p[1] - ay) ** 2) ** 0.5, 0.0
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / ln2))
    cx, cy = ax + t * dx, ay + t * dy
    return ((p[0] - cx) ** 2 + (p[1] - cy) ** 2) ** 0.5, t


def _side_label(a: list[float], b: list[float], centroid: tuple[float, float]) -> str:
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    dx, dy = mx - centroid[0], my - centroid[1]
    if abs(dx) > abs(dy):
        return "east wall" if dx > 0 else "west wall"
    return "north wall" if dy > 0 else "south wall"


def _opening_points(level: dict) -> list[tuple[str, tuple[float, float], float, float]]:
    """(kind, centre point m, width m, height m) for each door/window of the level."""
    walls = {w.get("id"): w for w in level.get("walls") or []}
    out = []
    for o in level.get("openings") or []:
        w = walls.get(o.get("wall_id"))
        if not w:
            continue
        (sx, sy), (ex, ey) = w["start"], w["end"]
        ln = ((ex - sx) ** 2 + (ey - sy) ** 2) ** 0.5 or 1.0
        width = float(o.get("width") or 0.9)
        off = float(o.get("offset") or 0.0) + width / 2
        px, py = sx + (ex - sx) * off / ln, sy + (ey - sy) * off / ln
        kind = "door" if o.get("type") == "door" else "window"
        height = float(o.get("height") or (2.1 if kind == "door" else 1.2))
        out.append((kind, (px, py), width, height))
    return out


def rooms_from_plan(plan_json: dict) -> list[RoomGeom]:
    levels = plan_json.get("levels") or []
    if not levels:
        return []
    level = levels[0]
    height_ft = m_to_ft(float(level.get("wall_height") or 0)) or float(
        application_rules()["default_ceiling_height_ft"]
    )
    openings = _opening_points(level)
    rooms: list[RoomGeom] = []
    for r in level.get("rooms") or []:
        pts = [list(map(float, p)) for p in r.get("polygon") or [] if len(p) >= 2]
        if len(pts) > 1 and pts[0] == pts[-1]:
            pts = pts[:-1]
        if len(pts) < 3:
            continue
        name = clean_name(r.get("name") or r.get("tag") or r.get("id") or "Room") or "Room"
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        sides = []
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            ln = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
            sides.append(
                SideGeom(index=i, length_ft=m_to_ft(ln), label=_side_label(a, b, (cx, cy)))
            )
        # two sides with the same compass label get numbered
        labels = [s.label for s in sides]
        for s in sides:
            if labels.count(s.label) > 1:
                s.label = f"{s.label} ({fmt(s.length_ft)} ft)"
        room_openings = []
        for kind, p, w, h in openings:
            best = min(
                (
                    (_dist_point_segment(p, pts[i], pts[(i + 1) % len(pts)])[0], i)
                    for i in range(len(pts))
                ),
                default=(99.0, -1),
            )
            if best[0] <= ON_SIDE_TOL_M:
                room_openings.append(
                    OpeningGeom(kind=kind, width_ft=m_to_ft(w), height_ft=m_to_ft(h), side=best[1])
                )
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        rooms.append(
            RoomGeom(
                name=name,
                kind=room_kind(name) or room_kind(str(r.get("tag") or "")) or "",
                area_sqft=_poly_area(pts) / 0.3048**2,
                height_ft=height_ft,
                sides=sides,
                openings=room_openings,
                length_ft=m_to_ft(max(xs) - min(xs)),
                width_ft=m_to_ft(max(ys) - min(ys)),
            )
        )
    return rooms


def room_label(room: RoomGeom) -> str:
    if room.length_ft and room.width_ft:
        long, short = max(room.length_ft, room.width_ft), min(room.length_ft, room.width_ft)
        return f"{room.name}, {fmt(long)} × {fmt(short)} ft"
    return f"{room.name}, {fmt(room.area_sqft)} sq ft"


# ---------------------------------------------------------------- matching


def _norm(s: str) -> str:
    s = s.lower().replace("’", "'")
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def room_kind(name: str) -> str | None:
    """'Modular kitchen' -> 'kitchen'; longest alias wins ('master bedroom' over 'bedroom')."""
    n = _norm(name)
    if not n:
        return None
    best: tuple[int, str] | None = None
    for kind, aliases in room_aliases().items():
        for alias in aliases:
            a = _norm(alias)
            if (
                a
                and re.search(rf"(^| ){re.escape(a)}( |$|\d)", n)
                and (best is None or len(a) > best[0])
            ):
                best = (len(a), kind)
    return best[1] if best else None


@dataclass
class RoomMatch:
    room: RoomGeom | None = None
    options: list[RoomGeom] = field(default_factory=list)  # ambiguous
    status: str = "ok"  # ok, ambiguous, not_found


def match_room(rooms: list[RoomGeom], query: str) -> RoomMatch:
    q = _norm(query)
    if not q:
        return RoomMatch(status="not_found")
    exact = [r for r in rooms if _norm(r.name) == q]
    if len(exact) == 1:
        return RoomMatch(room=exact[0])
    if len(exact) > 1:
        return RoomMatch(options=exact, status="ambiguous")
    num = re.search(r"\d+", q)
    kind = room_kind(q)
    if kind:
        same = [r for r in rooms if (r.kind or room_kind(r.name)) == kind]
        # "master bedroom" also counts as a "bedroom" when someone says "bedroom 2"
        if kind == "bedroom" and not num:
            same += [
                r
                for r in rooms
                if (r.kind or room_kind(r.name)) == "master_bedroom" and r not in same
            ]
        if num:
            numbered = [r for r in same if re.search(rf"(^|\D){num.group()}(\D|$)", r.name)]
            if len(numbered) == 1:
                return RoomMatch(room=numbered[0])
        if len(same) == 1:
            return RoomMatch(room=same[0])
        if len(same) > 1:
            return RoomMatch(options=same, status="ambiguous")
    contains = [r for r in rooms if q in _norm(r.name) or _norm(r.name) in q]
    if len(contains) == 1:
        return RoomMatch(room=contains[0])
    if len(contains) > 1:
        return RoomMatch(options=contains, status="ambiguous")
    return RoomMatch(status="not_found")


def plan_target(
    room: RoomGeom,
    source: str,
    project_id: str | None,
    project_name: str | None,
    plan_name: str | None = None,
) -> TargetSpace:
    where = (
        f"from project {project_name}"
        if source == "project" and project_name
        else f"from {plan_name or 'the uploaded plan'}"
    )
    return TargetSpace(
        source="project" if source == "project" else "uploaded_plan",
        label=f"{room_label(room)}, {where}",
        room=room,
        project_id=project_id,
        project_name=project_name,
    )
