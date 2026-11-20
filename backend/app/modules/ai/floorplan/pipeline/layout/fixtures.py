"""Place furniture and fixture symbols inside rooms (code, never the LLM).

Each fixture is placed with its back against a wall (rotation 0 = back to north,
90 = east, 180 = south, 270 = west), clear of door swings and other fixtures. A fixture
that does not fit is skipped; furniture never blocks a plan.
"""

from shapely.affinity import translate
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from app.modules.ai.floorplan.geometry import door_clear_zone, exterior_intervals
from app.modules.ai.floorplan.render.symbols import SYMBOLS, footprint
from app.modules.ai.floorplan.schemas.plan import Fixture, FloorPlan, Room

INSET = 14  # distance from the wall centre line to the fixture back (covers wall half-thickness)
GAP = 8
ROTATION_FOR_WALL = {"north": 0, "east": 90, "south": 180, "west": 270}


def _recipe(room: Room) -> list[tuple[str, str]]:
    """(symbol, strategy) list per room type, most important first."""
    t, area, short = room.type, room.area_m2, min(room.w, room.h)
    if t in ("master_bedroom", "bedroom"):
        return [
            ("bed_double" if short >= 300 else "bed_single", "wall_quiet"),
            ("wardrobe", "wall"),
            ("side_table", "beside_bed"),
            ("side_table", "beside_bed"),
        ]
    if t == "maid_room":
        return [("bed_single", "wall_quiet")]
    if t in ("living", "family_hall"):
        items = [("sofa_3", "wall_quiet"), ("coffee_table", "front_of_sofa")]
        if area >= 16:
            items.append(("armchair", "wall"))
        return items
    if t == "dining":
        return [("dining_6" if area >= 10 and short >= 280 else "dining_4", "center")]
    if t == "kitchen":
        return [("kitchen_counter", "wall_exterior")]
    if t == "bath":
        items = [("toilet", "wall_quiet"), ("basin", "wall")]
        if min(room.w, room.h) >= 160 and max(room.w, room.h) >= 240:
            items.append(("bathtub", "wall"))
        elif area >= 3.2:
            items.append(("shower", "wall"))
        return items
    if t == "toilet":
        return [("toilet", "wall_quiet"), ("basin", "wall")]
    if t == "dress":
        return [("wardrobe", "wall_quiet"), ("wardrobe", "wall")]
    if t == "study":
        return [("desk", "wall")]
    if t == "deck":
        return [("armchair", "wall"), ("armchair", "wall"), ("plant", "wall")]
    if t in ("garden", "courtyard"):
        return [("tree", "center"), ("plant", "wall"), ("plant", "wall")]
    if t == "foyer":
        return [("plant", "wall")]
    return []


def _wall_order(plan: FloorPlan, room: Room, strategy: str) -> list[str]:
    door_walls = {d.wall for d in plan.doors if d.to_room == room.id}
    length = {"north": room.w, "south": room.w, "east": room.h, "west": room.h}

    def has_exterior(w: str) -> bool:
        return bool(exterior_intervals(plan, room, w))

    walls = list(length)
    if strategy == "wall_quiet":
        walls.sort(key=lambda w: (w in door_walls, has_exterior(w), -length[w], w))
    elif strategy == "wall_exterior":
        walls.sort(key=lambda w: (not has_exterior(w), w in door_walls, -length[w], w))
    else:
        walls.sort(key=lambda w: (-length[w], w))
    return walls


def _positions_along(room: Room, wall: str, fw: float, fd: float, step: int = 10):
    """Candidate fixture centres (room-local) against a wall, centre of the wall first."""
    if wall in ("north", "south"):
        y = INSET + fd / 2 if wall == "north" else room.h - INSET - fd / 2
        lo, hi = INSET + fw / 2, room.w - INSET - fw / 2
        mid = room.w / 2
        xs = _spread(lo, hi, mid, step)
        return [(x, y) for x in xs]
    x = INSET + fw / 2 if wall == "west" else room.w - INSET - fw / 2
    lo, hi = INSET + fd / 2, room.h - INSET - fd / 2
    mid = room.h / 2
    return [(x, y) for y in _spread(lo, hi, mid, step)]


def _spread(lo: float, hi: float, mid: float, step: int) -> list[float]:
    if hi < lo:
        return []
    vals = [lo + i * step for i in range(int((hi - lo) / step) + 1)] + [hi]
    return sorted(set(vals), key=lambda v: (abs(v - mid), v))


def _fits(fp: Polygon, room: Room, blocked) -> bool:
    inner = box(INSET - 1, INSET - 1, room.w - INSET + 1, room.h - INSET + 1)
    return inner.contains(fp) and (blocked is None or not fp.intersects(blocked))


def _fp(x: float, y: float, fw: float, fd: float) -> Polygon:
    return box(x - fw / 2, y - fd / 2, x + fw / 2, y + fd / 2)


def place_fixtures(plan: FloorPlan) -> list[Fixture]:
    out: list[Fixture] = []
    for room in plan.rooms:
        zones = [
            _local(z, room)
            for d in plan.doors
            if (z := door_clear_zone(plan, d, room.id)) is not None
        ]
        placed: list[Polygon] = []
        sofa: Fixture | None = None
        bed: Fixture | None = None
        windows = _window_zones(plan, room)
        for symbol, strategy in _recipe(room):
            extra = windows if symbol in TALL else []
            blocked = (
                unary_union([*zones, *extra, *(p.buffer(GAP) for p in placed)])
                if (zones or placed or extra)
                else None
            )
            fx = _place_one(plan, room, symbol, strategy, blocked, sofa, bed)
            if fx is None:
                continue
            fixture = Fixture(
                id=f"f{len(out) + 1}", room=room.id, symbol=symbol, x=fx[0], y=fx[1], rotation=fx[2]
            )
            out.append(fixture)
            fw, fd = footprint(symbol, fixture.rotation)
            placed.append(_fp(fixture.x, fixture.y, fw, fd))
            if symbol == "sofa_3":
                sofa = fixture
            if symbol.startswith("bed_"):
                bed = fixture
    return out


TALL = frozenset({"wardrobe"})  # never in front of a window
WINDOW_CLEAR_CM = 70


def _window_zones(plan: FloorPlan, room: Room) -> list[Polygon]:
    """Room-local bands in front of the room's windows."""
    from app.modules.ai.floorplan.geometry import window_span

    out = []
    for w in plan.windows:
        if w.room != room.id:
            continue
        sp = window_span(plan, w)
        line = LineString([sp.start, sp.end])
        band = line.buffer(WINDOW_CLEAR_CM, cap_style="flat")
        out.append(_local(band, room))
    return out


def _local(poly: Polygon, room: Room) -> Polygon:
    return translate(poly, -room.x, -room.y)


def _place_one(
    plan, room, symbol, strategy, blocked, sofa, bed=None
) -> tuple[int, int, int] | None:
    sym = SYMBOLS[symbol]
    if strategy == "center":
        rot = 90 if (room.h > room.w) == (sym.w >= sym.d) else 0
        fw, fd = footprint(symbol, rot)
        cx, cy = room.w / 2, room.h / 2
        cands = [(cx + dx, cy + dy) for dx in range(-60, 61, 10) for dy in range(-60, 61, 10)]
        cands.sort(key=lambda p: ((p[0] - cx) ** 2 + (p[1] - cy) ** 2, p))
        for x, y in cands:
            if _fits(_fp(x, y, fw, fd), room, blocked):
                return round(x), round(y), rot
        return None
    if strategy == "beside_bed":  # bedside table at the head end, either side of the bed
        if bed is None:
            return None
        bsym = SYMBOLS[bed.symbol]
        # n: from the bed's back wall into the room; a: along that wall
        nx, ny = {0: (0, 1), 90: (-1, 0), 180: (0, -1), 270: (1, 0)}[bed.rotation]
        ax, ay = abs(ny), abs(nx)
        back = bsym.d / 2 - sym.d / 2  # keep the table's back on the bed's back line
        side = bsym.w / 2 + GAP + 2 + sym.w / 2
        fw, fd = footprint(symbol, bed.rotation)
        for sgn in (-1, 1):
            x = bed.x - nx * back + ax * side * sgn
            y = bed.y - ny * back + ay * side * sgn
            if _fits(_fp(x, y, fw, fd), room, blocked):
                return round(x), round(y), bed.rotation
        return None
    if strategy == "front_of_sofa":
        if sofa is None:
            return None
        dist = SYMBOLS["sofa_3"].d / 2 + 35 + sym.d / 2
        nx, ny = {0: (0, 1), 90: (-1, 0), 180: (0, -1), 270: (1, 0)}[sofa.rotation]
        x, y = sofa.x + nx * dist, sofa.y + ny * dist
        fw, fd = footprint(symbol, sofa.rotation)
        if _fits(_fp(x, y, fw, fd), room, blocked):
            return round(x), round(y), sofa.rotation
        return None
    for wall in _wall_order(plan, room, strategy):
        rot = ROTATION_FOR_WALL[wall]
        fw, fd = footprint(symbol, rot)
        for x, y in _positions_along(room, wall, fw, fd):
            if _fits(_fp(x, y, fw, fd), room, blocked):
                return round(x), round(y), rot
    return None
