"""Building -> presentation sheet: the same plan in muted colour, for clients (A2).

A second view of the same building model. Everything the engineering drawing has is kept
unchanged (walls, doors and windows, dimension chains, room names, sizes and areas, the
title block, north arrow and scale bar, the Jost text sizes); this view only adds colour:

- floors filled by room type in warm greys and beiges (never bright);
- gardens, lawns and verandahs dull green, pools and water dull blue, paving soft stone,
  each a flat fill instead of a hatch;
- minimal plan furniture drawn solid (a light fill under the engineering blocks): beds,
  WC and basin, sofa set, dining table and chairs, kitchen counters, plus a puja unit in a
  puja or prayer room, a few plants in gardens and loungers beside the pool;
- a colour legend.

It subclasses the engineering composer, so the engineering drawing itself is never touched
(tests/floorplan/test_fp_engineering_snapshot.py proves its files are byte for byte the same).
"""

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from app.modules.ai.floorplan.drawing.blocks import BLOCKS, place
from app.modules.ai.floorplan.drawing.compose import _Composer
from app.modules.ai.floorplan.drawing.display import Area, Circle, Line, Sheet, Text
from app.modules.ai.floorplan.drawing.style import GREY, INK
from app.modules.ai.floorplan.model.building import Building

# floor colours by room type: warm greys and beiges, light enough for black text
FLOOR = {
    "living": "#ece3d3",
    "family_hall": "#ece3d3",
    "majlis": "#eadfcc",
    "dining": "#ede4d4",
    "master_bedroom": "#e7ddd0",
    "bedroom": "#e8dfd3",
    "guest_bedroom": "#e8dfd3",
    "study": "#e6dfd4",
    "kitchen": "#e4e0d8",
    "utility": "#e2dfd9",
    "store": "#e0ddd7",
    "maid_room": "#e3ded5",
    "driver_room": "#e3ded5",
    "bath": "#dfe2e0",
    "toilet": "#dfe2e0",
    "dress": "#e9e1d6",
    "lobby": "#ebe6dd",
    "passage": "#ebe6dd",
    "foyer": "#ebe5da",
    "stair": "#e2ddd4",
    "puja": "#eee4cf",
    "prayer": "#eee4cf",
    "gym": "#e3e0da",
    "bar": "#e8ded0",
    "shaft": "#dcd8d1",
}
FLOOR_OTHER = "#e9e3d9"
SITE = {
    "garden": "#c8d1bb",  # dull sage green
    "lawn": "#c3cfb5",
    "deck": "#cfd6c3",  # verandah / sit-out: green as asked, a shade lighter
    "balcony": "#d9d4ca",
    "courtyard": "#e2ddd2",
    "paving": "#e6e1d7",  # soft stone
    "coping": "#ddd6c9",
    "parking": "#dedad2",
    "driveway": "#dedad2",
    "dock": "#d6d2ca",
}
WATER = "#b5c7cf"  # dull blue
WATER_EDGE = "#8fa7b2"
FURN_FILL = "#faf8f4"
FURN_LINE = "#6e675d"
PLANT_FILL = "#a9b79a"
PLANT_LINE = "#7f8f72"
SITE_KIND_COLOUR = {"pool": "coping"}


class _Presenter(_Composer):
    """The engineering composer with colour: floors, site fills, solid furniture."""

    # ------------------------------------------------------------ floors
    def floors(self) -> None:
        for r in self.st.rooms:
            colour = FLOOR.get(r.type, FLOOR_OTHER)
            self.add_poly(Polygon(r.polygon), colour, "A-FLOR-PATT")

    # ------------------------------------------------------------ site
    def hatch(self, geom_mm, kind: str, layer: str) -> None:
        """Flat muted fills instead of the engineering hatches."""
        if kind == "water":
            self.add_poly(geom_mm, WATER, layer, WATER_EDGE, self.pen("thin"))
            return
        self.add_poly(geom_mm, SITE.get(kind, SITE["paving"]), layer)

    def site(self) -> None:
        super().site()
        self.site_extras()

    def site_extras(self) -> None:
        """A few plants in gardens and lawns, loungers beside the pool."""
        footprint = (
            unary_union([Polygon(r.polygon) for r in self.st.rooms]).buffer(100)
            if self.st.rooms
            else Polygon()
        )
        for e in self.b.site.elements:
            poly = Polygon(e.polygon).difference(footprint)
            if poly.is_empty:
                continue
            if e.kind in ("garden", "lawn"):
                self._plants(poly)
            elif e.kind == "pool" and e.water:
                self._loungers(poly, Polygon(e.water))

    def _plants(self, poly) -> None:
        big = poly.buffer(-1900)
        if not big.is_empty:  # one tree where it fits whole and clear of the labels
            spot = self._clear_spot(big, 1800)
            if spot:
                self._draw(
                    BLOCKS["tree"](3600, 3600), *spot, "L-PLNT-TREE", PLANT_LINE, PLANT_FILL
                )
        core = poly.buffer(-700)
        if core.is_empty:
            return
        minx, miny, maxx, maxy = core.bounds
        spots = [(minx, miny), (maxx, miny), (minx, maxy), (maxx, maxy)]
        placed = 0
        for x, y in spots:
            if placed >= 3:
                break
            if not core.buffer(1).contains(box(x - 1, y - 1, x + 1, y + 1)):
                continue
            if self._on_label(x, y, 450):
                continue
            r = 450
            c = self.P(x, y)
            self.sheet.add(
                Circle(c, r / self.scale, self.pen("thin"), "L-PLNT", PLANT_LINE, PLANT_FILL)
            )
            self.sheet.add(
                Circle(c, r * 0.45 / self.scale, self.pen("fine"), "L-PLNT", PLANT_LINE, None)
            )
            placed += 1

    def _on_label(self, x: float, y: float, r: float) -> bool:
        x0, y0 = self.P(x - r, y - r)
        x1, y1 = self.P(x + r, y + r)
        return any(
            x0 < o[2] and o[0] < x1 and y0 < o[3] and o[1] < y1 for o in self.labels_taken
        )

    def _clear_spot(self, region, r: float):
        """A point of `region` (mm) whose circle of radius r misses every label."""
        minx, miny, maxx, maxy = region.bounds
        c = region.representative_point()
        cands = [(c.x, c.y)] + [
            (minx + (maxx - minx) * i / 4, miny + (maxy - miny) * j / 4)
            for i in range(5)
            for j in range(5)
        ]
        for x, y in cands:
            if region.buffer(1).contains(box(x - 1, y - 1, x + 1, y + 1)) and not self._on_label(
                x, y, r
            ):
                return x, y
        return None

    def _loungers(self, deck, water) -> None:
        """Two loungers on the widest strip of paving along the water."""
        wx0, wy0, wx1, wy1 = water.bounds
        options = []
        for side in ("n", "s", "w", "e"):
            if side == "n":
                strip = box(wx0, wy0 - 2400, wx1, wy0)
            elif side == "s":
                strip = box(wx0, wy1, wx1, wy1 + 2400)
            elif side == "w":
                strip = box(wx0 - 2400, wy0, wx0, wy1)
            else:
                strip = box(wx1, wy0, wx1 + 2400, wy1)
            free = strip.intersection(deck)
            options.append((free.area, side, free))
        area, side, free = max(options, key=lambda t: t[0])
        if area <= 0 or free.is_empty:
            return
        fx0, fy0, fx1, fy1 = free.bounds
        lw, ld = 700, 1900  # a lounger, mm
        if side in ("n", "s"):
            if fy1 - fy0 < ld + 200:
                return
            y = fy0 + (fy1 - fy0) / 2
            xs = [fx0 + (fx1 - fx0) * f for f in (0.3, 0.55)]
            pts = [(x, y, 0) for x in xs]
        else:
            if fx1 - fx0 < ld + 200:
                return
            x = fx0 + (fx1 - fx0) / 2
            ys = [fy0 + (fy1 - fy0) * f for f in (0.3, 0.55)]
            pts = [(x, y, 90) for y in ys]
        for cx, cy, rot in pts:
            w, d = (lw, ld) if rot == 0 else (ld, lw)
            rect = box(cx - w / 2, cy - d / 2, cx + w / 2, cy + d / 2)
            if not free.buffer(1).contains(rect):
                continue
            self.add_poly(rect, FURN_FILL, "L-SITE-FURN", FURN_LINE, self.pen("thin"))
            head = (
                box(cx - w / 2, cy - d / 2, cx + w / 2, cy - d / 2 + 450)
                if rot == 0
                else box(cx - w / 2, cy - d / 2, cx - w / 2 + 450, cy + d / 2)
            )
            self.add_poly(head, None, "L-SITE-FURN", FURN_LINE, self.pen("fine"))

    # ------------------------------------------------------------ furniture
    def _shapes(self, shapes, cx, cy, rot, layer, color, width=None) -> None:
        """Furniture and fixtures drawn solid: a light fill under each closed outline.
        The engineering garden tree (placed without checking that it fits) is left out;
        site_extras plants only what fits inside the garden."""
        if layer == "L-PLNT":
            return
        if layer not in ("A-FURN", "A-FLOR-FIXT"):
            super()._shapes(shapes, cx, cy, rot, layer, color, width)
            return
        self._draw(shapes, cx, cy, layer, FURN_LINE, FURN_FILL, width, rot)

    def _draw(self, shapes, cx, cy, layer, line, fill, width=None, rot=0) -> None:
        width = width or self.pen("thin")
        for sh in place(shapes, cx, cy, rot):
            if sh[0] == "line":
                pts = [self.P(*p) for p in sh[1]]
                if sh[2] and len(pts) >= 3:
                    self.sheet.add(Area([pts], fill, layer, line, width))
                else:
                    self.sheet.add(Line(pts, width, layer, line, None, sh[2]))
            elif sh[0] == "circle":
                self.sheet.add(Circle(self.P(*sh[1]), sh[2] / self.scale, width, layer, line, fill))

    def fixtures(self) -> None:
        super().fixtures()
        self.puja_units()

    def puja_units(self) -> None:
        """A puja unit (altar with its lamp) against the wall facing the door, in puja and
        prayer rooms and rooms named PUJA / POOJA / MANDIR."""
        for r in self.st.rooms:
            name = (r.name or "").upper()
            if r.type not in ("puja", "prayer") and not any(
                k in name for k in ("PUJA", "POOJA", "MANDIR", "PRAYER")
            ):
                continue
            if r.type == "prayer" and "PUJA" not in name:
                continue  # a prayer room (salah) stays empty: a rug is not drawn
            xs, ys = [p[0] for p in r.polygon], [p[1] for p in r.polygon]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
            w = min(1200.0, (x1 - x0) * 0.6)
            d = min(450.0, (y1 - y0) * 0.3)
            if w < 400 or d < 250:
                continue
            cx, top = (x0 + x1) / 2, y0 + 150 + d / 2
            unit = box(cx - w / 2, top - d / 2, cx + w / 2, top + d / 2)
            self.add_poly(unit, "#e9dcc0", "A-FURN", FURN_LINE, self.pen("thin"))
            lamp = self.P(cx, top)
            self.sheet.add(
                Circle(lamp, 90 / self.scale, self.pen("fine"), "A-FURN", FURN_LINE, "#d6c9a8")
            )

    # ------------------------------------------------------------ labels
    def block(self, cx, cy, lines, layer, mask=False, rotation=0.0) -> None:
        # on flat colour fills the labels read without a white box behind them
        super().block(cx, cy, lines, layer, mask=mask and layer != "L-SITE-IDEN", rotation=rotation)

    # ------------------------------------------------------------ legend
    def legend(self, x: float, y: float, right: float) -> None:
        small = self.txt("small")
        items = [
            ("area", GREY["wall_ext"], "EXTERIOR WALL (200 MM)"),
            ("area", GREY["wall_int"], "INTERIOR WALL (100-150 MM)"),
            ("area", FLOOR["living"], "LIVING / DINING"),
            ("area", FLOOR["bedroom"], "BEDROOMS"),
            ("area", FLOOR["kitchen"], "KITCHEN / SERVICE"),
            ("area", FLOOR["bath"], "BATHROOMS"),
            ("area", SITE["garden"], "GARDEN / LAWN / VERANDAH"),
            ("area", WATER, "WATER"),
            ("area", SITE["paving"], "PAVING"),
            ("plot", None, "PLOT BOUNDARY"),
        ]
        col_w = (right - x) / 2
        for i, (kind, colour, label) in enumerate(items):
            cx = x + (i % 2) * col_w
            cy = y + (i // 2) * self.s(4.6) + self.s(1.5)
            sw, sh = self.s(7), self.s(2.4)
            pts = [(cx, cy), (cx + sw, cy), (cx + sw, cy + sh), (cx, cy + sh)]
            if kind == "area":
                self.sheet.add(Area([pts], colour, "G-ANNO-LEGN", INK, self.pen("fine")))
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
                Text(cx + sw + self.s(1.5), cy + sh * 0.85, label, small * 0.92, "G-ANNO-LEGN",
                     False, "start")
            )

    def compose(self) -> Sheet:
        self.choose_scale()
        self.frame()
        self.reserve_chain_bands()
        self.floors()
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


def compose_presentation(
    b: Building, *, sheet: str | None = None, furniture: bool | None = None, unit: str | None = None
) -> Sheet:
    """The presentation view of a building (always with its minimal furniture unless
    `furniture` is False)."""
    from app.modules.ai.floorplan.settings import get_settings

    s = get_settings()
    sheet = (sheet or b.meta.sheet or s.sheet or "A3").upper()
    furniture = True if furniture is None else furniture
    return _Presenter(b, "A1" if sheet == "A1" else "A3", furniture, unit).compose()

