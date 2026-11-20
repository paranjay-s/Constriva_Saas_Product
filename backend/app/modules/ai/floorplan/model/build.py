"""Solved FloorPlan (cm rectangles) -> Building (mm, 50 mm grid). Deterministic.

    building = build_building(plan, revisions=[...], model="gemini-3.5-flash")

What code adds on the way (the FloorPlan does not carry it):
  - walls: every edge of an enclosed room becomes a wall piece; a piece with enclosed
    rooms on both sides is interior (100 mm inside a suite, 150 mm otherwise), with
    outside on one side it is exterior (200 mm); collinear pieces of the same kind merge
  - doors and windows: hosted on those walls, offset to their centre, with height, sill,
    operation (hinged, double, sliding) and hinge end
  - fixtures: furniture symbols become typed fixtures; a kitchen counter gets its sink,
    hob and fridge
  - stairs: flights sized from the storey height (DBC K.5.5.2 limits, see rules.py)
  - site: open areas become site elements (pool with its water, garden, lawn, parking,
    deck...), leftover plot is paving, plus setbacks, a boundary wall and gates
  - areas: gross built-up to the outer face of external walls, net room areas inside the
    wall faces, room gross areas that add up to the built-up area exactly
"""

import math
from collections import defaultdict
from datetime import UTC, datetime

from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

from app.modules.ai.floorplan.geometry import door_span, pool_water, window_span
from app.modules.ai.floorplan.model.building import (
    GRID_MM,
    Areas,
    Building,
    Fixture,
    Flight,
    Meta,
    Opening,
    Pt,
    Revision,
    Room,
    Setbacks,
    Site,
    SiteElement,
    Stair,
    Storey,
    Wall,
)
from app.modules.ai.floorplan.render.symbols import SYMBOLS
from app.modules.ai.floorplan.rules import (
    DOOR_HEIGHT_MM,
    MAIN_DOOR_HEIGHT_MM,
    STAIR_HEADROOM_MM,
    STAIR_MAX_RISER_MM,
    STAIR_MIN_WIDTH_MM,
    STAIR_TREAD_MM,
    WINDOW_SPEC_MM,
)
from app.modules.ai.floorplan.schemas.common import ZONE_BY_TYPE
from app.modules.ai.floorplan.schemas.plan import FloorPlan
from app.modules.ai.floorplan.schemas.plan import Room as PlanRoom
from app.modules.ai.floorplan.settings import FloorplanSettings, get_settings

SUITE_TYPES = frozenset({"bath", "toilet", "dress", "store", "utility", "shaft"})
FINISH = {
    "bath": "ceramic tiles, wet area",
    "toilet": "ceramic tiles, wet area",
    "kitchen": "porcelain tiles",
    "utility": "porcelain tiles",
    "stair": "marble treads",
    "store": "porcelain tiles",
    "parking": "interlock paving",
    "gym": "rubber flooring",
}
SITE_KIND = {
    "pool": "pool",
    "garden": "garden",
    "lawn": "lawn",
    "courtyard": "courtyard",
    "parking": "parking",
    "driveway": "driveway",
    "dock": "dock",
    "deck": "deck",
    "balcony": "balcony",
}
FIXTURE_KIND = {
    "toilet": "wc",
    "basin": "basin",
    "shower": "shower",
    "bathtub": "bath",
    "kitchen_counter": "counter",
    "wardrobe": "wardrobe",
    "bed_double": "bed_double",
    "bed_single": "bed_single",
    "side_table": "side_table",
    "sofa_3": "sofa",
    "armchair": "armchair",
    "coffee_table": "coffee_table",
    "dining_4": "dining_table",
    "dining_6": "dining_table",
    "desk": "desk",
    "tree": "tree",
    "plant": "plant",
}
OUTDOOR_DOOR_TYPES = frozenset({"pool", "deck", "garden", "lawn", "courtyard", "balcony"})


def mm(cm: float) -> int:
    """cm -> mm on the 50 mm grid."""
    return int(round(cm * 10 / GRID_MM)) * GRID_MM


def _rect(r: PlanRoom) -> tuple[int, int, int, int]:
    return mm(r.x), mm(r.y), mm(r.x2), mm(r.y2)


def _poly(x0: int, y0: int, x1: int, y1: int) -> list[Pt]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _coords(geom) -> list[Pt]:
    """Exterior ring of a polygon as grid points (closing point dropped)."""
    pts = list(geom.exterior.coords)[:-1]
    return [(int(round(x)), int(round(y))) for x, y in pts]


def _pieces(geom) -> list[Polygon]:
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]


# ------------------------------------------------------------------------- walls


def _walls(
    rects: dict[str, tuple[int, int, int, int]],
    types: dict[str, str],
    s: FloorplanSettings,
    height: int,
) -> list[Wall]:
    """Wall pieces on every room edge, classified by what lies on either side."""

    def room_at(x: float, y: float) -> str | None:
        for rid, (x0, y0, x1, y1) in rects.items():
            if x0 < x < x1 and y0 < y < y1:
                return rid
        return None

    def thickness(a: str | None, b: str | None) -> tuple[str, int]:
        if a is None or b is None:
            return "exterior", s.wall_exterior_mm
        if types[a] in SUITE_TYPES or types[b] in SUITE_TYPES:
            return "partition", s.wall_partition_mm
        return "interior", s.wall_interior_mm

    lines: dict[tuple[bool, int], list[tuple[int, int]]] = defaultdict(list)
    for x0, y0, x1, y1 in rects.values():
        lines[(True, y0)].append((x0, x1))
        lines[(True, y1)].append((x0, x1))
        lines[(False, x0)].append((y0, y1))
        lines[(False, x1)].append((y0, y1))

    walls: list[Wall] = []
    for (horizontal, c), spans in sorted(lines.items()):
        cuts = sorted({v for span in spans for v in span})
        run: list | None = None  # [start, end, kind, thickness, rooms]
        for p, q in zip(cuts, cuts[1:], strict=False):
            if not any(lo <= p and q <= hi for lo, hi in spans):
                run = _flush(run, walls, horizontal, c, height)
                continue
            m = (p + q) / 2
            a, b = (
                (room_at(m, c - 1), room_at(m, c + 1))
                if horizontal
                else (
                    room_at(c - 1, m),
                    room_at(c + 1, m),
                )
            )
            if a is None and b is None:
                run = _flush(run, walls, horizontal, c, height)
                continue
            kind, t = thickness(a, b)
            rooms = [r for r in (a, b) if r]
            if run and run[1] == p and run[2] == kind and run[3] == t:
                run[1] = q
                run[4] = list(dict.fromkeys(run[4] + rooms))
            else:
                run = _flush(run, walls, horizontal, c, height)
                run = [p, q, kind, t, rooms]
        _flush(run, walls, horizontal, c, height)
    return walls


def _flush(run, walls: list[Wall], horizontal: bool, c: int, height: int) -> None:
    if run is not None:
        p, q, kind, t, rooms = run
        a, b = ((p, c), (q, c)) if horizontal else ((c, p), (c, q))
        walls.append(
            Wall(
                id=f"W{len(walls) + 1:03d}",
                a=a,
                b=b,
                thickness=t,
                kind=kind,
                height=height,
                rooms=rooms,
            )
        )
    return None


def _host(walls: list[Wall], start: tuple[float, float], end: tuple[float, float]) -> Wall | None:
    (sx, sy), (ex, ey) = start, end
    horizontal = abs(sy - ey) < 1
    for w in walls:
        if horizontal and w.horizontal and abs(w.a[1] - sy) <= GRID_MM / 2:
            if w.a[0] - 1 <= min(sx, ex) and max(sx, ex) <= w.b[0] + 1:
                return w
        if not horizontal and not w.horizontal and abs(w.a[0] - sx) <= GRID_MM / 2:
            if w.a[1] - 1 <= min(sy, ey) and max(sy, ey) <= w.b[1] + 1:
                return w
    return None


# ---------------------------------------------------------------------- openings


def _openings(plan: FloorPlan, walls: list[Wall]) -> tuple[list[Opening], list[str]]:
    rooms = {r.id: r for r in plan.rooms}
    road = plan.plot.road_side or "south"
    out: list[Opening] = []
    notes: list[str] = []
    entrance_done = False
    for d in plan.doors:
        sp = door_span(plan, d)
        start = (sp.start[0] * 10, sp.start[1] * 10)
        end = (sp.end[0] * 10, sp.end[1] * 10)
        host = _host(walls, start, end)
        if host is None:
            notes.append(f"door {d.id} has no wall to sit in and was left out")
            continue
        centre = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        along = centre[0] - host.a[0] if host.horizontal else centre[1] - host.a[1]
        into_side, hand = d.swing.split("-") if d.swing != "none" else ("in", "left")
        into = d.to_room if into_side == "in" else d.from_room
        other = d.from_room if into_side == "in" else d.to_room
        outside_types = {rooms[r].type for r in (d.to_room, d.from_room) if r}
        width = mm(d.width)
        is_main = (
            not entrance_done
            and d.from_room is None
            and d.wall == road
            and not (outside_types & OUTDOOR_DOOR_TYPES)
        )
        entrance_done = entrance_done or is_main
        if outside_types & OUTDOOR_DOOR_TYPES and width >= 1500:
            operation = "sliding"
        elif width >= 1500:
            operation = "double"
        else:
            operation = "hinged"
        out.append(
            Opening(
                id=d.id,
                wall=host.id,
                kind="door",
                operation=operation,
                offset=int(round(along / 10)) * 10,
                width=width,
                height=MAIN_DOOR_HEIGHT_MM if is_main else DOOR_HEIGHT_MM,
                sill=0,
                rooms=(into, other),
                hinge=None if operation == "sliding" else ("start" if hand == "left" else "end"),
                main_entrance=is_main,
            )
        )
    for w in plan.windows:
        sp = window_span(plan, w)
        start = (sp.start[0] * 10, sp.start[1] * 10)
        end = (sp.end[0] * 10, sp.end[1] * 10)
        host = _host(walls, start, end)
        if host is None:
            notes.append(f"window {w.id} has no wall to sit in and was left out")
            continue
        centre = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        along = centre[0] - host.a[0] if host.horizontal else centre[1] - host.a[1]
        height, sill = WINDOW_SPEC_MM.get(rooms[w.room].type, WINDOW_SPEC_MM["default"])
        out.append(
            Opening(
                id=w.id,
                wall=host.id,
                kind="window",
                operation="sliding",
                offset=int(round(along / 10)) * 10,
                width=mm(w.width),
                height=height,
                sill=sill,
                rooms=(w.room, None),
            )
        )
    return out, notes


# ---------------------------------------------------------------------- fixtures


def _fixtures(plan: FloorPlan) -> list[Fixture]:
    rooms = {r.id: r for r in plan.rooms}
    out: list[Fixture] = []

    def add(room: str, kind: str, x: float, y: float, w: float, d: float, rot: int) -> None:
        out.append(
            Fixture(
                id=f"F{len(out) + 1:03d}",
                room=room,
                kind=kind,
                x=int(round(x / 10)) * 10,
                y=int(round(y / 10)) * 10,
                w=int(round(w)),
                d=int(round(d)),
                rotation=rot,
            )
        )

    for f in plan.fixtures:
        if rooms[f.room].is_open:
            continue  # planting in gardens and courts is drawn with the site, not as fixtures
        kind = FIXTURE_KIND.get(f.symbol)
        sym = SYMBOLS.get(f.symbol)
        if kind is None or sym is None:
            continue
        room = rooms[f.room]
        cx, cy = (room.x + f.x) * 10, (room.y + f.y) * 10
        w, d = sym.w * 10, sym.d * 10
        if kind != "counter":
            add(f.room, kind, cx, cy, w, d, f.rotation)
            continue
        # a counter run: sink, hob and fridge on it (the work triangle reads these)
        add(f.room, "counter", cx, cy, w, d, f.rotation)
        ux, uy = (1, 0) if f.rotation in (0, 180) else (0, 1)
        if f.rotation in (180, 270):
            ux, uy = -ux, -uy
        for kind2, t, size in (("sink", -0.25, (800, 500)), ("hob", 0.2, (600, 520))):
            add(f.room, kind2, cx + ux * t * w, cy + uy * t * w, size[0], size[1], f.rotation)
        if w >= 2400:  # room for a fridge at the end of the run
            fx = cx + ux * (w / 2 - 350)
            fy = cy + uy * (w / 2 - 350)
            add(f.room, "fridge", fx, fy, 700, 650, f.rotation)
    return out


# ------------------------------------------------------------------------ stairs


def stair_for(room_id: str, rect: tuple[int, int, int, int], storey_height: int) -> Stair:
    """Flights for a stair room: a U stair (two flights and a landing) when the room is
    wide enough for two flights, else one straight flight. Values from rules.py."""
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    risers = max(2, math.ceil(storey_height / STAIR_MAX_RISER_MM))
    riser = int(round(storey_height / risers))
    along_x = w >= h  # flights run along the room's long side
    long_, short = (w, h) if along_x else (h, w)
    tread = STAIR_TREAD_MM
    flights: list[Flight] = []
    landing = None
    if short >= 2 * STAIR_MIN_WIDTH_MM + 100:
        first = math.ceil(risers / 2)
        second = risers - first
        flight_w = (short - 100) // 2
        run = max(first - 1, second - 1) * tread
        land = max(STAIR_MIN_WIDTH_MM, long_ - run)
        tread = min(tread + 40, max(tread, (long_ - land) // max(1, first - 1)))
        run = (first - 1) * tread
        if along_x:
            flights.append(Flight(x=x0, y=y0, w=run, h=flight_w, axis="x", up=1, risers=first))
            flights.append(
                Flight(x=x0, y=y1 - flight_w, w=run, h=flight_w, axis="x", up=-1, risers=second)
            )
            landing = (x0 + run, y0, long_ - run, short)
        else:
            flights.append(Flight(x=x0, y=y0, w=flight_w, h=run, axis="y", up=1, risers=first))
            flights.append(
                Flight(x=x1 - flight_w, y=y0, w=flight_w, h=run, axis="y", up=-1, risers=second)
            )
            landing = (x0, y0 + run, short, long_ - run)
        width = flight_w
    else:
        run = (risers - 1) * tread
        if along_x:
            flights.append(Flight(x=x0, y=y0, w=min(run, w), h=h, axis="x", up=1, risers=risers))
        else:
            flights.append(Flight(x=x0, y=y0, w=w, h=min(run, h), axis="y", up=1, risers=risers))
        width = short
    return Stair(
        id=f"S-{room_id}",
        room=room_id,
        width=width,
        riser=riser,
        tread=tread,
        risers=risers,
        headroom=STAIR_HEADROOM_MM,
        landing=landing,
        flights=flights,
    )


# -------------------------------------------------------------------------- site


def setbacks_for(plot) -> Setbacks:
    """The plot's setbacks in mm (zero on a plot laid out without setbacks)."""
    sb = plot.setbacks
    return Setbacks(front=mm(sb.front), rear=mm(sb.rear), left=mm(sb.left), right=mm(sb.right))


def setback_box(site: Site) -> tuple[int, int, int, int]:
    """The buildable rectangle (x0, y0, x1, y1) inside the setbacks.

    Standing on the road and facing the house: front is the road side, left and right
    are as the person sees them."""
    sb = site.setbacks
    n, s_, w, e = {
        "south": (sb.rear, sb.front, sb.left, sb.right),
        "north": (sb.front, sb.rear, sb.right, sb.left),
        "east": (sb.left, sb.right, sb.rear, sb.front),
        "west": (sb.right, sb.left, sb.front, sb.rear),
    }[site.road_side]
    return w, n, site.width - e, site.depth - s_


def _site(
    plan: FloorPlan,
    width: int,
    depth: int,
    built_outer,
    s: FloorplanSettings,
) -> Site:
    road = plan.plot.road_side or "south"
    elements: list[SiteElement] = []
    joined: dict[str, list] = defaultdict(list)
    for r in plan.rooms:
        if r.type == "shaft" and r.part_of:
            joined[r.part_of].append(box(*_rect(r)))
    for r in plan.rooms:
        kind = SITE_KIND.get(r.type)
        if kind is None:
            continue
        if kind == "garden" and "LAWN" in r.label.upper():
            kind = "lawn"
        shape = unary_union([box(*_rect(r)), *joined.get(r.id, [])]).difference(built_outer)
        for i, piece in enumerate(_pieces(shape)):
            if piece.area < 0.25e6:
                continue
            water = None
            if kind == "pool" and i == 0:
                wx, wy, ww, wh = pool_water(r)
                water = _poly(mm(wx), mm(wy), mm(wx + ww), mm(wy + wh))
            elements.append(
                SiteElement(
                    id=f"E-{r.id}" + (f"-{i}" if i else ""),
                    kind=kind,
                    name=r.label,
                    polygon=_coords(piece.simplify(1)),
                    water=water,
                    room=r.id,
                )
            )
    plot = box(0, 0, width, depth)
    taken = unary_union([built_outer, *[Polygon(e.polygon) for e in elements]])
    for i, piece in enumerate(_pieces(plot.difference(taken))):
        if piece.area >= 0.25e6:
            elements.append(
                SiteElement(
                    id=f"E-paving-{i + 1}",
                    kind="paving",
                    name="PAVING",
                    polygon=_coords(piece.simplify(1)),
                )
            )
    elements += _boundary(plan, width, depth, road)
    return Site(
        width=width,
        depth=depth,
        road_side=road,
        north_deg=0.0,
        setbacks=setbacks_for(plan.plot),
        elements=elements,
    )


def _boundary(plan: FloorPlan, width: int, depth: int, road: str) -> list[SiteElement]:
    """A 200 mm boundary wall inside the plot edge, with a vehicle gate in front of the
    parking (when there is one) and a pedestrian gate in line with the main door."""
    t = 200
    gates: list[tuple[int, int]] = []  # intervals along the road edge
    along = lambda x, y: x if road in ("north", "south") else y  # noqa: E731
    for r in plan.rooms:
        if r.type == "parking":
            x0, y0, x1, y1 = _rect(r)
            lo, hi = (x0, x1) if road in ("north", "south") else (y0, y1)
            mid = (lo + hi) // 2
            gates.append((max(lo, mid - 2000), min(hi, mid + 2000)))
    entrance = next((d for d in plan.doors if d.from_room is None and d.wall == road), None)
    if entrance is not None:
        sp = door_span(plan, entrance)
        mid = mm((along(*sp.start) + along(*sp.end)) / 2)
        gates.append((mid - 750, mid + 750))
    edge_len = width if road in ("north", "south") else depth
    gates = sorted((max(0, a), min(edge_len, b)) for a, b in gates)
    pieces: list[tuple[int, int]] = []
    pos = 0
    for a, b in gates:
        if a > pos:
            pieces.append((pos, a))
        pos = max(pos, b)
    if pos < edge_len:
        pieces.append((pos, edge_len))

    def band(lo: int, hi: int) -> list[Pt]:
        if road == "south":
            return _poly(lo, depth - t, hi, depth)
        if road == "north":
            return _poly(lo, 0, hi, t)
        if road == "east":
            return _poly(width - t, lo, width, hi)
        return _poly(0, lo, t, hi)

    out = [
        SiteElement(id=f"E-bw-road-{i + 1}", kind="boundary_wall", polygon=band(a, b))
        for i, (a, b) in enumerate(pieces)
        if b - a > 0
    ]
    others = {
        "north": _poly(0, 0, width, t),
        "south": _poly(0, depth - t, width, depth),
        "west": _poly(0, 0, t, depth),
        "east": _poly(width - t, 0, width, depth),
    }
    out += [
        SiteElement(id=f"E-bw-{side}", kind="boundary_wall", polygon=poly)
        for side, poly in others.items()
        if side != road
    ]
    out += [
        SiteElement(id=f"E-gate-{i + 1}", kind="gate", name="GATE", polygon=band(a, b))
        for i, (a, b) in enumerate(gates)
    ]
    return out


# ------------------------------------------------------------------------- areas


def _areas(rooms: list[Room], walls: list[Wall], t_ext: int, site_area_m2: float):
    """Fill each room's gross and net area; return (outer footprint, Areas).

    Gross: the room on wall centre lines, extended to the outer face where its wall is
    external, so the rooms' gross areas add up to the footprint (DBC K.5.2.7 coverage).
    Net: inside the wall faces."""
    polys = {r.id: Polygon(r.polygon) for r in rooms}
    footprint = unary_union(list(polys.values()))
    outer = footprint.buffer(t_ext / 2, join_style="mitre", cap_style="flat")
    wall_bands = unary_union(
        [
            box(
                min(w.a[0], w.b[0]) - (w.thickness / 2 if not w.horizontal else 0),
                min(w.a[1], w.b[1]) - (w.thickness / 2 if w.horizontal else 0),
                max(w.a[0], w.b[0]) + (w.thickness / 2 if not w.horizontal else 0),
                max(w.a[1], w.b[1]) + (w.thickness / 2 if w.horizontal else 0),
            )
            for w in walls
        ]
    )
    assigned = None
    for r in sorted(rooms, key=lambda r: r.id):
        p = polys[r.id]
        others = unary_union([q for k, q in polys.items() if k != r.id])
        g = p.buffer(t_ext / 2, join_style="mitre", cap_style="flat").intersection(outer)
        g = g.difference(others)
        if assigned is not None:
            g = g.difference(assigned)
        g = g.union(p)
        assigned = g if assigned is None else assigned.union(g)
        r.gross_area_m2 = round(g.area / 1e6, 2)
        r.net_area_m2 = round(p.difference(wall_bands).area / 1e6, 2)
    built = round(outer.area / 1e6, 2)
    areas = Areas(
        plot_m2=round(site_area_m2, 2),
        built_up_m2=built,
        built_up_net_m2=round(sum(r.net_area_m2 for r in rooms if r.type != "shaft"), 2),
        exterior_m2=round(site_area_m2 - built, 2),
        coverage=round(built / site_area_m2, 4) if site_area_m2 else 0.0,
        rooms_gross_m2=round(sum(r.gross_area_m2 for r in rooms), 2),
    )
    return outer, areas


# -------------------------------------------------------------------------- main


def build_building(
    plan: FloorPlan,
    *,
    version: int = 1,
    revisions: list[Revision] | None = None,
    model: str = "",
    settings: FloorplanSettings | None = None,
    date: str | None = None,
) -> Building:
    s = settings or get_settings()
    width, depth = mm(plan.plot.width), mm(plan.plot.depth)

    def duct(r: PlanRoom) -> bool:  # a shaft inside the house, not touching the plot edge
        return (
            r.type == "shaft"
            and not r.part_of
            and r.x > 0
            and r.y > 0
            and r.x2 < plan.plot.width
            and r.y2 < plan.plot.depth
        )

    enclosed = [r for r in plan.rooms if not r.is_open or duct(r)]
    rects = {r.id: _rect(r) for r in enclosed}
    types = {r.id: r.type for r in enclosed}
    walls = _walls(rects, types, s, s.storey_height_mm - 300)
    openings, _notes = _openings(plan, walls)
    rooms = [
        Room(
            id=r.id,
            name=r.label,
            type=r.type,
            zone=ZONE_BY_TYPE.get(r.type, "public"),
            polygon=_poly(*rects[r.id]),
            enclosed=r.type != "shaft",
            finish=FINISH.get(r.type, "porcelain tiles"),
        )
        for r in enclosed
    ]
    outer, areas = _areas(rooms, walls, s.wall_exterior_mm, width * depth / 1e6)
    stairs = [
        stair_for(r.id, rects[r.id], s.storey_height_mm) for r in enclosed if r.type == "stair"
    ]
    storey = Storey(
        id="L0",
        name=plan.meta.floor_name or "GROUND FLOOR",
        index=0,
        elevation=0,
        height=s.storey_height_mm,
        walls=walls,
        openings=openings,
        rooms=rooms,
        fixtures=_fixtures(plan),
        stairs=stairs,
    )
    today = date or datetime.now(UTC).strftime("%Y-%m-%d")
    meta = Meta(
        plan_id=plan.id,
        version=version,
        project=plan.meta.project,
        client=plan.meta.owner,
        title=f"{(plan.meta.floor_name or 'GROUND FLOOR').upper()} PLAN",
        sheet="A1" if s.sheet.upper() == "A1" else "A3",
        date=today,
        unit_display=plan.meta.unit_display,
        revisions=revisions or [Revision(rev="A", date=today, description="First issue")],
        model=model,
    )
    site = _site(plan, width, depth, outer, s)
    return Building(meta=meta, site=site, storeys=[storey], areas=areas)
