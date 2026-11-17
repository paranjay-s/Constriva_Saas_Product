"""DXF (CAD) export of a FloorPlan: real vectors, real units, standard layers.

Everything is drawn from the same plan JSON as the SVG, in centimetres ($INSUNITS = cm),
so a CAD user can measure, edit and re-layer it:

    WALLS       solid-hatched wall outline with door/window openings cut out
    DOORS       door leaf lines and swing arcs (true ARC entities)
    WINDOWS     window frames in the wall openings
    FURNITURE   fixtures as named blocks (BED_DOUBLE, TOILET, ...) inserted with rotation
    HATCH       diagonal hatch of open areas (courtyard, garden, parking, open shafts)
    TEXT        room names and sizes, road label, north arrow, title block
    DIMENSIONS  linear DIMENSION entities (chain and overall) with the plan's unit text
    PLOT        plot boundary

The plan's y axis grows south; DXF's grows north, so y is flipped: Y = plot depth - y.
"""

import io
import math

import ezdxf
from ezdxf import units
from ezdxf.enums import TextEntityAlignment
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

from app.modules.ai.floorplan.geometry import (
    door_span,
    opening_cut,
    pool_water,
    wall_polygon,
    window_span,
)
from app.modules.ai.floorplan.render.svg_renderer import (
    _label_fit,
    _label_obstacles,
    _label_position,
    joined_area,
)
from app.modules.ai.floorplan.render.symbols import (
    SYMBOLS,
    Arc,
    Circle,
    Line,
    Poly,
    Rect,
)
from app.modules.ai.floorplan.rules import WALL_EXTERIOR_CM
from app.modules.ai.floorplan.schemas.plan import FloorPlan, Room
from app.modules.ai.floorplan.units import fmt_area, fmt_length, fmt_size

# name: (ACI colour, lineweight in 1/100 mm)
LAYERS: dict[str, tuple[int, int]] = {
    "WALLS": (7, 50),
    "DOORS": (1, 25),
    "WINDOWS": (5, 25),
    "FURNITURE": (8, 18),
    "HATCH": (3, 13),
    "TEXT": (7, 25),
    "DIMENSIONS": (2, 18),
    "PLOT": (8, 25),
    "POOL": (4, 35),
}
DIMSTYLE = "PLAN_CM"


def render_dxf(plan: FloorPlan) -> bytes:
    """The plan as a DXF (R2010) document, returned as bytes."""
    doc = ezdxf.new("R2010", setup=True)
    doc.units = units.CM
    doc.header["$INSUNITS"] = units.CM
    doc.header["$MEASUREMENT"] = 1  # metric
    doc.header["$LUNITS"] = 2
    for name, (color, lw) in LAYERS.items():
        doc.layers.add(name, color=color, lineweight=lw)
    _dimstyle(doc, plan)
    msp = doc.modelspace()
    flip = _Flip(plan.plot.depth)

    _plot_boundary(msp, plan, flip)
    _hatches(msp, plan, flip)
    _pool_and_deck(msp, plan, flip)
    _walls(msp, plan, flip)
    _windows(msp, plan, flip)
    _doors(msp, plan, flip)
    _fixtures(doc, msp, plan, flip)
    _labels(msp, plan, flip)
    _dimensions(msp, plan, flip)
    _sheet_text(msp, plan, flip)

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


class _Flip:
    def __init__(self, depth: float) -> None:
        self.depth = depth

    def __call__(self, x: float, y: float) -> tuple[float, float]:
        return (round(x, 2), round(self.depth - y, 2))


def _text_unit(plan: FloorPlan) -> float:
    return max(14.0, min(40.0, max(plan.plot.width, plan.plot.depth) / 60))


# ---------------------------------------------------------------- geometry layers


def _plot_boundary(msp, plan: FloorPlan, f: _Flip) -> None:
    pw, pd = plan.plot.width, plan.plot.depth
    pts = [f(0, 0), f(pw, 0), f(pw, pd), f(0, pd)]
    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "PLOT"})


def _polygons(geom) -> list[Polygon]:
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]


def _walls(msp, plan: FloorPlan, f: _Flip) -> None:
    walls = wall_polygon(plan)
    cuts = [opening_cut(door_span(plan, d), WALL_EXTERIOR_CM + 2) for d in plan.doors]
    cuts += [opening_cut(window_span(plan, w), WALL_EXTERIOR_CM + 2) for w in plan.windows]
    if cuts:
        walls = walls.difference(unary_union(cuts))
    for poly in _polygons(walls):
        rings = [list(poly.exterior.coords)[:-1]] + [list(r.coords)[:-1] for r in poly.interiors]
        hatch = msp.add_hatch(color=256, dxfattribs={"layer": "WALLS"})
        hatch.set_solid_fill(color=256)
        for i, ring in enumerate(rings):
            if len(ring) < 3:
                continue
            pts = [f(x, y) for x, y in ring]
            msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "WALLS"})
            flags = (
                ezdxf.const.BOUNDARY_PATH_EXTERNAL if i == 0 else ezdxf.const.BOUNDARY_PATH_DEFAULT
            )
            hatch.paths.add_polyline_path(pts, is_closed=True, flags=flags)


def _hatches(msp, plan: FloorPlan, f: _Flip) -> None:
    for r in plan.rooms:
        look = joined_area(plan, r)
        if not look.is_open or look.type in ("pool", "deck"):
            continue
        hatch = msp.add_hatch(color=256, dxfattribs={"layer": "HATCH"})
        hatch.set_pattern_fill("ANSI31", scale=max(6.0, min(r.w, r.h) / 40), color=256)
        hatch.paths.add_polyline_path(_rect_pts(r, f), is_closed=True)


def _pool_and_deck(msp, plan: FloorPlan, f: _Flip) -> None:
    """Pool: water edge and coping on layer POOL. Deck: plank lines on HATCH."""
    for r in plan.rooms:
        if r.type == "pool":
            x, y, w, h = pool_water(r)
            for inset in (0, 12):
                pts = [
                    f(x + inset, y + inset),
                    f(x + w - inset, y + inset),
                    f(x + w - inset, y + h - inset),
                    f(x + inset, y + h - inset),
                ]
                msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "POOL"})
        elif r.type == "deck":
            if r.w >= r.h:
                for k in range(15, r.h, 15):
                    msp.add_line(f(r.x, r.y + k), f(r.x2, r.y + k), dxfattribs={"layer": "HATCH"})
            else:
                for k in range(15, r.w, 15):
                    msp.add_line(f(r.x + k, r.y), f(r.x + k, r.y2), dxfattribs={"layer": "HATCH"})


def _rect_pts(r: Room, f: _Flip) -> list[tuple[float, float]]:
    return [f(r.x, r.y), f(r.x2, r.y), f(r.x2, r.y2), f(r.x, r.y2)]


def _windows(msp, plan: FloorPlan, f: _Flip) -> None:
    t = WALL_EXTERIOR_CM
    attrs = {"layer": "WINDOWS"}
    for win in plan.windows:
        sp = window_span(plan, win)
        (x1, y1), (x2, y2) = sp.start, sp.end
        if sp.horizontal:
            box = [f(x1, y1 - t / 2), f(x2, y1 - t / 2), f(x2, y1 + t / 2), f(x1, y1 + t / 2)]
            lines = [((x1, y1 + o), (x2, y1 + o)) for o in (-t / 6, t / 6)]
        else:
            box = [f(x1 - t / 2, y1), f(x1 + t / 2, y1), f(x1 + t / 2, y2), f(x1 - t / 2, y2)]
            lines = [((x1 + o, y1), (x1 + o, y2)) for o in (-t / 6, t / 6)]
        msp.add_lwpolyline(box, close=True, dxfattribs=attrs)
        for a, b in lines:
            msp.add_line(f(*a), f(*b), dxfattribs=attrs)


def _doors(msp, plan: FloorPlan, f: _Flip) -> None:
    attrs = {"layer": "DOORS"}
    for door in plan.doors:
        sp = door_span(plan, door)
        if door.swing == "none":  # wide opening between public rooms: mark the jambs
            for x, y in (sp.start, sp.end):
                nx, ny = sp.inward
                msp.add_line(
                    f(x - nx * WALL_EXTERIOR_CM / 2, y - ny * WALL_EXTERIOR_CM / 2),
                    f(x + nx * WALL_EXTERIOR_CM / 2, y + ny * WALL_EXTERIOR_CM / 2),
                    dxfattribs=attrs,
                )
            continue
        into, side = door.swing.split("-")
        nx, ny = sp.inward if into == "in" else (-sp.inward[0], -sp.inward[1])
        hinge, other = (sp.start, sp.end) if side == "left" else (sp.end, sp.start)
        r = door.width
        leaf = (hinge[0] + nx * r, hinge[1] + ny * r)
        h, lf, ot = f(*hinge), f(*leaf), f(*other)
        msp.add_line(h, lf, dxfattribs=attrs)
        a1 = math.degrees(math.atan2(lf[1] - h[1], lf[0] - h[0])) % 360
        a2 = math.degrees(math.atan2(ot[1] - h[1], ot[0] - h[0])) % 360
        start, end = (a1, a2) if (a2 - a1) % 360 <= 180 else (a2, a1)  # the 90 deg sweep
        msp.add_arc(h, r, start, end, dxfattribs=attrs)


# ------------------------------------------------------------------- furniture


def _block_name(symbol: str) -> str:
    return symbol.upper()


def _define_block(doc, symbol: str) -> None:
    name = _block_name(symbol)
    if name in doc.blocks:
        return
    blk = doc.blocks.new(name=name)
    attrs = {"layer": "0"}  # BYBLOCK-style: takes the FURNITURE layer of the insert

    def p(x: float, y: float) -> tuple[float, float]:
        return (round(x, 2), round(-y, 2))  # symbol y grows south

    for prim in SYMBOLS[symbol].prims:
        if isinstance(prim, Rect):
            pts = [
                p(prim.x, prim.y),
                p(prim.x + prim.w, prim.y),
                p(prim.x + prim.w, prim.y + prim.h),
                p(prim.x, prim.y + prim.h),
            ]
            blk.add_lwpolyline(pts, close=True, dxfattribs=attrs)
        elif isinstance(prim, Circle):
            blk.add_circle(p(prim.cx, prim.cy), prim.r, dxfattribs=attrs)
        elif isinstance(prim, Line):
            blk.add_line(p(prim.x1, prim.y1), p(prim.x2, prim.y2), dxfattribs=attrs)
        elif isinstance(prim, Arc):
            blk.add_arc(p(prim.cx, prim.cy), prim.r, prim.start_deg, prim.end_deg, dxfattribs=attrs)
        elif isinstance(prim, Poly):
            blk.add_lwpolyline(
                [p(x, y) for x, y in prim.points], close=prim.closed, dxfattribs=attrs
            )


def _fixtures(doc, msp, plan: FloorPlan, f: _Flip) -> None:
    for fx in plan.fixtures:
        _define_block(doc, fx.symbol)
        room = plan.room(fx.room)
        msp.add_blockref(
            _block_name(fx.symbol),
            f(room.x + fx.x, room.y + fx.y),
            dxfattribs={"layer": "FURNITURE", "rotation": (-fx.rotation) % 360},
        )


# ------------------------------------------------------------------------- text


def _text(msp, text: str, at: tuple[float, float], height: float, rotation: float = 0) -> None:
    t = msp.add_text(
        text, height=round(height, 2), dxfattribs={"layer": "TEXT", "rotation": rotation}
    )
    t.set_placement(at, align=TextEntityAlignment.MIDDLE_CENTER)


def _labels(msp, plan: FloorPlan, f: _Flip) -> None:
    """Room name and size, placed clear of furniture and door swings (same rules as SVG)."""
    unit = plan.meta.unit_display
    u = _text_unit(plan)
    for r in plan.rooms:
        if joined_area(plan, r) is not r:
            continue  # part of the garden/pool next to it, which has the label
        name = r.label.upper()
        if r.type == "pool":
            _, _, ww, wh = pool_water(r)
            size = fmt_size(ww, wh, unit)
        else:
            size = fmt_size(r.w, r.h, unit)
        fs_h = _label_fit(r, name, size, u, rotated=False)
        fs_v = _label_fit(r, name, size, u, rotated=True)
        rotated = fs_v > fs_h * 1.3
        fs0 = max(fs_v if rotated else fs_h, 6.0)
        text_len = max(len(name), len(size))
        obstacles = _label_obstacles(plan, r)
        best = None
        for scale in (1.0, 0.8, 0.65):
            fs_try = max(fs0 * scale, 6.0)
            px, py, overlap = _label_position(r, fs_try, text_len, rotated, obstacles)
            key = (overlap, -fs_try, px, py)
            if best is None or key < best:
                best = key
            if overlap == 0:
                break
        fs, px, py = -best[1], best[2], best[3]
        if rotated:  # reads bottom to top; name on the left of the size line
            _text(msp, name, f(px - 0.55 * fs, py), fs, 90)
            _text(msp, size, f(px + 0.55 * fs, py), 0.85 * fs, 90)
        else:
            _text(msp, name, f(px, py - 0.55 * fs), fs)
            _text(msp, size, f(px, py + 0.55 * fs), 0.85 * fs)


def _sheet_text(msp, plan: FloorPlan, f: _Flip) -> None:
    u = _text_unit(plan)
    pw, pd = plan.plot.width, plan.plot.depth
    unit = plan.meta.unit_display
    off = WALL_EXTERIOR_CM / 2 + 6.5 * u
    road = {
        "north": ((pw / 2, -off), 0),
        "south": ((pw / 2, pd + off), 0),
        "west": ((-off, pd / 2), 90),
        "east": ((pw + off, pd / 2), 90),
    }.get(plan.plot.road_side or "")
    if road:
        (x, y), rot = road
        _text(msp, "ROAD", f(x, y), 0.8 * u, rot)
    # north arrow above the north-east corner
    cx, cy = f(pw + 3 * u, -3 * u)
    r = 0.9 * u
    msp.add_circle((cx, cy), r, dxfattribs={"layer": "TEXT"})
    msp.add_lwpolyline(
        [
            (cx, cy + r),
            (cx - 0.4 * r, cy - 0.5 * r),
            (cx, cy - 0.2 * r),
            (cx + 0.4 * r, cy - 0.5 * r),
        ],
        close=True,
        dxfattribs={"layer": "TEXT"},
    )
    _text(msp, "N", (cx, cy + r + 0.6 * u), 0.7 * u)
    # title block under the plan: only what the user entered, plus the computed area
    rows = [
        ("PROJECT", plan.meta.project.strip()),
        ("OWNER", plan.meta.owner.strip()),
        ("FLOOR", plan.meta.floor_name.strip().upper()),
        ("TOTAL AREA", fmt_area(plan.built_area_m2, unit)),
    ]
    top = pd + off + 2.5 * u
    width = pw / len(rows)
    for i, (caption, value) in enumerate(rows):
        x0 = i * width
        box = [f(x0, top), f(x0 + width, top), f(x0 + width, top + 3.4 * u), f(x0, top + 3.4 * u)]
        msp.add_lwpolyline(box, close=True, dxfattribs={"layer": "TEXT"})
        _text(msp, caption, f(x0 + width / 2, top + 0.9 * u), 0.5 * u)
        if value:
            fs = min(1.0 * u, width * 0.9 / (max(len(value), 1) * 0.6))
            _text(msp, value, f(x0 + width / 2, top + 2.3 * u), fs)


# ------------------------------------------------------------------- dimensions


def _dimstyle(doc, plan: FloorPlan) -> None:
    u = _text_unit(plan)
    ds = doc.dimstyles.new(DIMSTYLE)
    ds.dxf.dimtxt = round(0.6 * u, 2)  # text height
    ds.dxf.dimtsz = round(0.3 * u, 2)  # architectural ticks instead of arrows
    ds.dxf.dimexe = round(0.3 * u, 2)
    ds.dxf.dimexo = round(WALL_EXTERIOR_CM / 2 + 4, 2)
    ds.dxf.dimgap = round(0.2 * u, 2)
    ds.dxf.dimtad = 1  # text above the line
    ds.dxf.dimdec = 0
    ds.dxf.dimclrd = 2
    ds.dxf.dimclre = 2
    ds.dxf.dimclrt = 7


def _dimensions(msp, plan: FloorPlan, f: _Flip) -> None:
    pw, pd = plan.plot.width, plan.plot.depth
    unit = plan.meta.unit_display
    u = _text_unit(plan)
    tier1 = WALL_EXTERIOR_CM / 2 + 1.8 * u
    tier2 = tier1 + 2.0 * u
    xs = sorted({0, pw, *(v for r in plan.rooms if r.y == 0 for v in (r.x, r.x2))})
    ys = sorted({0, pd, *(v for r in plan.rooms if r.x == 0 for v in (r.y, r.y2))})

    def dim(p1, p2, base, angle) -> None:
        length = math.dist(p1, p2)
        if length < 1:
            return
        d = msp.add_linear_dim(
            base=base,
            p1=p1,
            p2=p2,
            angle=angle,
            text=fmt_length(length, unit),
            dimstyle=DIMSTYLE,
            dxfattribs={"layer": "DIMENSIONS"},
        )
        d.render()

    for a, b in zip(xs, xs[1:], strict=False):  # chain along the north side
        dim(f(a, 0), f(b, 0), f(a, -tier1), 0)
    dim(f(0, 0), f(pw, 0), f(0, -tier2), 0)  # overall width
    for a, b in zip(ys, ys[1:], strict=False):  # chain along the west side
        dim(f(0, a), f(0, b), f(-tier1, a), 90)
    dim(f(0, 0), f(0, pd), f(-tier2, 0), 90)  # overall depth
