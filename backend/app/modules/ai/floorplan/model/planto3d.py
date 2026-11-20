"""Building -> PlanTo3D plan (feet, y up), directly, without reading a drawing.

Origin: the plot's south-west corner, so the pool, garden and every site element lie
inside the floor's `size` (the whole plot). Walls are the centre line +- half the
thickness, run on to the far face of a wall they meet (as PlanTo3D's detector draws
them); boundary walls are low walls. Doors and windows are rectangles across their wall
with hinge point and swing side; rooms are rectangles (enclosed rooms between the wall
faces, site elements as drawn) with PlanTo3D's room types from its vocabulary
(services/planto3d/web/rooms.json); stairs are the model's flights with steps = risers
and an UP word at the start of the first flight.

Every wall, opening, room and flight of the model is in the result with its position and
size to within 0.001 ft; tests/floorplan/test_fp_building.py checks that.
"""

from typing import Any

from shapely.geometry import LineString, Polygon

from app.modules.ai.floorplan.model.building import Building, Storey, Wall

MM_PER_FT = 304.8
TYPE_3D = {
    "bedroom": "bedroom",
    "master_bedroom": "bedroom",
    "maid_room": "bedroom",
    "driver_room": "bedroom",
    "bath": "toilet",
    "toilet": "toilet",
    "kitchen": "kitchen",
    "living": "living",
    "family_hall": "living",
    "majlis": "majlis",
    "dining": "dining",
    "foyer": "foyer",
    "lobby": "passage",
    "passage": "passage",
    "utility": "wash",
    "store": "store",
    "dress": "dress",
    "study": "study",
    "stair": "stair",
    "lift": "lift",
    "shaft": "duct",
    "prayer": "prayer",
    "puja": "puja",
    "bar": "bar",
    "gym": "gym",
    # site elements
    "pool": "pool",
    "garden": "garden",
    "lawn": "garden",
    "courtyard": "yard",
    "parking": "parking",
    "driveway": "yard",
    "paving": "yard",
    "deck": "yard",
    "balcony": "balcony",
    "dock": "dock",
}


def _ft(v: float) -> float:
    return round(v / MM_PER_FT, 3)


def _type_3d(model_type: str, name: str) -> str:
    if model_type in TYPE_3D:
        return TYPE_3D[model_type]
    from app.modules.plan3d.convert import room_type_from_name

    return room_type_from_name(name) or "room"


def _rects(poly: list[tuple[int, int]]) -> list[tuple[int, int, int, int]]:
    """An axis-aligned polygon as rectangles (x0, y0, x1, y1): vertical slabs between the
    distinct x coordinates, neighbouring slabs with the same y span merged."""
    shape = Polygon(poly)
    xs = sorted({p[0] for p in poly})
    slabs: list[list[int]] = []
    for x0, x1 in zip(xs, xs[1:], strict=False):
        cut = shape.intersection(LineString([((x0 + x1) / 2, -1e9), ((x0 + x1) / 2, 1e9)]))
        parts = [cut] if cut.geom_type == "LineString" else list(getattr(cut, "geoms", []))
        for part in parts:
            ys = [c[1] for c in part.coords]
            y0, y1 = int(round(min(ys))), int(round(max(ys)))
            if y1 > y0:
                last = next((s for s in slabs if s[2] == x0 and s[1] == y0 and s[3] == y1), None)
                if last:
                    last[2] = x1
                else:
                    slabs.append([x0, y0, x1, y1])
    return [tuple(s) for s in slabs]


def _wall_rect(w: Wall, walls: list[Wall]) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) in mm: centre line +- t/2, each end run on to the far face of a
    perpendicular wall it ends on."""
    h = w.thickness / 2
    lo, hi = (min(w.a[0], w.b[0]), max(w.a[0], w.b[0])) if w.horizontal else (
        min(w.a[1], w.b[1]),
        max(w.a[1], w.b[1]),
    )
    c = w.a[1] if w.horizontal else w.a[0]
    ext_lo = ext_hi = 0.0
    for q in walls:
        if q.horizontal == w.horizontal or q.kind == "boundary":
            continue
        qc = q.a[0] if w.horizontal else q.a[1]  # q's line, across w's direction
        qlo, qhi = (min(q.a[1], q.b[1]), max(q.a[1], q.b[1])) if w.horizontal else (
            min(q.a[0], q.b[0]),
            max(q.a[0], q.b[0]),
        )
        if not qlo <= c <= qhi:
            continue
        if qc == lo:
            ext_lo = max(ext_lo, q.thickness / 2)
        if qc == hi:
            ext_hi = max(ext_hi, q.thickness / 2)
    lo, hi = lo - ext_lo, hi + ext_hi
    if w.horizontal:
        return lo, c - h, hi, c + h
    return c - h, lo, c + h, hi


def _floor(b: Building, st: Storey) -> dict[str, Any]:
    depth = b.site.depth

    def R(x0: float, y0: float, x1: float, y1: float) -> list[float]:
        """mm rectangle (y down) -> PlanTo3D [x0, x1, y0, y1] in ft (y up)."""
        return [_ft(x0), _ft(x1), _ft(depth - y1), _ft(depth - y0)]

    def P(x: float, y: float) -> list[float]:
        return [_ft(x), _ft(depth - y)]

    walls = {w.id: w for w in st.walls}
    out_walls = [[*R(*_wall_rect(w, st.walls)), 0] for w in st.walls]
    if st.index == 0:
        for e in b.site.elements:
            if e.kind == "boundary_wall":
                xs, ys = [p[0] for p in e.polygon], [p[1] for p in e.polygon]
                out_walls.append([*R(min(xs), min(ys), max(xs), max(ys)), 1])

    room_poly = {r.id: Polygon(r.polygon) for r in st.rooms}
    openings = []
    for o in st.openings:
        w = walls[o.wall]
        h = w.thickness / 2
        if w.horizontal:
            cx, cy = w.a[0] + o.offset, w.a[1]
            rect = R(cx - o.width / 2, cy - h, cx + o.width / 2, cy + h)
        else:
            cx, cy = w.a[0], w.a[1] + o.offset
            rect = R(cx - h, cy - o.width / 2, cx + h, cy + o.width / 2)
        d: dict[str, Any] = {
            "type": o.kind,
            "rect": rect,
            "axis": "x" if w.horizontal else "y",
            "id": o.id,
            "width_mm": o.width,
            "height_mm": o.height,
            "sill_mm": o.sill,
            "operation": o.operation,
        }
        if o.kind == "door" and o.hinge:
            into = o.rooms[0]
            # side of the wall the leaf opens to, in model coordinates (y down)
            side = 1
            if into is not None and into in room_poly:
                rc = room_poly[into].representative_point()
                side = 1 if (rc.y > cy if w.horizontal else rc.x > cx) else -1
            sign = -1 if o.hinge == "start" else 1
            if w.horizontal:
                hx, hy = cx + sign * o.width / 2, cy + side * h
                d["swing"] = -side  # y flips: +1 is towards +y in PlanTo3D
            else:
                hx, hy = cx + side * h, cy + sign * o.width / 2
                d["swing"] = side
            d["hinge"] = P(hx, hy)
            d["double"] = o.operation == "double"
        openings.append(d)

    walls_by_room: dict[str, list[Wall]] = {}
    for w in st.walls:
        for rid in w.rooms:
            walls_by_room.setdefault(rid, []).append(w)
    rooms = []
    labels = []
    for r in st.rooms:
        xs, ys = [p[0] for p in r.polygon], [p[1] for p in r.polygon]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)

        edges = {"n": (True, y0), "s": (True, y1), "w": (False, x0), "e": (False, x1)}
        half = {
            k: max(
                [
                    w.thickness / 2
                    for w in walls_by_room.get(r.id, [])
                    if w.horizontal == hz and (w.a[1] if hz else w.a[0]) == c
                ],
                default=0.0,
            )
            for k, (hz, c) in edges.items()
        }
        nx0, ny0, nx1, ny1 = x0 + half["w"], y0 + half["n"], x1 - half["e"], y1 - half["s"]
        rect = R(nx0, ny0, nx1, ny1)
        rooms.append(
            {
                "type": _type_3d(r.type, r.name),
                "label": r.name,
                "rects": [rect],
                "area": round((nx1 - nx0) * (ny1 - ny0) / MM_PER_FT**2, 1),
                "dims": [_ft(nx1 - nx0), _ft(ny1 - ny0)],
                "id": r.id,
                "model_type": r.type,
                "centre_line_mm": [x0, y0, x1, y1],
            }
        )
        labels.append({"text": r.name, "at": P((x0 + x1) / 2, (y0 + y1) / 2)})
    if st.index == 0:
        for e in b.site.elements:
            if e.kind in ("boundary_wall", "gate", "plot"):
                continue
            rects = [R(*q) for q in _rects(e.polygon)]
            area = Polygon(e.polygon).area / MM_PER_FT**2
            room = {
                "type": _type_3d(e.kind, e.name),
                "label": e.name or e.kind.upper(),
                "rects": rects,
                "area": round(area, 1),
                "dims": None,
                "id": e.id,
                "model_type": e.kind,
            }
            if e.water:
                xs, ys = [p[0] for p in e.water], [p[1] for p in e.water]
                room["water"] = R(min(xs), min(ys), max(xs), max(ys))
            rooms.append(room)
    stairs = []
    for s in st.stairs:
        for i, f in enumerate(s.flights):
            rect = R(f.x, f.y, f.x + f.w, f.y + f.h)
            entry: dict[str, Any] = {
                "rect": rect,
                "axis": f.axis,
                "steps": f.risers,
                "up": i == 0,
                "words": [],
            }
            if i == 0:  # gen.py starts the climb at the end nearest the UP word
                if f.axis == "x":
                    sx = f.x if f.up == 1 else f.x + f.w
                    entry["words"] = [["UP", *P(sx, f.y + f.h / 2)]]
                else:
                    sy = f.y if f.up == 1 else f.y + f.h
                    entry["words"] = [["UP", *P(f.x + f.w / 2, sy)]]
            stairs.append(entry)
    return {
        "title": st.name.upper(),
        "name": st.name.title(),
        "level": st.index,
        "page": 1,
        "size": [_ft(b.site.width), _ft(b.site.depth)],
        "north_deg": b.site.north_deg,
        "walls": out_walls,
        "openings": openings,
        "rooms": rooms,
        "stairs": stairs,
        "labels": labels,
    }


def to_planto3d(b: Building, *, source_name: str = "") -> dict[str, Any]:
    floors = [_floor(b, st) for st in b.storeys]
    thick = sorted(w.thickness for st in b.storeys for w in st.walls)
    return {
        "version": 1,
        "source": source_name or f"{b.meta.project or 'plan'}.pdf",
        "reader": "model",
        "units": "ft",
        "scale_pt_per_ft": round(MM_PER_FT / b.meta.scale / 25.4 * 72, 4),
        "scale_source": "labels",
        "wall_pt": round(thick[len(thick) // 2] / b.meta.scale / 25.4 * 72, 2) if thick else 1.0,
        "floor_height": round(b.storeys[0].height / MM_PER_FT, 3),
        "slab": round(300 / MM_PER_FT, 3),
        "floors": floors,
        "plan_id": b.meta.plan_id,
        "plan_version": b.meta.version,
    }
