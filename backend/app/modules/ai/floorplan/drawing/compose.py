"""Building -> Sheet (display list on A3 or A1 at a stated scale).

Layout of the sheet (A3 landscape; A1 is the same layout at twice the size):

    +-----------------------------------------------+-------------+
    |  plot chain (outside the plot)                | logo        |
    |    building chains (in the setback strips)    | project ... |
    |        the plan, north up                     | north arrow |
    |                                               | revisions   |
    |  GROUND FLOOR PLAN  SCALE 1:100   [scale bar] | areas       |
    |                                               | legend      |
    +-----------------------------------------------+-------------+

The scale is the largest standard scale (style.SCALES) at which the plot and its
dimension chains fit. Everything is placed by code; text is kept off lines: room labels
move clear of fixtures, door swings and stairs, and labels on hatched ground get a white
mask behind them.
"""

import math
from functools import lru_cache

import pymupdf
from shapely.geometry import LineString, MultiLineString, Polygon, box
from shapely.ops import unary_union

from app.modules.ai.floorplan.drawing.blocks import BLOCKS, place
from app.modules.ai.floorplan.drawing.display import Arc, Area, Circle, Line, Sheet, Text
from app.modules.ai.floorplan.drawing.style import (
    FONT_BOLD,
    FONT_REGULAR,
    GREY,
    HATCH,
    INK,
    PEN,
    SCALES,
    SHEETS,
    TEXT,
)
from app.modules.ai.floorplan.model.areas import SQFT_PER_M2, area_lines
from app.modules.ai.floorplan.model.building import Building, Opening, Storey, Wall
from app.modules.ai.floorplan.model.planto3d import _wall_rect

FRAME_IN = 8.0
STRIP_W = 98.0  # title strip on the right (A3)
FOOT_H = 20.0  # drawing title and scale bar under the plan
CHAIN_GAP = 6.5  # between dimension chains
MM_PER_IN = 25.4


# ------------------------------------------------------------------ text metrics


@lru_cache(maxsize=2)
def _font(bold: bool) -> pymupdf.Font:
    return pymupdf.Font(fontfile=str(FONT_BOLD if bold else FONT_REGULAR))


def text_width(text: str, size: float, bold: bool = False) -> float:
    return _font(bold).text_length(text, fontsize=size)


# ------------------------------------------------------------------ units


def fmt_len(mm: float, unit: str) -> str:
    if unit == "ft":
        inches = round(mm / MM_PER_IN)
        ft, inch = divmod(inches, 12)
        return f"{ft}'{inch}\""
    if unit == "m":
        return f"{mm / 1000:.2f}"
    if unit == "cm":
        return f"{mm / 10:.0f}"
    return f"{mm:.0f}"


def chain_labels(points: list[float], unit: str) -> list[str]:
    """Labels of the segments between sorted points (mm). Positions are rounded
    cumulatively, so the segments add up exactly to the rounded overall length."""
    if unit == "ft":
        q = [round(p / MM_PER_IN) for p in points]
        out = []
        for a, b in zip(q, q[1:], strict=False):
            ft, inch = divmod(b - a, 12)
            out.append(f"{ft}'{inch}\"")
        return out
    step = {"m": 10, "cm": 10, "mm": 1}.get(unit, 10)
    q = [round(p / step) * step for p in points]
    return [fmt_len(b - a, unit) for a, b in zip(q, q[1:], strict=False)]


def fmt_area(m2: float, unit: str) -> str:
    if unit == "ft":
        return f"{m2:.1f} m² / {m2 * SQFT_PER_M2:,.0f} sq ft"
    return f"{m2:.1f} m²"


# ------------------------------------------------------------------ composer


class _Composer:
    def __init__(self, b: Building, sheet: str, furniture: bool, unit: str | None) -> None:
        self.b = b
        self.k = 2.0 if sheet == "A1" else 1.0  # A1 is A3 at twice the size
        w, h = SHEETS["A3"]
        self.sheet = Sheet(w * self.k, h * self.k, scale=100, title=b.meta.title)
        self.unit = unit or b.meta.unit_display
        self.furniture = furniture
        self.st: Storey = b.storeys[0]
        self.labels_taken: list[tuple[float, float, float, float]] = []

    # sizes on paper scale with the sheet
    def s(self, v: float) -> float:
        return v * self.k

    def pen(self, name: str) -> float:
        return PEN[name] * self.k

    def txt(self, name: str) -> float:
        return TEXT[name] * self.k

    # ---------------------------------------------------------------- placement
    def choose_scale(self) -> None:
        site = self.b.site
        sb = site.setbacks
        inside_chains = min(sb.front, sb.rear, sb.left, sb.right) > 0
        band = self.s(14 if inside_chains else 3 * CHAIN_GAP + 6)
        x0 = self.s(FRAME_IN + 4)
        x1 = self.sheet.width - self.s(FRAME_IN + STRIP_W + 4)
        y0 = self.s(FRAME_IN + 4)
        y1 = self.sheet.height - self.s(FRAME_IN + FOOT_H)
        avail_w, avail_h = x1 - x0 - 2 * band, y1 - y0 - 2 * band
        scale = SCALES[-1]
        for s in SCALES:
            if site.width / s <= avail_w and site.depth / s <= avail_h:
                scale = s
                break
        self.scale = scale
        self.sheet.scale = scale
        pw, ph = site.width / scale, site.depth / scale
        self.ox = x0 + band + (avail_w - pw) / 2
        self.oy = y0 + band + (avail_h - ph) / 2
        self.inside_chains = inside_chains
        self.draw_box = (x0, y0, x1, y1)

    def P(self, x: float, y: float) -> tuple[float, float]:
        return (self.ox + x / self.scale, self.oy + y / self.scale)

    def ring(self, coords) -> list[tuple[float, float]]:
        return [self.P(x, y) for x, y in coords]

    def add_poly(self, geom, fill, layer, stroke=None, width=0.0) -> None:
        polys = [geom] if geom.geom_type == "Polygon" else list(getattr(geom, "geoms", []))
        for p in polys:
            if p.geom_type != "Polygon" or p.is_empty:
                continue
            rings = [self.ring(p.exterior.coords)] + [self.ring(i.coords) for i in p.interiors]
            self.sheet.add(Area(rings, fill, layer, stroke, width))

    # ---------------------------------------------------------------- hatches
    def hatch(self, geom_mm, kind: str, layer: str) -> None:
        spec = HATCH[kind]
        paper = (
            Polygon(
                self.ring(geom_mm.exterior.coords), [self.ring(i.coords) for i in geom_mm.interiors]
            )
            if geom_mm.geom_type == "Polygon"
            else None
        )
        if paper is None or paper.is_empty:
            for g in getattr(geom_mm, "geoms", []):
                self.hatch(g, kind, layer)
            return
        if "grid" in spec:
            for ang in (0, 90):
                self._hatch_lines(paper, ang, self.s(spec["grid"]), spec["color"], None, layer)
        else:
            dash = tuple(self.s(v) for v in spec["dash"]) if spec.get("dash") else None
            self._hatch_lines(paper, spec["angle"], self.s(spec["gap"]), spec["color"], dash, layer)

    def _hatch_lines(self, poly, angle, gap, color, dash, layer) -> None:
        minx, miny, maxx, maxy = poly.bounds
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        r = math.hypot(maxx - minx, maxy - miny) / 2 + gap
        a = math.radians(angle)
        dx, dy = math.cos(a), math.sin(a)
        nx, ny = -dy, dx
        n = int(r / gap) + 1
        for i in range(-n, n + 1):
            ox, oy = cx + nx * i * gap, cy + ny * i * gap
            seg = LineString([(ox - dx * r, oy - dy * r), (ox + dx * r, oy + dy * r)])
            cut = seg.intersection(poly)
            parts = [cut] if cut.geom_type == "LineString" else list(getattr(cut, "geoms", []))
            for p in parts:
                if p.geom_type == "LineString" and p.length > 0.2:
                    self.sheet.add(Line(list(p.coords), self.pen("fine"), layer, color, dash))

    # ---------------------------------------------------------------- site
    def site(self) -> None:
        b, site = self.b, self.b.site
        plot = box(0, 0, site.width, site.depth)
        footprint = (
            unary_union([Polygon(r.polygon) for r in self.st.rooms]).buffer(100, join_style="mitre")
            if self.st.rooms
            else Polygon()
        )
        names = {
            "pool": "SWIMMING POOL",
            "lawn": "LAWN",
            "garden": "GARDEN",
            "courtyard": "COURTYARD",
            "parking": "PARKING",
            "driveway": "DRIVEWAY",
            "paving": "",
            "deck": "DECK",
            "balcony": "BALCONY",
            "dock": "DOCK",
        }
        for e in site.elements:
            poly = Polygon(e.polygon).difference(footprint)
            if poly.is_empty:
                continue
            if e.kind == "boundary_wall":
                self.add_poly(poly, GREY["site_wall"], "L-SITE-WALL", INK, self.pen("normal"))
                continue
            if e.kind == "gate":
                xs = [p[0] for p in e.polygon]
                ys = [p[1] for p in e.polygon]
                mid_y = (min(ys) + max(ys)) / 2
                mid_x = (min(xs) + max(xs)) / 2
                if max(xs) - min(xs) >= max(ys) - min(ys):
                    pts = [self.P(min(xs), mid_y), self.P(max(xs), mid_y)]
                else:
                    pts = [self.P(mid_x, min(ys)), self.P(mid_x, max(ys))]
                self.sheet.add(
                    Line(pts, self.pen("thin"), "L-SITE-GATE", INK, (self.s(1.2), self.s(0.8)))
                )
                continue
            kind = {
                "pool": "coping",
                "lawn": "lawn",
                "garden": "garden",
                "parking": "parking",
                "deck": "deck",
            }.get(e.kind, "paving")
            area = poly
            if e.kind == "pool" and e.water:
                water = Polygon(e.water)
                area = poly.difference(water)
                self.hatch(water, "water", "L-SITE-POOL")
                self.add_poly(water, None, "L-SITE-POOL", INK, self.pen("normal"))
                inner = water.buffer(-150, join_style="mitre")
                if not inner.is_empty:
                    self.add_poly(inner, None, "L-SITE-POOL", GREY["text_muted"], self.pen("fine"))
            self.hatch(area, kind, f"L-SITE-{e.kind.upper()}")
            self.add_poly(poly, None, f"L-SITE-{e.kind.upper()}", GREY["rule"], self.pen("fine"))
            if e.kind == "garden" or e.kind == "lawn":
                c = poly.representative_point()
                r = min(1800.0, max(600.0, math.sqrt(poly.area) * 0.15))
                if poly.buffer(-r).area > 0:
                    self._shapes(
                        BLOCKS["tree"](2 * r, 2 * r), c.x, c.y, 0, "L-PLNT", GREY["furniture"]
                    )
            label = names.get(e.kind, "")
            if e.name and e.kind not in ("paving",):
                label = e.name.upper()
            if label:
                self.site_label(poly, e, label)
        # plot boundary (chain) and setback line (dashed)
        self.sheet.add(
            Line(
                self.ring(plot.exterior.coords),
                self.pen("wide"),
                "C-PROP",
                INK,
                (self.s(6), self.s(1), self.s(0.8), self.s(1)),
                True,
            )
        )
        from app.modules.ai.floorplan.model.build import setback_box

        x0, y0, x1, y1 = setback_box(site)
        if (x0, y0, x1, y1) != (0, 0, site.width, site.depth):
            sb = box(x0, y0, x1, y1)
            self.sheet.add(
                Line(
                    self.ring(sb.exterior.coords),
                    self.pen("thin"),
                    "C-PROP-SETB",
                    GREY["text_muted"],
                    (self.s(2.5), self.s(1.2)),
                    True,
                )
            )
        _ = b

    def site_label(self, poly, e, label: str) -> None:
        """The area's name and size where the whole label fits inside it (turned for a
        narrow strip, smaller if needed); no label rather than one over a wall."""
        area_m2 = poly.area / 1e6
        host = Polygon(e.water) if (e.kind == "pool" and e.water) else poly
        walls = [
            Polygon(x.polygon) for x in self.b.site.elements if x.kind in ("boundary_wall", "gate")
        ]
        if walls:
            host = host.difference(unary_union(walls).buffer(150))
        option_sets = [
            [
                (label, self.txt("room"), True),
                (fmt_area(area_m2, self.unit), self.txt("label"), False),
            ],
            [
                (label, self.txt("label"), True),
                (fmt_area(area_m2, self.unit), self.txt("small"), False),
            ],
            [(label, self.txt("small"), True)],
        ]
        for lines in option_sets:
            w = max(text_width(t, sz, b) for t, sz, b in lines) + self.s(1.5)
            h = sum(sz * 1.3 for _, sz, _ in lines) + self.s(1)
            for rotate in (False, True):
                ww, hh = (h, w) if rotate else (w, h)
                wm, hm = ww * self.scale, hh * self.scale  # mm on the ground
                core = host.buffer(-min(wm, hm) / 2, join_style="mitre")
                if core.is_empty:
                    continue
                minx, miny, maxx, maxy = core.bounds
                c0 = core.centroid
                cands = [(c0.x, c0.y)] + [
                    (minx + (maxx - minx) * i / 8, miny + (maxy - miny) * j / 8)
                    for i in range(9)
                    for j in range(9)
                ]
                cands.sort(key=lambda p: (p[0] - c0.x) ** 2 + (p[1] - c0.y) ** 2)
                for x, y in cands:
                    rect = box(x - wm / 2, y - hm / 2, x + wm / 2, y + hm / 2)
                    if host.contains(rect):
                        px, py = self.P(x, y)
                        bb = (px - ww / 2, py - hh / 2, px + ww / 2, py + hh / 2)
                        if any(_overlap(bb, o) for o in self.labels_taken):
                            continue
                        self.block(
                            px,
                            py,
                            lines,
                            "L-SITE-IDEN",
                            mask=True,
                            rotation=90.0 if rotate else 0.0,
                        )
                        self.labels_taken.append(bb)
                        return

    # ---------------------------------------------------------------- walls
    def walls(self) -> None:
        st = self.st
        rects = {w.id: box(*_wall_rect(w, st.walls)) for w in st.walls}
        cuts = []
        for o in st.openings:
            w = st.wall(o.wall)
            cuts.append(self._opening_box(w, o, extra=5))
        cut = unary_union(cuts) if cuts else Polygon()
        ext = unary_union([rects[w.id] for w in st.walls if w.kind == "exterior"])
        inner = unary_union([rects[w.id] for w in st.walls if w.kind != "exterior"]).difference(ext)
        self.add_poly(inner.difference(cut), GREY["wall_int"], "A-WALL-PATT", INK, self.pen("wide"))
        self.add_poly(ext.difference(cut), GREY["wall_ext"], "A-WALL", INK, self.pen("thick"))

    def _opening_box(self, w: Wall, o: Opening, extra: float = 0.0):
        h = w.thickness / 2 + extra
        if w.horizontal:
            cx, cy = w.a[0] + o.offset, w.a[1]
            return box(cx - o.width / 2, cy - h, cx + o.width / 2, cy + h)
        cx, cy = w.a[0], w.a[1] + o.offset
        return box(cx - h, cy - o.width / 2, cx + h, cy + o.width / 2)

    # ---------------------------------------------------------------- openings
    def openings(self) -> None:
        st = self.st
        polys = {r.id: Polygon(r.polygon) for r in st.rooms}
        for o in st.openings:
            w = st.wall(o.wall)
            if o.kind == "window":
                self.window(w, o)
            else:
                self.door(w, o, polys)

    def _axis(self, w: Wall, o: Opening):
        """(start point, end point, unit along, unit across) of the opening, mm."""
        if w.horizontal:
            cx, cy = w.a[0] + o.offset, w.a[1]
            return (cx - o.width / 2, cy), (cx + o.width / 2, cy), (1, 0), (0, 1)
        cx, cy = w.a[0], w.a[1] + o.offset
        return (cx, cy - o.width / 2), (cx, cy + o.width / 2), (0, 1), (1, 0)

    def window(self, w: Wall, o: Opening) -> None:
        a, b, _, n = self._axis(w, o)
        h = w.thickness / 2
        for off, pen, color in (
            (-h, "normal", INK),
            (h, "normal", INK),
            (-h * 0.18, "thin", INK),
            (h * 0.18, "thin", INK),
        ):
            p1 = (a[0] + n[0] * off, a[1] + n[1] * off)
            p2 = (b[0] + n[0] * off, b[1] + n[1] * off)
            self.sheet.add(Line([self.P(*p1), self.P(*p2)], self.pen(pen), "A-GLAZ", color))

    def door(self, w: Wall, o: Opening, polys) -> None:
        a, b, u, n = self._axis(w, o)
        h = w.thickness / 2
        into = o.rooms[0]
        side = 1.0
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if into and into in polys:
            c = polys[into].representative_point()
            side = 1.0 if (c.x - mid[0]) * n[0] + (c.y - mid[1]) * n[1] > 0 else -1.0
        elif o.rooms[1] and o.rooms[1] in polys:
            c = polys[o.rooms[1]].representative_point()
            side = -1.0 if (c.x - mid[0]) * n[0] + (c.y - mid[1]) * n[1] > 0 else 1.0
        if o.operation == "sliding":
            t = 35.0
            for k, (p0, frac) in enumerate(((a, 0.0), (b, 0.45))):
                s0 = (a[0] + u[0] * o.width * frac, a[1] + u[1] * o.width * frac)
                s1 = (s0[0] + u[0] * o.width * 0.55, s0[1] + u[1] * o.width * 0.55)
                off = (-1 if k == 0 else 1) * t
                quad = [
                    (s0[0] + n[0] * (off - t / 2), s0[1] + n[1] * (off - t / 2)),
                    (s1[0] + n[0] * (off - t / 2), s1[1] + n[1] * (off - t / 2)),
                    (s1[0] + n[0] * (off + t / 2), s1[1] + n[1] * (off + t / 2)),
                    (s0[0] + n[0] * (off + t / 2), s0[1] + n[1] * (off + t / 2)),
                ]
                self.sheet.add(
                    Line([self.P(*p) for p in quad], self.pen("normal"), "A-DOOR", INK, None, True)
                )
                _ = p0
            return
        face = h * side
        leaves = [(a, b)] if o.operation != "double" else [(a, mid), (b, mid)]
        if o.operation != "double" and o.hinge == "end":
            leaves = [(b, a)]
        for hinge, other in leaves:
            r = math.dist(hinge, other)
            hp = (hinge[0] + n[0] * face, hinge[1] + n[1] * face)
            op = (other[0] + n[0] * face, other[1] + n[1] * face)
            leaf = (hp[0] + n[0] * side * r, hp[1] + n[1] * side * r)
            self.sheet.add(Line([self.P(*hp), self.P(*leaf)], self.pen("normal"), "A-DOOR", INK))
            a1 = math.degrees(math.atan2(leaf[1] - hp[1], leaf[0] - hp[0]))
            a2 = math.degrees(math.atan2(op[1] - hp[1], op[0] - hp[0]))
            start, end = sorted((a1, a2))
            if end - start > 180:
                start, end = end, start + 360
            self.sheet.add(
                Arc(self.P(*hp), r / self.scale, start, end, self.pen("thin"), "A-DOOR", INK)
            )
        if o.main_entrance:  # a solid triangle outside the main door, pointing in
            out = -side
            tip = (mid[0] + n[0] * out * (h + 120), mid[1] + n[1] * out * (h + 120))
            base = (
                mid[0] + n[0] * out * (h + 120 + 2.2 * self.scale),
                mid[1] + n[1] * out * (h + 120 + 2.2 * self.scale),
            )
            half = 1.1 * self.scale
            l1 = (base[0] + u[0] * half, base[1] + u[1] * half)
            l2 = (base[0] - u[0] * half, base[1] - u[1] * half)
            self.sheet.add(Area([[self.P(*tip), self.P(*l1), self.P(*l2)]], INK, "A-ANNO-SYMB"))

    # ---------------------------------------------------------------- stairs
    def stairs(self) -> None:
        for s in self.st.stairs:
            for i, f in enumerate(s.flights):
                r = box(f.x, f.y, f.x + f.w, f.y + f.h)
                self.sheet.add(
                    Line(
                        self.ring(r.exterior.coords),
                        self.pen("normal"),
                        "A-FLOR-STRS",
                        INK,
                        None,
                        True,
                    )
                )
                along_x = f.axis == "x"
                run = f.w if along_x else f.h
                n = max(1, f.risers - 1)
                step = run / n
                cut_at = 0.6 * run if i == 0 else -1
                for k in range(1, n):
                    d = k * step
                    above = (i == 0 and d > cut_at) or i > 0
                    pos = (f.x + d, f.y) if along_x else (f.x, f.y + d)
                    if f.up == -1:
                        pos = (f.x + f.w - d, f.y) if along_x else (f.x, f.y + f.h - d)
                    p1 = self.P(*pos)
                    p2 = self.P(pos[0], pos[1] + f.h) if along_x else self.P(pos[0] + f.w, pos[1])
                    dash = (self.s(1.2), self.s(0.8)) if above else None
                    self.sheet.add(Line([p1, p2], self.pen("thin"), "A-FLOR-STRS", INK, dash))
                if i == 0:  # cut line: a zig-zag across the flight where the plan cuts it
                    d = cut_at
                    if along_x:
                        pts = [
                            (f.x + d - 150, f.y),
                            (f.x + d, f.y + f.h * 0.45),
                            (f.x + d + 120, f.y + f.h * 0.55),
                            (f.x + d + 270, f.y + f.h),
                        ]
                    else:
                        pts = [
                            (f.x, f.y + d - 150),
                            (f.x + f.w * 0.45, f.y + d),
                            (f.x + f.w * 0.55, f.y + d + 120),
                            (f.x + f.w, f.y + d + 270),
                        ]
                    if f.up == -1:
                        pts = (
                            [(2 * f.x + f.w - x, y) for x, y in pts]
                            if along_x
                            else [(x, 2 * f.y + f.h - y) for x, y in pts]
                        )
                    self.sheet.add(
                        Line([self.P(*p) for p in pts], self.pen("normal"), "A-FLOR-STRS", INK)
                    )
            # walking line with arrow and UP
            pts = []
            for f in s.flights:
                c = (f.x + f.w / 2, f.y + f.h / 2)
                if f.axis == "x":
                    a, b = (f.x + 150, c[1]), (f.x + f.w - 150, c[1])
                else:
                    a, b = (c[0], f.y + 150), (c[0], f.y + f.h - 150)
                pts += [a, b] if f.up == 1 else [b, a]
            if len(pts) >= 2:
                self.sheet.add(
                    Line([self.P(*p) for p in pts], self.pen("thin"), "A-FLOR-STRS", INK)
                )
                (x1, y1), (x2, y2) = self.P(*pts[-2]), self.P(*pts[-1])
                ang = math.atan2(y2 - y1, x2 - x1)
                hl = self.s(1.6)
                head = [
                    (x2, y2),
                    (x2 - hl * math.cos(ang - 0.4), y2 - hl * math.sin(ang - 0.4)),
                    (x2 - hl * math.cos(ang + 0.4), y2 - hl * math.sin(ang + 0.4)),
                ]
                self.sheet.add(Area([head], INK, "A-FLOR-STRS"))
                sx, sy = self.P(*pts[0])
                self.text(
                    sx,
                    sy - self.s(1.2),
                    "UP",
                    self.txt("label"),
                    "A-FLOR-STRS",
                    bold=True,
                    mask=True,
                )
                self.labels_taken.append((sx - 3, sy - 4, sx + 3, sy))

    # ---------------------------------------------------------------- fixtures
    def _shapes(self, shapes, cx, cy, rot, layer, color, width=None) -> None:
        width = width or self.pen("thin")
        for sh in place(shapes, cx, cy, rot):
            if sh[0] == "line":
                self.sheet.add(Line([self.P(*p) for p in sh[1]], width, layer, color, None, sh[2]))
            elif sh[0] == "circle":
                self.sheet.add(Circle(self.P(*sh[1]), sh[2] / self.scale, width, layer, color))

    def fixtures(self) -> None:
        for f in self.st.fixtures:
            if f.furniture and not self.furniture:
                continue
            draw = BLOCKS.get(f.kind)
            if draw is None:
                continue
            layer = "A-FURN" if f.furniture else "A-FLOR-FIXT"
            color = GREY["furniture"] if f.furniture else INK
            width = self.pen("fine") if f.furniture else self.pen("thin")
            self._shapes(draw(f.w, f.d), f.x, f.y, f.rotation, layer, color, width)

    # ---------------------------------------------------------------- labels
    def text(
        self,
        x,
        y,
        text,
        size,
        layer,
        bold=False,
        anchor="middle",
        rotation=0.0,
        color=INK,
        mask=False,
    ) -> None:
        if mask:
            w = text_width(text, size, bold)
            x0 = x - w / 2 if anchor == "middle" else (x - w if anchor == "end" else x)
            pad = size * 0.25
            self.sheet.add(
                Area(
                    [
                        [
                            (x0 - pad, y - size * 0.85 - pad),
                            (x0 + w + pad, y - size * 0.85 - pad),
                            (x0 + w + pad, y + size * 0.3 + pad),
                            (x0 - pad, y + size * 0.3 + pad),
                        ]
                    ],
                    "#ffffff",
                    layer,
                )
            )
        self.sheet.add(Text(x, y, text, size, layer, bold, anchor, rotation, color))

    def block(self, cx, cy, lines, layer, mask=False, rotation=0.0) -> None:
        heights = [sz * 1.3 for _, sz, _ in lines]
        total = sum(heights)
        y = cy - total / 2
        for (t, sz, bold), hgt in zip(lines, heights, strict=True):
            y += hgt
            if rotation:
                self.sheet.add(
                    Text(cx + (y - cy) - hgt * 0.25, cy, t, sz, layer, bold, "middle", rotation)
                )
            else:
                self.text(
                    cx,
                    y - hgt * 0.25,
                    t,
                    sz,
                    layer,
                    bold,
                    mask=mask,
                    color=INK if bold else GREY["text_muted"],
                )

    def obstacles(self, room_id: str) -> list[tuple[float, float, float, float]]:
        out = list(self.labels_taken)
        for f in self.st.fixtures:
            if f.room != room_id or (f.furniture and not self.furniture):
                continue
            w, d = (f.d, f.w) if f.rotation in (90, 270) else (f.w, f.d)
            x0, y0 = self.P(f.x - w / 2, f.y - d / 2)
            x1, y1 = self.P(f.x + w / 2, f.y + d / 2)
            out.append((x0, y0, x1, y1))
        for o in self.st.openings:
            if o.kind != "door" or room_id not in o.rooms:
                continue
            g = self._opening_box(self.st.wall(o.wall), o).buffer(o.width)
            x0, y0 = self.P(g.bounds[0], g.bounds[1])
            x1, y1 = self.P(g.bounds[2], g.bounds[3])
            out.append((x0, y0, x1, y1))
        for s in self.st.stairs:
            if s.room == room_id:
                for f in s.flights:
                    x0, y0 = self.P(f.x, f.y)
                    x1, y1 = self.P(f.x + f.w, f.y + f.h)
                    out.append((x0, y0, x1, y1))
        return out

    def room_labels(self) -> None:
        walls_of: dict[str, list[Wall]] = {}
        for w in self.st.walls:
            for rid in w.rooms:
                walls_of.setdefault(rid, []).append(w)
        for r in self.st.rooms:
            xs, ys = [p[0] for p in r.polygon], [p[1] for p in r.polygon]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
            half = {"n": 0.0, "s": 0.0, "w": 0.0, "e": 0.0}
            for w in walls_of.get(r.id, []):
                if w.horizontal and w.a[1] == y0:
                    half["n"] = max(half["n"], w.thickness / 2)
                if w.horizontal and w.a[1] == y1:
                    half["s"] = max(half["s"], w.thickness / 2)
                if not w.horizontal and w.a[0] == x0:
                    half["w"] = max(half["w"], w.thickness / 2)
                if not w.horizontal and w.a[0] == x1:
                    half["e"] = max(half["e"], w.thickness / 2)
            nx0, ny0, nx1, ny1 = x0 + half["w"], y0 + half["n"], x1 - half["e"], y1 - half["s"]
            if r.type == "shaft":
                cx, cy = self.P((nx0 + nx1) / 2, (ny0 + ny1) / 2)
                self.text(
                    cx,
                    cy + self.txt("small") / 3,
                    "DUCT",
                    self.txt("small"),
                    "A-AREA-IDEN",
                    color=GREY["text_muted"],
                )
                continue
            dims = f"{fmt_len(nx1 - nx0, self.unit)} × {fmt_len(ny1 - ny0, self.unit)}"
            area = fmt_area(r.net_area_m2, self.unit)
            px0, py0 = self.P(nx0, ny0)
            px1, py1 = self.P(nx1, ny1)
            self.place_label(r.id, r.name.upper(), dims, area, (px0, py0, px1, py1))

    def place_label(self, room_id, name, dims, area, rect) -> None:
        px0, py0, px1, py1 = rect
        obstacles = self.obstacles(room_id)
        options = [
            [
                (name, self.txt("room"), True),
                (dims, self.txt("label"), False),
                (area, self.txt("label"), False),
            ],
            [
                (name, self.txt("label"), True),
                (dims, self.txt("small"), False),
                (area, self.txt("small"), False),
            ],
            [(name, self.txt("label"), True), (dims, self.txt("small"), False)],
            [(name, self.txt("small"), True)],
        ]
        cw, ch = px1 - px0, py1 - py0
        offsets = [
            (0, 0),
            (0, -0.25),
            (0, 0.25),
            (-0.25, 0),
            (0.25, 0),
            (-0.25, -0.25),
            (0.25, -0.25),
            (-0.25, 0.25),
            (0.25, 0.25),
            (0, -0.38),
            (0, 0.38),
        ]
        for rotate in (False, True):
            for lines in options:
                w = max(text_width(t, sz, b) for t, sz, b in lines) + self.s(1)
                h = sum(sz * 1.3 for _, sz, _ in lines) + self.s(0.6)
                if rotate:
                    w, h = h, w
                if w > cw or h > ch:
                    continue
                for fx, fy in offsets:
                    cx, cy = px0 + cw * (0.5 + fx), py0 + ch * (0.5 + fy)
                    bb = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
                    if bb[0] < px0 or bb[2] > px1 or bb[1] < py0 or bb[3] > py1:
                        continue
                    if any(_overlap(bb, o) for o in obstacles):
                        continue
                    self.block(cx, cy, lines, "A-AREA-IDEN", rotation=90.0 if rotate else 0.0)
                    self.labels_taken.append(bb)
                    return
        # no clear place: the smallest label at the centre, masked
        cx, cy = (px0 + px1) / 2, (py0 + py1) / 2
        self.block(cx, cy, options[-1], "A-AREA-IDEN", mask=True)

    # ---------------------------------------------------------------- dimensions
    def dimensions(self) -> None:
        site, st = self.b.site, self.st
        if not st.rooms:
            return
        t_ext = max((w.thickness for w in st.walls if w.kind == "exterior"), default=200)
        foot = unary_union([Polygon(r.polygon) for r in st.rooms]).buffer(
            t_ext / 2, join_style="mitre"
        )
        fx0, fy0, fx1, fy1 = foot.bounds
        for side in ("north", "south", "west", "east"):
            g = self.chain_gap(side)
            horizontal = side in ("north", "south")
            pts = self._facade_points(side, foot)
            overall = [fx0, fx1] if horizontal else [fy0, fy1]
            plot_pts = [0.0, float(site.width)] if horizontal else [0.0, float(site.depth)]
            if self.inside_chains:
                edge = {"north": fy0, "south": fy1, "west": fx0, "east": fx1}[side]
                sign = -1 if side in ("north", "west") else 1
                p_edge = self.P(edge, edge)[1 if horizontal else 0]
                base = [p_edge + sign * g * 1.0, p_edge + sign * g * 2.0]
                p_plot = (
                    self.P(0, 0)[1]
                    if side == "north"
                    else self.P(site.width, site.depth)[1]
                    if side == "south"
                    else self.P(0, 0)[0]
                    if side == "west"
                    else self.P(site.width, site.depth)[0]
                )
                plot_pos = p_plot + sign * g
            else:
                sign = -1 if side in ("north", "west") else 1
                p_plot = (
                    self.P(0, 0)[1]
                    if side == "north"
                    else self.P(site.width, site.depth)[1]
                    if side == "south"
                    else self.P(0, 0)[0]
                    if side == "west"
                    else self.P(site.width, site.depth)[0]
                )
                base = [p_plot + sign * g, p_plot + sign * 2 * g]
                plot_pos = p_plot + sign * 3 * g
            if len(pts) > 2:
                self.chain(pts, base[0], horizontal, side)
            self.chain(overall, base[1], horizontal, side)
            self.chain(plot_pts, plot_pos, horizontal, side)

    def chain_gap(self, side: str) -> float:
        """Spacing of the dimension chains on a side: two chains must fit in the setback
        strip between the building and the plot line."""
        g = self.s(CHAIN_GAP)
        if not self.inside_chains:
            return g
        site = self.b.site
        from app.modules.ai.floorplan.model.build import setback_box

        x0, y0, x1, y1 = setback_box(site)
        strip = {"north": y0, "south": site.depth - y1, "west": x0, "east": site.width - x1}[side]
        t_ext = max((w.thickness for w in self.st.walls if w.kind == "exterior"), default=200)
        boundary = 200 if any(e.kind == "boundary_wall" for e in site.elements) else 0
        paper = (strip - t_ext / 2 - boundary) / self.scale
        text_room = self.txt("label") * 1.4 + self.s(0.6)  # outer chain text, clear of the wall
        return max(self.s(3.0), min(g, (paper - text_room) / 2))

    def reserve_chain_bands(self) -> None:
        """Keep site labels off the dimension chains (they are drawn later)."""
        if not self.st.rooms:
            return
        t_ext = max((w.thickness for w in self.st.walls if w.kind == "exterior"), default=200)
        foot = unary_union([Polygon(r.polygon) for r in self.st.rooms]).buffer(
            t_ext / 2, join_style="mitre"
        )
        fx0, fy0, fx1, fy1 = foot.bounds
        (px0, py0), (px1, py1) = self.P(fx0, fy0), self.P(fx1, fy1)
        if self.inside_chains:
            gn, gs, gw, ge = (
                self.chain_gap(s) * 2 + self.s(2.5) for s in ("north", "south", "west", "east")
            )
            self.labels_taken += [
                (px0 - gw, py0 - gn, px1 + ge, py0),
                (px0 - gw, py1, px1 + ge, py1 + gs),
                (px0 - gw, py0, px0, py1),
                (px1, py0, px1 + ge, py1),
            ]

    def _facade_points(self, side: str, foot) -> list[float]:
        """Break points along a facade: its corners and the interior walls that meet it."""
        fx0, fy0, fx1, fy1 = foot.bounds
        horizontal = side in ("north", "south")
        pts = {fx0, fx1} if horizontal else {fy0, fy1}
        edge = {"north": fy0, "south": fy1, "west": fx0, "east": fx1}[side]
        for x, y in foot.exterior.coords:
            if horizontal and abs(y - edge) < 1:
                pts.add(x)
            if not horizontal and abs(x - edge) < 1:
                pts.add(y)
        t_ext = max((w.thickness for w in self.st.walls if w.kind == "exterior"), default=200)
        for w in self.st.walls:
            if w.kind == "exterior" or w.horizontal == horizontal:
                continue
            lo, hi = (
                (min(w.a[1], w.b[1]), max(w.a[1], w.b[1]))
                if horizontal
                else (min(w.a[0], w.b[0]), max(w.a[0], w.b[0]))
            )
            near = edge + (t_ext / 2 if side in ("north", "west") else -t_ext / 2)
            if lo - 1 <= near <= hi + 1:
                pts.add(w.a[0] if horizontal else w.a[1])
        return sorted(pts)

    def chain(self, pts: list[float], pos: float, horizontal: bool, side: str) -> None:
        pts = sorted(set(pts))
        if len(pts) < 2:
            return
        labels = chain_labels(pts, self.unit)
        ext = self.s(1.0)
        tick = self.s(1.2)
        paper = [self.P(p, 0)[0] if horizontal else self.P(0, p)[1] for p in pts]
        if horizontal:
            self.sheet.add(
                Line(
                    [(paper[0] - ext, pos), (paper[-1] + ext, pos)],
                    self.pen("fine"),
                    "A-ANNO-DIMS",
                    INK,
                )
            )
        else:
            self.sheet.add(
                Line(
                    [(pos, paper[0] - ext), (pos, paper[-1] + ext)],
                    self.pen("fine"),
                    "A-ANNO-DIMS",
                    INK,
                )
            )
        for p in paper:
            if horizontal:
                self.sheet.add(
                    Line(
                        [(p, pos - ext * 1.6), (p, pos + ext * 1.6)],
                        self.pen("fine"),
                        "A-ANNO-DIMS",
                        INK,
                    )
                )
                self.sheet.add(
                    Line(
                        [(p - tick / 2, pos + tick / 2), (p + tick / 2, pos - tick / 2)],
                        self.pen("medium"),
                        "A-ANNO-DIMS",
                        INK,
                    )
                )
            else:
                self.sheet.add(
                    Line(
                        [(pos - ext * 1.6, p), (pos + ext * 1.6, p)],
                        self.pen("fine"),
                        "A-ANNO-DIMS",
                        INK,
                    )
                )
                self.sheet.add(
                    Line(
                        [(pos - tick / 2, p + tick / 2), (pos + tick / 2, p - tick / 2)],
                        self.pen("medium"),
                        "A-ANNO-DIMS",
                        INK,
                    )
                )
        size = self.txt("label")
        for (a, b), label in zip(zip(paper, paper[1:], strict=False), labels, strict=True):
            w = text_width(label, size)
            mid = (a + b) / 2
            room = b - a
            if horizontal:
                y = pos - self.s(0.8)
                x = mid if w + self.s(0.8) <= room else b + w / 2 + self.s(0.8)
                self.sheet.add(Text(x, y, label, size, "A-ANNO-DIMS"))
            else:
                x = pos - self.s(0.8)
                y = mid if w + self.s(0.8) <= room else b + w / 2 + self.s(0.8)
                self.sheet.add(Text(x, y, label, size, "A-ANNO-DIMS", rotation=90.0))

    # ---------------------------------------------------------------- frame, title
    def frame(self) -> None:
        W, H = self.sheet.width, self.sheet.height
        f = self.s(FRAME_IN)
        self.sheet.add(
            Line(
                [(f, f), (W - f, f), (W - f, H - f), (f, H - f)],
                self.pen("wide"),
                "G-ANNO-TTLB",
                INK,
                None,
                True,
            )
        )

    def footer(self) -> None:
        x0, _, x1, y1 = self.draw_box
        y = self.sheet.height - self.s(FRAME_IN + FOOT_H) + self.s(9)
        title = self.b.meta.title.upper()
        tsize = self.txt("heading")
        self.sheet.add(Text(x0 + self.s(2), y, title, tsize, "G-ANNO-TTLB", True, "start"))
        tw = text_width(title, tsize, True)
        self.sheet.add(
            Line(
                [(x0 + self.s(2), y + self.s(1.2)), (x0 + self.s(2) + tw, y + self.s(1.2))],
                self.pen("medium"),
                "G-ANNO-TTLB",
                INK,
            )
        )
        sheet = "A1" if self.k == 2 else "A3"
        self.sheet.add(
            Text(
                x0 + self.s(2),
                y + self.s(5),
                f"SCALE 1:{self.scale} @ {sheet}",
                self.txt("label"),
                "G-ANNO-TTLB",
                False,
                "start",
            )
        )
        self.scale_bar(x1 - self.s(4), y - self.s(3))

    def scale_bar(self, right: float, y: float) -> None:
        """Alternating black and white boxes, 0 to a round length, ending at `right`."""
        if self.unit == "ft":
            unit_mm, step, n, unit_txt = 304.8, 5, 4, "FT"
        else:
            unit_mm, step, n, unit_txt = (
                1000.0,
                {50: 1, 75: 1, 100: 1, 125: 2, 150: 2, 200: 2}.get(self.scale, 5),
                5,
                "M",
            )
        seg = step * unit_mm / self.scale
        total = seg * n
        x = right - total - self.s(6)
        hgt = self.s(1.6)
        for i in range(n):
            xa = x + i * seg
            fill = INK if i % 2 == 0 else "#ffffff"
            self.sheet.add(
                Area(
                    [[(xa, y), (xa + seg, y), (xa + seg, y + hgt), (xa, y + hgt)]],
                    fill,
                    "G-ANNO-SCAL",
                    INK,
                    self.pen("fine"),
                )
            )
            self.sheet.add(
                Text(xa, y + hgt + self.s(2.6), str(i * step), self.txt("small"), "G-ANNO-SCAL")
            )
        self.sheet.add(
            Text(x + total, y + hgt + self.s(2.6), str(n * step), self.txt("small"), "G-ANNO-SCAL")
        )
        self.sheet.add(
            Text(
                x + total + self.s(2),
                y + hgt,
                unit_txt,
                self.txt("small"),
                "G-ANNO-SCAL",
                False,
                "start",
            )
        )

    def north_arrow(self, cx: float, cy: float, r: float) -> None:
        a = math.radians(self.b.site.north_deg)
        tip = (cx + r * math.sin(a), cy - r * math.cos(a))
        left = (
            cx - r * 0.45 * math.cos(a) - r * 0.55 * math.sin(a),
            cy - r * 0.45 * math.sin(a) + r * 0.55 * math.cos(a),
        )
        right = (
            cx + r * 0.45 * math.cos(a) - r * 0.55 * math.sin(a),
            cy + r * 0.45 * math.sin(a) + r * 0.55 * math.cos(a),
        )
        self.sheet.add(Circle((cx, cy), r, self.pen("normal"), "G-ANNO-NRTH"))
        self.sheet.add(Area([[tip, (cx, cy), left]], INK, "G-ANNO-NRTH"))
        self.sheet.add(
            Area([[tip, right, (cx, cy)]], "#ffffff", "G-ANNO-NRTH", INK, self.pen("thin"))
        )
        self.sheet.add(
            Text(tip[0], tip[1] - self.s(1.5), "N", self.txt("label"), "G-ANNO-NRTH", True)
        )

    def title_strip(self) -> None:
        b, a = self.b, self.b.areas
        W, H = self.sheet.width, self.sheet.height
        x0 = W - self.s(FRAME_IN + STRIP_W)
        x1 = W - self.s(FRAME_IN)
        top, bottom = self.s(FRAME_IN), H - self.s(FRAME_IN)
        pad = self.s(3)

        def rule(y: float) -> None:
            self.sheet.add(Line([(x0, y), (x1, y)], self.pen("medium"), "G-ANNO-TTLB", INK))

        self.sheet.add(Line([(x0, top), (x0, bottom)], self.pen("wide"), "G-ANNO-TTLB", INK))
        small, label = self.txt("small"), self.txt("label")
        # logo placeholder
        y = top + pad
        self.sheet.add(
            Line(
                [
                    (x0 + pad, y),
                    (x1 - pad, y),
                    (x1 - pad, y + self.s(16)),
                    (x0 + pad, y + self.s(16)),
                ],
                self.pen("thin"),
                "G-ANNO-TTLB",
                GREY["rule"],
                (self.s(1.5), self.s(1)),
                True,
            )
        )
        self.sheet.add(
            Text(
                (x0 + x1) / 2,
                y + self.s(9.5),
                "LOGO",
                label,
                "G-ANNO-TTLB",
                False,
                "middle",
                0.0,
                GREY["rule"],
            )
        )
        y += self.s(19)
        rule(y)
        fields = [
            ("PROJECT", b.meta.project or "-"),
            ("CLIENT", b.meta.client or "-"),
            ("DRAWING", b.meta.title),
            ("DRAWING NO.", f"{b.meta.drawing_number}   VERSION {b.meta.version}"),
            ("SCALE", f"1:{self.scale} @ {'A1' if self.k == 2 else 'A3'}"),
            ("DATE", b.meta.date),
            ("SETBACKS", _setbacks_text(b)),
        ]
        for name, value in fields:
            y += self.s(4.2)
            self.sheet.add(
                Text(
                    x0 + pad, y, name, small, "G-ANNO-TTLB", False, "start", 0.0, GREY["text_muted"]
                )
            )
            self.sheet.add(
                Text(
                    x0 + self.s(25),
                    y,
                    _fit(value, label, x1 - pad - x0 - self.s(25)),
                    label,
                    "G-ANNO-TTLB",
                    True,
                    "start",
                )
            )
        y += self.s(3)
        rule(y)
        # north arrow and scale note
        self.north_arrow(x0 + self.s(14), y + self.s(10), self.s(6))
        self.sheet.add(
            Text(x0 + self.s(26), y + self.s(8), "NORTH", small, "G-ANNO-TTLB", True, "start")
        )
        self.sheet.add(
            Text(
                x0 + self.s(26),
                y + self.s(12),
                f"DIMENSIONS IN {_unit_name(self.unit)}",
                small,
                "G-ANNO-TTLB",
                False,
                "start",
            )
        )
        y += self.s(20)
        rule(y)
        # revisions
        y += self.s(4)
        self.sheet.add(Text(x0 + pad, y, "REVISIONS", label, "G-ANNO-TTLB", True, "start"))
        cols = (x0 + pad, x0 + self.s(13), x0 + self.s(32))
        y += self.s(3.6)
        for c, h in zip(cols, ("REV", "DATE", "DESCRIPTION"), strict=True):
            self.sheet.add(
                Text(c, y, h, small, "G-ANNO-TTLB", True, "start", 0.0, GREY["text_muted"])
            )
        for rev in b.meta.revisions[-5:]:
            y += self.s(3.2)
            self.sheet.add(Text(cols[0], y, rev.rev, small, "G-ANNO-TTLB", False, "start"))
            self.sheet.add(Text(cols[1], y, rev.date, small, "G-ANNO-TTLB", False, "start"))
            self.sheet.add(
                Text(
                    cols[2],
                    y,
                    _fit(rev.description, small, x1 - pad - cols[2]),
                    small,
                    "G-ANNO-TTLB",
                    False,
                    "start",
                )
            )
        y += self.s(3)
        rule(y)
        # area schedule
        y += self.s(4)
        self.sheet.add(Text(x0 + pad, y, "AREA SCHEDULE", label, "G-ANNO-TTLB", True, "start"))
        y += self.s(3.6)
        self.sheet.add(
            Text(x0 + pad, y, "ROOM", small, "G-ANNO-TTLB", True, "start", 0.0, GREY["text_muted"])
        )
        self.sheet.add(
            Text(
                x1 - self.s(22),
                y,
                "NET m²",
                small,
                "G-ANNO-TTLB",
                True,
                "end",
                0.0,
                GREY["text_muted"],
            )
        )
        self.sheet.add(
            Text(
                x1 - pad, y, "GROSS m²", small, "G-ANNO-TTLB", True, "end", 0.0, GREY["text_muted"]
            )
        )
        rooms = [r for r in self.st.rooms if r.type != "shaft"]
        for r in rooms:
            y += self.s(2.9)
            self.sheet.add(
                Text(
                    x0 + pad,
                    y,
                    _fit(r.name.upper(), small, self.s(50)),
                    small,
                    "G-ANNO-TTLB",
                    False,
                    "start",
                )
            )
            self.sheet.add(
                Text(x1 - self.s(22), y, f"{r.net_area_m2:.1f}", small, "G-ANNO-TTLB", False, "end")
            )
            self.sheet.add(
                Text(x1 - pad, y, f"{r.gross_area_m2:.1f}", small, "G-ANNO-TTLB", False, "end")
            )
        y += self.s(1.2)
        self.sheet.add(Line([(x0 + pad, y), (x1 - pad, y)], self.pen("fine"), "G-ANNO-TTLB", INK))
        y += self.s(3)
        self.sheet.add(Text(x0 + pad, y, "BUILT-UP", small, "G-ANNO-TTLB", True, "start"))
        self.sheet.add(
            Text(x1 - self.s(22), y, f"{a.built_up_net_m2:.1f}", small, "G-ANNO-TTLB", True, "end")
        )
        self.sheet.add(Text(x1 - pad, y, f"{a.built_up_m2:.1f}", small, "G-ANNO-TTLB", True, "end"))
        for line in area_lines(a, self.unit):
            y += self.s(3.2)
            self.sheet.add(
                Text(
                    x0 + pad,
                    y,
                    _fit(line, small, x1 - x0 - 2 * pad),
                    small,
                    "G-ANNO-TTLB",
                    False,
                    "start",
                )
            )
        y += self.s(2.5)
        rule(y)
        # legend
        y += self.s(4)
        self.sheet.add(Text(x0 + pad, y, "LEGEND", label, "G-ANNO-TTLB", True, "start"))
        self.legend(x0 + pad, y + self.s(2), x1 - pad)
        # disclaimer at the bottom
        yb = bottom - self.s(9)
        rule(yb)
        self.sheet.add(
            Text(
                (x0 + x1) / 2,
                yb + self.s(4),
                "FOR DESIGN PURPOSES ONLY,",
                label,
                "G-ANNO-TTLB",
                True,
            )
        )
        self.sheet.add(
            Text(
                (x0 + x1) / 2, yb + self.s(7.2), "NOT FOR CONSTRUCTION", label, "G-ANNO-TTLB", True
            )
        )

    def legend(self, x: float, y: float, right: float) -> None:
        small = self.txt("small")
        items = [
            ("wall_ext", "EXTERIOR WALL (200 MM)"),
            ("wall_int", "INTERIOR WALL (100-150 MM)"),
            ("door", "HINGED DOOR"),
            ("sliding", "SLIDING DOOR"),
            ("window", "WINDOW"),
            ("lawn", "LAWN / GARDEN"),
            ("water", "WATER"),
            ("paving", "PAVING"),
            ("setback", "SETBACK LINE"),
            ("plot", "PLOT BOUNDARY"),
        ]
        col_w = (right - x) / 2
        for i, (kind, label) in enumerate(items):
            cx = x + (i % 2) * col_w
            cy = y + (i // 2) * self.s(4.6) + self.s(1.5)
            sw, sh = self.s(7), self.s(2.4)
            box_pts = [(cx, cy), (cx + sw, cy), (cx + sw, cy + sh), (cx, cy + sh)]
            if kind == "wall_ext":
                self.sheet.add(
                    Area([box_pts], GREY["wall_ext"], "G-ANNO-LEGN", INK, self.pen("normal"))
                )
            elif kind == "wall_int":
                self.sheet.add(
                    Area([box_pts], GREY["wall_int"], "G-ANNO-LEGN", INK, self.pen("thin"))
                )
            elif kind in ("lawn", "water", "paving"):
                poly = Polygon(box_pts)
                spec = HATCH[kind]
                if "grid" in spec:
                    for ang in (0, 90):
                        self._hatch_lines(
                            poly, ang, self.s(1.2), spec["color"], None, "G-ANNO-LEGN"
                        )
                else:
                    self._hatch_lines(
                        poly, spec["angle"], self.s(0.8), spec["color"], None, "G-ANNO-LEGN"
                    )
                self.sheet.add(
                    Line(box_pts, self.pen("fine"), "G-ANNO-LEGN", GREY["rule"], None, True)
                )
            elif kind == "door":
                self.sheet.add(
                    Line([(cx, cy + sh), (cx, cy)], self.pen("normal"), "G-ANNO-LEGN", INK)
                )
                self.sheet.add(Arc((cx, cy + sh), sh, -90, 0, self.pen("thin"), "G-ANNO-LEGN", INK))
            elif kind == "sliding":
                self.sheet.add(
                    Line(
                        [(cx, cy + sh * 0.35), (cx + sw * 0.6, cy + sh * 0.35)],
                        self.pen("normal"),
                        "G-ANNO-LEGN",
                        INK,
                    )
                )
                self.sheet.add(
                    Line(
                        [(cx + sw * 0.4, cy + sh * 0.65), (cx + sw, cy + sh * 0.65)],
                        self.pen("normal"),
                        "G-ANNO-LEGN",
                        INK,
                    )
                )
            elif kind == "window":
                for f in (0.1, 0.4, 0.6, 0.9):
                    self.sheet.add(
                        Line(
                            [(cx, cy + sh * f), (cx + sw, cy + sh * f)],
                            self.pen("thin"),
                            "G-ANNO-LEGN",
                            INK,
                        )
                    )
            elif kind == "setback":
                self.sheet.add(
                    Line(
                        [(cx, cy + sh / 2), (cx + sw, cy + sh / 2)],
                        self.pen("thin"),
                        "G-ANNO-LEGN",
                        GREY["text_muted"],
                        (self.s(1.2), self.s(0.6)),
                    )
                )
            else:
                self.sheet.add(
                    Line(
                        [(cx, cy + sh / 2), (cx + sw, cy + sh / 2)],
                        self.pen("normal"),
                        "G-ANNO-LEGN",
                        INK,
                        (self.s(2.5), self.s(0.5), self.s(0.5), self.s(0.5)),
                    )
                )
            self.sheet.add(
                Text(
                    cx + sw + self.s(1.5),
                    cy + sh * 0.85,
                    label,
                    small * 0.92,
                    "G-ANNO-LEGN",
                    False,
                    "start",
                )
            )

    def compose(self) -> Sheet:
        self.choose_scale()
        self.frame()
        self.reserve_chain_bands()
        self.site()
        self.fixtures()
        self.stairs()
        self.walls()
        self.openings()
        self.room_labels()
        self.dimensions()
        self.footer()
        self.title_strip()
        return self.sheet


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _fit(text: str, size: float, width: float) -> str:
    if text_width(text, size) <= width:
        return text
    while text and text_width(text + "…", size) > width:
        text = text[:-1]
    return text + "…"


def _setbacks_text(b: Building) -> str:
    sb = b.site.setbacks
    if not (sb.front or sb.rear or sb.left or sb.right):
        return "NONE"
    side = (
        f"{sb.left / 1000:g}" if sb.left == sb.right else f"{sb.left / 1000:g}/{sb.right / 1000:g}"
    )
    return f"{sb.front / 1000:g} M FRONT, {side} M SIDES, {sb.rear / 1000:g} M REAR"


def _unit_name(unit: str) -> str:
    return {"ft": "FEET AND INCHES", "m": "METRES", "cm": "CENTIMETRES", "mm": "MILLIMETRES"}.get(
        unit, unit.upper()
    )


def compose_sheet(
    b: Building, *, sheet: str | None = None, furniture: bool | None = None, unit: str | None = None
) -> Sheet:
    from app.modules.ai.floorplan.settings import get_settings

    s = get_settings()
    sheet = (sheet or b.meta.sheet or s.sheet or "A3").upper()
    furniture = s.furniture if furniture is None else furniture
    return _Composer(b, "A1" if sheet == "A1" else "A3", furniture, unit).compose()


__all__ = ["compose_sheet", "chain_labels", "fmt_len", "text_width", "MultiLineString"]
