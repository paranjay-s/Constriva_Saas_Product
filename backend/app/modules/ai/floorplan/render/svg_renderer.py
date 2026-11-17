"""Render a FloorPlan to a CAD-style SVG presentation sheet.

Everything is drawn from the plan JSON only. Drawing units are cm (1 SVG unit = 1 cm).
Title-block text comes only from `plan.meta` (user input) and the computed area; no
names or branding are hard-coded.

Draw order: sheet, room fills, open-area hatch, fixtures, walls (with openings cut),
windows, doors, labels, dimensions, north arrow / road, title block.
"""

import math
from xml.sax.saxutils import escape

import shapely
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.geometry import box as shp_box
from shapely.ops import unary_union

from app.modules.ai.floorplan.geometry import (
    door_clear_zone,
    door_span,
    opening_cut,
    pool_water,
    room_box,
    wall_polygon,
    window_span,
)
from app.modules.ai.floorplan.render.symbols import (
    FILLS,
    SYMBOLS,
    Arc,
    Circle,
    Line,
    Poly,
    Rect,
    Symbol,
    footprint,
)
from app.modules.ai.floorplan.rules import WALL_EXTERIOR_CM
from app.modules.ai.floorplan.schemas.plan import FloorPlan, Room
from app.modules.ai.floorplan.units import fmt_area, fmt_length, fmt_size

# Helvetica first: it is built into PDF/PNG converters (PyMuPDF); browsers map it to Arial.
FONT = "Helvetica, Arial, sans-serif"

COLORS = {
    "sheet_line": "#2B2B2B",
    "wall": "#3A3A3A",
    "fixture": "#3B3F44",
    "door": "#3A3A3A",
    "door_arc": "#C0392B",
    "window": "#1F6FB2",
    "label": "#23235B",
    "size": "#C2185B",
    "dim": "#505050",
    "hatch": "#9CC88A",
    "title": "#1A1A1A",
    "title_muted": "#6B6B6B",
    "area": "#1F3FA6",
}

ZONE_FILL = {
    "private": "#FBF3E4",
    "public": "#ECE9F7",
    "service": "#EEF3F7",
    "circulation": "#FAFAF6",
    "open": "#EAF4E3",
}


POOL_COLORS = {
    "paving": "#E7E0D2",
    "water": "#8FCBEA",
    "water_edge": "#2878B5",
    "ripple": "#D6EEF9",
    "deck": "#E2CBA6",
    "plank": "#B48C5E",
}


def _room_label_size(r: Room, unit: str) -> str:
    """Size shown under a room name; a pool shows its water size."""
    if r.type == "pool":
        _, _, ww, wh = pool_water(r)
        return fmt_size(ww, wh, unit)
    return fmt_size(r.w, r.h, unit)


def _pool_and_deck(plan: FloorPlan) -> str:
    parts = ['<g id="pool-deck">']
    for r in plan.rooms:
        if r.type == "pool":
            x, y, w, h = pool_water(r)
            parts.append(
                f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}" rx="10" '
                f'fill="{POOL_COLORS["water"]}" stroke="{POOL_COLORS["water_edge"]}" '
                f'stroke-width="4"/>'
            )
            parts.append(
                f'<rect x="{_n(x + 12)}" y="{_n(y + 12)}" width="{_n(w - 24)}" '
                f'height="{_n(h - 24)}" rx="6" fill="none" stroke="#FFFFFF" '
                f'stroke-width="1.5" stroke-opacity="0.8"/>'
            )
            long_x = w >= h
            n = 3
            for i in range(1, n + 1):  # gentle ripples across the water
                if long_x:
                    yy = y + h * i / (n + 1)
                    pts = " ".join(
                        f"{_n(x + w * (0.2 + 0.6 * k / 8))},{_n(yy + (6 if k % 2 else -6))}"
                        for k in range(9)
                    )
                else:
                    xx = x + w * i / (n + 1)
                    pts = " ".join(
                        f"{_n(xx + (6 if k % 2 else -6))},{_n(y + h * (0.2 + 0.6 * k / 8))}"
                        for k in range(9)
                    )
                parts.append(
                    f'<polyline points="{pts}" fill="none" stroke="{POOL_COLORS["ripple"]}" '
                    f'stroke-width="3" stroke-linejoin="round"/>'
                )
        elif r.type == "deck":
            step = 15
            if r.w >= r.h:  # planks run along the longer side
                for k in range(step, r.h, step):
                    parts.append(
                        f'<line x1="{r.x}" y1="{r.y + k}" x2="{r.x2}" y2="{r.y + k}" '
                        f'stroke="{POOL_COLORS["plank"]}" stroke-width="0.9"/>'
                    )
            else:
                for k in range(step, r.w, step):
                    parts.append(
                        f'<line x1="{r.x + k}" y1="{r.y}" x2="{r.x + k}" y2="{r.y2}" '
                        f'stroke="{POOL_COLORS["plank"]}" stroke-width="0.9"/>'
                    )
    parts.append("</g>")
    return "\n".join(parts)


def _n(v: float) -> str:
    """Compact, deterministic number formatting."""
    s = f"{v:.1f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


class _Sheet:
    """Layout of the sheet around the plot (all in cm)."""

    def __init__(self, plan: FloorPlan) -> None:
        pw, pd = plan.plot.width, plan.plot.depth
        self.u = max(14.0, min(40.0, max(pw, pd) / 60))  # base text unit
        u = self.u
        self.tier1 = WALL_EXTERIOR_CM / 2 + 1.8 * u
        self.tier2 = self.tier1 + 2.0 * u
        self.road = self.tier2 + 1.8 * u
        self.margin = self.road + 1.6 * u + 10
        self.title_h = 3.6 * u
        self.ox = self.margin
        self.oy = self.margin
        self.width = pw + 2 * self.margin
        self.height = pd + 2 * self.margin + self.title_h


def render_svg(plan: FloorPlan) -> str:
    sh = _Sheet(plan)
    unit = plan.meta.unit_display
    out: list[str] = []
    w, h = sh.width, sh.height
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {_n(w)} {_n(h)}" width="{_n(w / 2)}" height="{_n(h / 2)}">'
    )
    out.append(_defs(plan))
    # font-family on a <g>, not the root: PyMuPDF only honours it on child elements.
    out.append(f'<g id="sheet" font-family="{FONT}">')
    out.append(f'<rect x="0" y="0" width="{_n(w)}" height="{_n(h)}" fill="#FFFFFF"/>')
    b = 0.4 * sh.u
    out.append(
        f'<rect x="{_n(b)}" y="{_n(b)}" width="{_n(w - 2 * b)}" height="{_n(h - 2 * b)}" '
        f'fill="none" stroke="{COLORS["sheet_line"]}" stroke-width="{_n(0.25 * sh.u)}"/>'
    )

    out.append(f'<g id="plan" transform="translate({_n(sh.ox)} {_n(sh.oy)})">')
    out.append(_room_fills(plan))
    out.append(_hatches(plan))
    out.append(_pool_and_deck(plan))
    out.append(
        f'<rect id="plot-boundary" x="0" y="0" width="{plan.plot.width}" '
        f'height="{plan.plot.depth}" '
        f'fill="none" stroke="{COLORS["wall"]}" stroke-width="3"/>'
    )
    out.append(_fixtures(plan))
    out.append(_walls(plan))
    out.append(_windows(plan))
    out.append(_doors(plan))
    out.append(_labels(plan, sh))
    out.append(_dimensions(plan, sh))
    out.append(_road(plan, sh))
    out.append("</g>")
    out.append(_north_arrow(sh))
    out.append(_title_block(plan, sh, unit))
    out.append("</g>")
    out.append("</svg>")
    return "\n".join(s for s in out if s) + "\n"


# --------------------------------------------------------------------------- defs


def _defs(plan: FloorPlan) -> str:
    used = sorted({f.symbol for f in plan.fixtures})
    if not used:
        return ""
    parts = ["<defs>"]
    for name in used:
        parts.append(_symbol_def(SYMBOLS[name]))
    parts.append("</defs>")
    return "\n".join(parts)


def _symbol_def(sym: Symbol) -> str:
    dx, dy = sym.w / 2, sym.d / 2
    body = [
        f'<symbol id="sym-{sym.name}" overflow="visible">',
        f'<g fill="none" stroke="{COLORS["fixture"]}" stroke-width="1.8" stroke-linejoin="round">',
    ]
    for p in sym.prims:
        body.append(_prim_svg(p, dx, dy))
    body.append("</g></symbol>")
    return "".join(body)


def _fill(key: str | None) -> str:
    return f' fill="{FILLS[key]}"' if key else ""


def _prim_svg(p, dx: float, dy: float) -> str:
    if isinstance(p, Rect):
        return (
            f'<rect x="{_n(p.x + dx)}" y="{_n(p.y + dy)}" width="{_n(p.w)}" '
            f'height="{_n(p.h)}"{_fill(p.fill)}/>'
        )
    if isinstance(p, Circle):
        return f'<circle cx="{_n(p.cx + dx)}" cy="{_n(p.cy + dy)}" r="{_n(p.r)}"{_fill(p.fill)}/>'
    if isinstance(p, Line):
        return (
            f'<line x1="{_n(p.x1 + dx)}" y1="{_n(p.y1 + dy)}" '
            f'x2="{_n(p.x2 + dx)}" y2="{_n(p.y2 + dy)}"/>'
        )
    if isinstance(p, Arc):
        a0, a1 = math.radians(p.start_deg), math.radians(p.end_deg)
        x0, y0 = p.cx + dx + p.r * math.cos(a0), p.cy + dy - p.r * math.sin(a0)
        x1, y1 = p.cx + dx + p.r * math.cos(a1), p.cy + dy - p.r * math.sin(a1)
        large = 1 if (p.end_deg - p.start_deg) % 360 > 180 else 0
        return f'<path d="M{_n(x0)} {_n(y0)} A{_n(p.r)} {_n(p.r)} 0 {large} 0 {_n(x1)} {_n(y1)}"/>'
    if isinstance(p, Poly):
        pts = " ".join(f"{_n(x + dx)},{_n(y + dy)}" for x, y in p.points)
        tag = "polygon" if p.closed else "polyline"
        return f'<{tag} points="{pts}"{_fill(p.fill)}/>'
    raise TypeError(p)


# ------------------------------------------------------------------- room layers


def joined_area(plan: FloorPlan, r: Room) -> Room:
    """The open area a leftover shaft is drawn as part of (or the room itself)."""
    if r.part_of:
        for o in plan.rooms:
            if o.id == r.part_of:
                return o
    return r


def _room_fill(r: Room) -> str:
    if r.type == "pool":
        return POOL_COLORS["paving"]
    if r.type == "deck":
        return POOL_COLORS["deck"]
    return ZONE_FILL[r.zone]


def _room_fills(plan: FloorPlan) -> str:
    parts = ['<g id="room-fills" stroke="none">']
    for r in plan.rooms:
        fill = _room_fill(joined_area(plan, r))
        parts.append(f'<rect x="{r.x}" y="{r.y}" width="{r.w}" height="{r.h}" fill="{fill}"/>')
    parts.append("</g>")
    return "\n".join(parts)


def _hatches(plan: FloorPlan) -> str:
    """Light diagonal hatch for open areas, as explicit clipped lines (PDF/DXF friendly)."""
    parts = [f'<g id="hatch" stroke="{COLORS["hatch"]}" stroke-width="0.8">']
    step = 18
    for r in plan.rooms:
        look = joined_area(plan, r)
        if not look.is_open or look.type in ("pool", "deck"):
            continue
        area = room_box(r)
        span = r.w + r.h
        for k in range(0, int(span) + step, step):
            ln = LineString([(r.x + k, r.y), (r.x + k - span, r.y + span)]).intersection(area)
            if isinstance(ln, LineString) and ln.length > 1:
                (x1, y1), (x2, y2) = ln.coords[0], ln.coords[-1]
                parts.append(f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}"/>')
    parts.append("</g>")
    return "\n".join(parts)


def _fixtures(plan: FloorPlan) -> str:
    parts = ['<g id="fixtures">']
    for f in plan.fixtures:
        room = plan.room(f.room)
        sym = SYMBOLS[f.symbol]
        gx, gy = room.x + f.x, room.y + f.y
        parts.append(
            f'<use xlink:href="#sym-{f.symbol}" width="{_n(sym.w)}" height="{_n(sym.d)}" '
            f'transform="translate({_n(gx)} {_n(gy)}) rotate({f.rotation}) '
            f'translate({_n(-sym.w / 2)} {_n(-sym.d / 2)})"/>'
        )
    parts.append("</g>")
    return "\n".join(parts)


def _walls(plan: FloorPlan) -> str:
    walls = wall_polygon(plan)
    cuts = [opening_cut(door_span(plan, d), WALL_EXTERIOR_CM + 2) for d in plan.doors]
    cuts += [opening_cut(window_span(plan, w), WALL_EXTERIOR_CM + 2) for w in plan.windows]
    if cuts:
        walls = walls.difference(unary_union(cuts))
    walls = shapely.normalize(walls)
    return (
        f'<g id="walls"><path fill="{COLORS["wall"]}" fill-rule="evenodd" stroke="none" '
        f'd="{_geom_path(walls)}"/></g>'
    )


def _geom_path(geom) -> str:
    polys: list[Polygon] = []
    if isinstance(geom, Polygon):
        polys = [geom]
    elif isinstance(geom, MultiPolygon):
        polys = list(geom.geoms)
    else:
        polys = [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]
    d: list[str] = []
    for poly in polys:
        for ring in (poly.exterior, *poly.interiors):
            coords = list(ring.coords)[:-1]
            if len(coords) < 3:
                continue
            d.append("M" + " L".join(f"{_n(x)} {_n(y)}" for x, y in coords) + " Z")
    return " ".join(d)


def _windows(plan: FloorPlan) -> str:
    parts = [f'<g id="windows" stroke="{COLORS["window"]}" stroke-width="1.4">']
    t = WALL_EXTERIOR_CM
    for win in plan.windows:
        sp = window_span(plan, win)
        (x1, y1), (x2, y2) = sp.start, sp.end
        if sp.horizontal:
            parts.append(
                f'<rect x="{_n(x1)}" y="{_n(y1 - t / 2)}" width="{_n(x2 - x1)}" height="{_n(t)}" '
                f'fill="#FFFFFF"/>'
            )
            for off in (-t / 6, t / 6):
                parts.append(
                    f'<line x1="{_n(x1)}" y1="{_n(y1 + off)}" x2="{_n(x2)}" y2="{_n(y1 + off)}"/>'
                )
        else:
            parts.append(
                f'<rect x="{_n(x1 - t / 2)}" y="{_n(y1)}" width="{_n(t)}" height="{_n(y2 - y1)}" '
                f'fill="#FFFFFF"/>'
            )
            for off in (-t / 6, t / 6):
                parts.append(
                    f'<line x1="{_n(x1 + off)}" y1="{_n(y1)}" x2="{_n(x1 + off)}" y2="{_n(y2)}"/>'
                )
    parts.append("</g>")
    return "\n".join(parts)


def _doors(plan: FloorPlan) -> str:
    parts = ['<g id="doors">']
    for door in plan.doors:
        if door.swing == "none":
            continue
        sp = door_span(plan, door)
        into, side = door.swing.split("-")
        nx, ny = sp.inward if into == "in" else (-sp.inward[0], -sp.inward[1])
        hinge, other = (sp.start, sp.end) if side == "left" else (sp.end, sp.start)
        r = door.width
        leaf = (hinge[0] + nx * r, hinge[1] + ny * r)
        v1 = (leaf[0] - hinge[0], leaf[1] - hinge[1])
        v2 = (other[0] - hinge[0], other[1] - hinge[1])
        sweep = 1 if v1[0] * v2[1] - v1[1] * v2[0] > 0 else 0
        parts.append(
            f'<line x1="{_n(hinge[0])}" y1="{_n(hinge[1])}" x2="{_n(leaf[0])}" y2="{_n(leaf[1])}" '
            f'stroke="{COLORS["door"]}" stroke-width="3"/>'
        )
        parts.append(
            f'<path d="M{_n(leaf[0])} {_n(leaf[1])} A{_n(r)} {_n(r)} 0 0 {sweep} '
            f'{_n(other[0])} {_n(other[1])}" fill="none" stroke="{COLORS["door_arc"]}" '
            f'stroke-width="1" stroke-dasharray="6 4"/>'
        )
    parts.append("</g>")
    return "\n".join(parts)


# ------------------------------------------------------------------------ labels


def _label_fit(room: Room, name: str, size: str, u: float, rotated: bool) -> float:
    along, across = (room.h, room.w) if rotated else (room.w, room.h)
    longest = max(len(name), len(size), 4)
    return min(1.15 * u, along * 0.85 / (longest * 0.6), across / 3.2)


def _label_obstacles(plan: FloorPlan, room: Room) -> list[Polygon]:
    """Fixture footprints and door swing areas inside a room."""
    boxes = [z for d in plan.doors if (z := door_clear_zone(plan, d, room.id)) is not None]
    for f in plan.fixtures:
        if f.room != room.id:
            continue
        fw, fd = footprint(f.symbol, f.rotation)
        gx, gy = room.x + f.x, room.y + f.y
        boxes.append(shp_box(gx - fw / 2, gy - fd / 2, gx + fw / 2, gy + fd / 2))
    return boxes


def _label_position(
    room: Room, fs: float, text_len: int, rotated: bool, obstacles: list[Polygon]
) -> tuple[float, float, float]:
    """Return (x, y, overlap_area) for the label block.

    Prefers a spot with no overlap nearest the room centre; otherwise the spot with the
    least overlap with fixtures and door swings.
    """
    cx, cy = room.x + room.w / 2, room.y + room.h / 2
    if not obstacles:
        return cx, cy, 0.0
    bw, bh = text_len * fs * 0.62, fs * 2.2
    if rotated:
        bw, bh = bh, bw
    inner = shp_box(room.x, room.y, room.x2, room.y2).buffer(-WALL_EXTERIOR_CM / 2 - 2)
    blocked = unary_union(obstacles).buffer(4)
    step = max(8.0, min(room.w, room.h) / 14)
    best: tuple[float, float, float, float] | None = None  # (overlap, dist, x, y)
    nx, ny = int(room.w / step), int(room.h / step)
    for i in range(nx + 1):
        for j in range(ny + 1):
            px, py = room.x + i * step, room.y + j * step
            lab = shp_box(px - bw / 2, py - bh / 2, px + bw / 2, py + bh / 2)
            if not inner.contains(lab):
                continue
            key = (round(lab.intersection(blocked).area), (px - cx) ** 2 + (py - cy) ** 2, px, py)
            if best is None or key < best:
                best = key
    if best is None:
        return cx, cy, float("inf")
    return best[2], best[3], float(best[0])


def _labels(plan: FloorPlan, sh: _Sheet) -> str:
    unit = plan.meta.unit_display
    parts = ['<g id="labels" text-anchor="middle" font-weight="bold">']
    for r in plan.rooms:
        if joined_area(plan, r) is not r:
            continue  # drawn as part of the garden/pool next to it, which has the label
        name = escape(r.label.upper())
        size = escape(_room_label_size(r, unit))
        fs_h = _label_fit(r, name, size, sh.u, rotated=False)
        fs_v = _label_fit(r, name, size, sh.u, rotated=True)
        rotated = fs_v > fs_h * 1.3
        fs0 = max(fs_v if rotated else fs_h, 6.0)
        text_len = max(len(r.label), len(size))
        obstacles = _label_obstacles(plan, r)
        # Try full size first, then shrink, keeping the first overlap-free placement.
        best: tuple[float, float, float, float] | None = None  # (overlap, -fs, x, y)
        for scale in (1.0, 0.8, 0.65):
            fs_try = max(fs0 * scale, 6.0)
            px, py, overlap = _label_position(r, fs_try, text_len, rotated, obstacles)
            key = (overlap, -fs_try, px, py)
            if best is None or key < best:
                best = key
            if overlap == 0:
                break
        assert best is not None
        fs, cx, cy = -best[1], best[2], best[3]
        cy -= 0.45 * fs  # centre the two-line block on the chosen point
        rot = f' transform="rotate(-90 {_n(cx)} {_n(cy)})"' if rotated else ""
        parts.append(
            f'<g{rot}><text x="{_n(cx)}" y="{_n(cy - 0.1 * fs)}" font-size="{_n(fs)}" '
            f'fill="{COLORS["label"]}">{name}</text>'
            f'<text x="{_n(cx)}" y="{_n(cy + 1.0 * fs)}" font-size="{_n(0.85 * fs)}" '
            f'fill="{COLORS["size"]}">{size}</text></g>'
        )
    parts.append("</g>")
    return "\n".join(parts)


# -------------------------------------------------------------------- dimensions


def _breaks(values: list[int], total: int) -> list[int]:
    return sorted({0, total, *values})


def _dimensions(plan: FloorPlan, sh: _Sheet) -> str:
    pw, pd = plan.plot.width, plan.plot.depth
    unit = plan.meta.unit_display
    xs = _breaks([v for r in plan.rooms if r.y == 0 for v in (r.x, r.x2)], pw)
    ys = _breaks([v for r in plan.rooms if r.x == 0 for v in (r.y, r.y2)], pd)
    u = sh.u
    parts = [
        f'<g id="dimensions" stroke="{COLORS["dim"]}" stroke-width="1" fill="{COLORS["dim"]}">'
    ]
    for a, b in zip(xs, xs[1:], strict=False):
        parts.append(_dim_h(a, b, -sh.tier1, 0, unit, u))
    parts.append(_dim_h(0, pw, -sh.tier2, 0, unit, u))
    parts.append(_dim_h(0, pw, pd + sh.tier1, pd, unit, u))
    for a, b in zip(ys, ys[1:], strict=False):
        parts.append(_dim_v(a, b, -sh.tier1, 0, unit, u))
    parts.append(_dim_v(0, pd, -sh.tier2, 0, unit, u))
    parts.append(_dim_v(0, pd, pw + sh.tier1, pw, unit, u))
    parts.append("</g>")
    return "\n".join(parts)


def _dim_text_size(length: float, text: str, u: float) -> float:
    return min(0.62 * u, length * 0.8 / (max(len(text), 1) * 0.6))


def _tick(x: float, y: float, k: float) -> str:
    return (
        f'<line x1="{_n(x - k)}" y1="{_n(y + k)}" x2="{_n(x + k)}" y2="{_n(y - k)}" '
        f'stroke-width="1.6"/>'
    )


def _dim_h(x1: float, x2: float, y: float, base_y: float, unit: str, u: float) -> str:
    sign = -1 if y < base_y else 1
    gap = WALL_EXTERIOR_CM / 2 + 4
    k = 0.3 * u
    out = [f'<line x1="{_n(x1)}" y1="{_n(y)}" x2="{_n(x2)}" y2="{_n(y)}"/>']
    for x in (x1, x2):
        out.append(
            f'<line x1="{_n(x)}" y1="{_n(base_y + sign * gap)}" x2="{_n(x)}" '
            f'y2="{_n(y + sign * k)}" '
            f'stroke-width="0.6"/>'
        )
        out.append(_tick(x, y, k))
    text = escape(fmt_length(x2 - x1, unit))
    fs = _dim_text_size(x2 - x1, text, u)
    if fs >= 0.25 * u:
        out.append(
            f'<text x="{_n((x1 + x2) / 2)}" y="{_n(y - 0.3 * fs)}" font-size="{_n(fs)}" '
            f'text-anchor="middle" stroke="none">{text}</text>'
        )
    return "".join(out)


def _dim_v(y1: float, y2: float, x: float, base_x: float, unit: str, u: float) -> str:
    sign = -1 if x < base_x else 1
    gap = WALL_EXTERIOR_CM / 2 + 4
    k = 0.3 * u
    out = [f'<line x1="{_n(x)}" y1="{_n(y1)}" x2="{_n(x)}" y2="{_n(y2)}"/>']
    for y in (y1, y2):
        out.append(
            f'<line x1="{_n(base_x + sign * gap)}" y1="{_n(y)}" x2="{_n(x + sign * k)}" '
            f'y2="{_n(y)}" '
            f'stroke-width="0.6"/>'
        )
        out.append(_tick(x, y, k))
    text = escape(fmt_length(y2 - y1, unit))
    fs = _dim_text_size(y2 - y1, text, u)
    if fs >= 0.25 * u:
        cy = (y1 + y2) / 2
        tx = x - 0.3 * fs
        out.append(
            f'<text x="{_n(tx)}" y="{_n(cy)}" font-size="{_n(fs)}" text-anchor="middle" '
            f'stroke="none" transform="rotate(-90 {_n(tx)} {_n(cy)})">{text}</text>'
        )
    return "".join(out)


# ------------------------------------------------------------- arrow, road, title


def _road(plan: FloorPlan, sh: _Sheet) -> str:
    side = plan.plot.road_side
    if side is None:
        return ""
    pw, pd = plan.plot.width, plan.plot.depth
    fs = 0.8 * sh.u
    attrs = (
        f'font-size="{_n(fs)}" text-anchor="middle" letter-spacing="{_n(0.6 * fs)}" '
        f'fill="{COLORS["dim"]}"'
    )
    if side == "north":
        return f'<text id="road" x="{_n(pw / 2)}" y="{_n(-sh.road)}" {attrs}>ROAD</text>'
    if side == "south":
        return f'<text id="road" x="{_n(pw / 2)}" y="{_n(pd + sh.road + fs)}" {attrs}>ROAD</text>'
    x = -sh.road if side == "west" else pw + sh.road
    return (
        f'<text id="road" x="{_n(x)}" y="{_n(pd / 2)}" {attrs} '
        f'transform="rotate(-90 {_n(x)} {_n(pd / 2)})">ROAD</text>'
    )


def _north_arrow(sh: _Sheet) -> str:
    r = 0.9 * sh.u
    cx, cy = sh.width - sh.margin / 2, sh.margin / 2
    return (
        f'<g id="north-arrow" stroke="{COLORS["dim"]}" stroke-width="1.2">'
        f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}" fill="none"/>'
        f'<polygon points="{_n(cx)},{_n(cy - r)} {_n(cx - 0.4 * r)},{_n(cy + 0.5 * r)} '
        f'{_n(cx)},{_n(cy + 0.2 * r)} {_n(cx + 0.4 * r)},{_n(cy + 0.5 * r)}" '
        f'fill="{COLORS["dim"]}"/>'
        f'<text x="{_n(cx)}" y="{_n(cy - r - 0.25 * sh.u)}" font-size="{_n(0.7 * sh.u)}" '
        f'text-anchor="middle" stroke="none" fill="{COLORS["dim"]}" font-weight="bold">N</text></g>'
    )


def _fit(text: str, base: float, width: float) -> float:
    return min(base, width * 0.9 / (max(len(text), 1) * 0.6))


def _title_block(plan: FloorPlan, sh: _Sheet, unit: str) -> str:
    u = sh.u
    b = 0.4 * u
    x0, x1 = b, sh.width - b
    y1 = sh.height - b
    y0 = y1 - sh.title_h
    width = x1 - x0
    cols = [0.32, 0.28, 0.2, 0.2]
    edges = [x0]
    for c in cols:
        edges.append(edges[-1] + c * width)
    project = escape(plan.meta.project.strip())
    owner = escape(plan.meta.owner.strip())
    floor = escape(plan.meta.floor_name.strip().upper())
    area = escape(fmt_area(plan.built_area_m2, unit))

    parts = [
        f'<g id="title-block" stroke="{COLORS["sheet_line"]}" stroke-width="{_n(0.15 * u)}">',
        f'<rect x="{_n(x0)}" y="{_n(y0)}" width="{_n(width)}" height="{_n(sh.title_h)}" '
        f'fill="none"/>',
    ]
    for ex in edges[1:-1]:
        parts.append(f'<line x1="{_n(ex)}" y1="{_n(y0)}" x2="{_n(ex)}" y2="{_n(y1)}"/>')
    small = 0.55 * u
    cells = [("PROJECT", project, COLORS["title"]), ("OWNER", owner, COLORS["title"])]
    for i, (caption, value, color) in enumerate(cells):
        cx0, cw = edges[i], edges[i + 1] - edges[i]
        parts.append(
            f'<text x="{_n(cx0 + 0.5 * u)}" y="{_n(y0 + 1.0 * u)}" font-size="{_n(small)}" '
            f'stroke="none" fill="{COLORS["title_muted"]}">{caption}</text>'
        )
        if value:
            fs = _fit(value, 1.1 * u, cw - u)
            parts.append(
                f'<text x="{_n(cx0 + 0.5 * u)}" y="{_n(y0 + 2.6 * u)}" font-size="{_n(fs)}" '
                f'stroke="none" fill="{color}" font-weight="bold">{value}</text>'
            )
    # floor name
    cx0, cw = edges[2], edges[3] - edges[2]
    fs = _fit(floor, 1.3 * u, cw)
    parts.append(
        f'<text x="{_n(cx0 + cw / 2)}" y="{_n(y0 + sh.title_h / 2 + 0.45 * fs)}" '
        f'font-size="{_n(fs)}" '
        f'text-anchor="middle" stroke="none" fill="{COLORS["title"]}" '
        f'font-weight="bold">{floor}</text>'
    )
    # total area
    cx0, cw = edges[3], edges[4] - edges[3]
    parts.append(
        f'<text x="{_n(cx0 + cw / 2)}" y="{_n(y0 + 1.0 * u)}" font-size="{_n(small)}" '
        f'text-anchor="middle" stroke="none" fill="{COLORS["title_muted"]}">TOTAL AREA</text>'
    )
    fs = _fit(area, 1.1 * u, cw)
    parts.append(
        f'<text x="{_n(cx0 + cw / 2)}" y="{_n(y0 + 2.6 * u)}" font-size="{_n(fs)}" '
        f'text-anchor="middle" '
        f'stroke="none" fill="{COLORS["area"]}" font-weight="bold">{area}</text>'
    )
    parts.append("</g>")
    return "\n".join(parts)
