"""Geometry helpers shared by the renderer, validator and exporters.

Pure functions over the FloorPlan schema. All values are cm.
"""

from dataclasses import dataclass

from shapely.affinity import translate
from shapely.geometry import LineString, Polygon, box
from shapely.geometry import Point as ShpPoint
from shapely.ops import unary_union

from app.modules.ai.floorplan.rules import WALL_EXTERIOR_CM, WALL_INTERIOR_CM
from app.modules.ai.floorplan.schemas.plan import Door, FloorPlan, Room, Window

Point = tuple[float, float]

# Unit vector pointing out of a room through each of its walls.
OUTWARD: dict[str, Point] = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}


def pool_water(room: Room) -> tuple[float, float, float, float]:
    """Water rectangle (x, y, w, h) of a pool room: the room minus its walkway."""
    from app.modules.ai.floorplan.rules import POOL_WALKWAY_CM

    lo, hi = POOL_WALKWAY_CM
    walk = max(lo, min(hi, (min(room.w, room.h) - 300) / 2))
    walk = min(walk, min(room.w, room.h) / 4)
    return (room.x + walk, room.y + walk, room.w - 2 * walk, room.h - 2 * walk)


def room_box(room: Room) -> Polygon:
    return box(room.x, room.y, room.x2, room.y2)


def wall_line(room: Room, wall: str) -> tuple[Point, Point]:
    """Centre line of a room wall, from its start (west or north end) to its end."""
    if wall == "north":
        return (room.x, room.y), (room.x2, room.y)
    if wall == "south":
        return (room.x, room.y2), (room.x2, room.y2)
    if wall == "west":
        return (room.x, room.y), (room.x, room.y2)
    return (room.x2, room.y), (room.x2, room.y2)


def wall_length(room: Room, wall: str) -> int:
    return room.w if wall in ("north", "south") else room.h


@dataclass(frozen=True)
class OpeningSpan:
    """An opening (door or window) located on a wall centre line."""

    start: Point
    end: Point
    inward: Point  # unit normal pointing into the owning room
    horizontal: bool


def opening_span(room: Room, wall: str, offset: float, width: float) -> OpeningSpan:
    (x1, y1), (x2, y2) = wall_line(room, wall)
    horizontal = y1 == y2
    if horizontal:
        start, end = (x1 + offset, y1), (x1 + offset + width, y1)
    else:
        start, end = (x1, y1 + offset), (x1, y1 + offset + width)
    ox, oy = OUTWARD[wall]
    return OpeningSpan(start, end, (-ox, -oy), horizontal)


def door_span(plan: FloorPlan, door: Door) -> OpeningSpan:
    return opening_span(plan.room(door.to_room), door.wall, door.offset, door.width)


def window_span(plan: FloorPlan, window: Window) -> OpeningSpan:
    return opening_span(plan.room(window.room), window.wall, window.offset, window.width)


def enclosed_union(plan: FloorPlan):
    """Union of all enclosed (non-open) rooms."""
    return unary_union([room_box(r) for r in plan.rooms if not r.is_open])


def split_wall_edges(plan: FloorPlan) -> tuple[list[LineString], list[LineString]]:
    """Split every enclosed room's walls into exterior and interior centre-line pieces.

    A piece is interior when an enclosed room lies on the other side of it; otherwise
    (plot edge, courtyard, garden, empty space) it is exterior.
    """
    inside = enclosed_union(plan)
    exterior: list[LineString] = []
    interior: list[LineString] = []
    for room in plan.rooms:
        if room.is_open:
            continue
        for wall, (ox, oy) in OUTWARD.items():
            a, b = wall_line(room, wall)
            edge = LineString([a, b])
            # Probe 1 cm outside the room: the part of the probe inside another
            # enclosed room is a shared (interior) wall.
            probe = LineString([(a[0] + ox, a[1] + oy), (b[0] + ox, b[1] + oy)])
            shared = probe.intersection(inside)
            shared_back = translate(shared, -ox, -oy)
            exterior.extend(_lines(edge.difference(shared_back.buffer(0.01))))
            interior.extend(_lines(edge.intersection(shared_back.buffer(0.01))))
    return exterior, interior


def wall_polygon(plan: FloorPlan):
    """Filled wall mass: exterior and interior wall pieces buffered to thickness, unioned.

    Square caps make corners and T-junctions join cleanly.
    """
    exterior, interior = split_wall_edges(plan)
    parts = [
        ln.buffer(WALL_EXTERIOR_CM / 2, cap_style="square", join_style="mitre") for ln in exterior
    ]
    parts += [
        ln.buffer(WALL_INTERIOR_CM / 2, cap_style="square", join_style="mitre") for ln in interior
    ]
    return unary_union(parts) if parts else Polygon()


def opening_is_exterior(plan: FloorPlan, span: OpeningSpan) -> bool:
    """True if the far side of the opening is outside or an open area."""
    mx = (span.start[0] + span.end[0]) / 2 - span.inward[0]
    my = (span.start[1] + span.end[1]) / 2 - span.inward[1]
    return not enclosed_union(plan).contains(ShpPoint(mx, my))


def door_clear_zone(plan: FloorPlan, door: Door, room_id: str) -> Polygon | None:
    """Area inside `room_id` that a door needs free (its swing, or a strip for open doors)."""
    if room_id not in (door.to_room, door.from_room):
        return None
    sp = door_span(plan, door)
    if door.swing == "none":
        depth, into_to = 60, room_id == door.to_room
    else:
        into_to = door.swing.startswith("in")
        if (door.to_room if into_to else door.from_room) != room_id:
            return None
        depth = door.width
    nx, ny = sp.inward if into_to else (-sp.inward[0], -sp.inward[1])
    (x1, y1), (x2, y2) = sp.start, sp.end
    x3, y3 = x2 + nx * depth, y2 + ny * depth
    return box(min(x1, x3), min(y1, y3), max(x1, x2, x3), max(y1, y2, y3))


OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}

Interval = tuple[float, float]


def span_interval(span: OpeningSpan) -> Interval:
    """Opening extent along its wall axis (x for horizontal walls, y for vertical)."""
    i = 0 if span.horizontal else 1
    a, b = span.start[i], span.end[i]
    return (min(a, b), max(a, b))


def _line_interval(geom, horizontal: bool) -> Interval | None:
    if geom.is_empty or not isinstance(geom, LineString) or geom.length <= 0.5:
        return None
    i = 0 if horizontal else 1
    vals = [c[i] for c in geom.coords]
    return (min(vals), max(vals))


def shared_wall_interval(room: Room, wall: str, other: Room) -> Interval | None:
    """Part of `room`'s `wall` that is also `other`'s opposite wall, or None."""
    a = LineString(wall_line(room, wall))
    b = LineString(wall_line(other, OPPOSITE[wall]))
    return _line_interval(a.intersection(b), wall in ("north", "south"))


def exterior_intervals(plan: FloorPlan, room: Room, wall: str) -> list[Interval]:
    """Parts of a room wall whose far side is outside the plot or an open area."""
    ox, oy = OUTWARD[wall]
    a, b = wall_line(room, wall)
    edge = LineString([a, b])
    probe = LineString([(a[0] + ox, a[1] + oy), (b[0] + ox, b[1] + oy)])
    shared = translate(probe.intersection(enclosed_union(plan)), -ox, -oy)
    horizontal = wall in ("north", "south")
    out = [_line_interval(g, horizontal) for g in _lines(edge.difference(shared.buffer(0.01)))]
    return sorted(i for i in out if i is not None)


def interval_within(inner: Interval, outer: Interval, clearance: float = 0.0) -> bool:
    return inner[0] - clearance >= outer[0] - 1e-6 and inner[1] + clearance <= outer[1] + 1e-6


def opening_cut(span: OpeningSpan, depth: float) -> Polygon:
    """Rectangle that removes wall material for an opening."""
    (x1, y1), (x2, y2) = span.start, span.end
    half = depth / 2
    if span.horizontal:
        return box(min(x1, x2), y1 - half, max(x1, x2), y1 + half)
    return box(x1 - half, min(y1, y2), x1 + half, max(y1, y2))


def _lines(geom) -> list[LineString]:
    if geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom] if geom.length > 0.5 else []
    out: list[LineString] = []
    for g in getattr(geom, "geoms", []):
        out.extend(_lines(g))
    return out
