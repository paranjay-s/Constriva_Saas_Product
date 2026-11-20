"""DXF from the building model (ezdxf): millimetres, AIA / US National CAD Standard layers.

Model space holds the plan at 1:1 in mm ($INSUNITS = 4, y up: Y = plot depth - y).
A paper-space layout "A3" (or "A1") holds the title block and a viewport at the sheet's
scale, so the file plots like the PDF.

    A-WALL-EXTR / A-WALL-INTR   cut wall outlines (exterior 0.70 mm, interior 0.50 mm)
    A-WALL-PATT                 solid poche hatches of the walls
    A-DOOR                      door blocks (leaf + swing arc, sliding panels)
    A-GLAZ                      window blocks (frame + glazing)
    A-FLOR-STRS                 stair treads, walking line, UP
    A-FLOR-FIXT / A-FURN        fixture and furniture blocks (WC_400x700, BED_DOUBLE_...)
    A-AREA-IDEN                 room name, size and area
    A-ANNO-DIMS                 DIMENSION entities (chains on four sides)
    L-SITE-*                    site areas with HATCH (lawn, water, paving), boundary wall
    C-PROP / C-PROP-SETB        plot boundary (phantom), setback line (dashed)
    G-ANNO-TTLB                 title block in paper space
"""

import io
import math

import ezdxf
from ezdxf import colors, units
from ezdxf.enums import TextEntityAlignment
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from app.modules.ai.floorplan.drawing.blocks import BLOCKS
from app.modules.ai.floorplan.drawing.compose import _Composer, chain_labels, fmt_area, fmt_len
from app.modules.ai.floorplan.model.areas import area_lines
from app.modules.ai.floorplan.model.building import Building, Opening, Wall
from app.modules.ai.floorplan.model.planto3d import _wall_rect

# name: (ACI colour, lineweight in 1/100 mm, linetype)
LAYERS: dict[str, tuple[int, int, str]] = {
    "A-WALL-EXTR": (7, 70, "Continuous"),
    "A-WALL-INTR": (7, 50, "Continuous"),
    "A-WALL-PATT": (8, 13, "Continuous"),
    "A-DOOR": (7, 25, "Continuous"),
    "A-GLAZ": (7, 25, "Continuous"),
    "A-FLOR-STRS": (7, 25, "Continuous"),
    "A-FLOR-FIXT": (7, 18, "Continuous"),
    "A-FURN": (8, 13, "Continuous"),
    "A-AREA-IDEN": (7, 18, "Continuous"),
    "A-ANNO-DIMS": (7, 13, "Continuous"),
    "A-ANNO-SYMB": (7, 25, "Continuous"),
    "L-SITE": (8, 18, "Continuous"),
    "L-SITE-HATCH": (8, 9, "Continuous"),
    "L-SITE-WALL": (7, 25, "Continuous"),
    "C-PROP": (7, 50, "PHANTOM"),
    "C-PROP-SETB": (8, 18, "DASHED"),
    "G-ANNO-TTLB": (7, 35, "Continuous"),
}
HATCH_RGB = {
    "lawn": (169, 187, 155),
    "garden": (169, 187, 155),
    "water": (147, 179, 200),
    "paving": (203, 198, 189),
    "parking": (203, 198, 189),
    "deck": (201, 187, 163),
}
HATCH_PATTERN = {
    "lawn": ("GRASS", 30.0),
    "garden": ("GRASS", 40.0),
    "water": ("AR-RROOF", 15.0),
    "paving": ("NET", 400.0),
    "parking": ("NET", 600.0),
    "deck": ("LINE", 150.0),
}


class _Dxf:
    def __init__(self, b: Building, sheet: str | None, furniture: bool | None) -> None:
        self.b = b
        self.st = b.storeys[0]
        self.D = b.site.depth
        self.doc = ezdxf.new("R2018", setup=True)
        self.doc.units = units.MM
        self.doc.header["$MEASUREMENT"] = 1
        self.doc.header["$LUNITS"] = 2
        self.msp = self.doc.modelspace()
        for name, (aci, lw, lt) in LAYERS.items():
            self.doc.layers.add(name, color=aci, lineweight=lw, linetype=lt)
        self.blocks: set[str] = set()
        from app.modules.ai.floorplan.drawing.compose import compose_sheet

        self.sheet = compose_sheet(b, sheet=sheet, furniture=furniture)
        self.furniture = any(it.layer == "A-FURN" for it in self.sheet.items) or not any(
            f.furniture for f in self.st.fixtures
        )
        self.scale = self.sheet.scale
        self.unit = b.meta.unit_display
        style = self.doc.styles.new("PLAN", dxfattribs={"font": "Jost-Regular.ttf"})
        style.dxf.height = 0
        self.text_h = 2.5 * self.scale  # 2.5 mm on paper
        self.small_h = 1.8 * self.scale

    def Y(self, y: float) -> float:
        return self.D - y

    def pt(self, x: float, y: float) -> tuple[float, float]:
        return (x, self.D - y)

    def poly(self, geom, layer: str, hatch: str | None = None, solid_rgb=None) -> None:
        polys = [geom] if geom.geom_type == "Polygon" else list(getattr(geom, "geoms", []))
        for p in polys:
            if p.geom_type != "Polygon" or p.is_empty:
                continue
            rings = [list(p.exterior.coords)] + [list(i.coords) for i in p.interiors]
            for ring in rings:
                self.msp.add_lwpolyline(
                    [self.pt(x, y) for x, y in ring[:-1]], close=True, dxfattribs={"layer": layer}
                )
            if hatch or solid_rgb:
                attribs = {"layer": "A-WALL-PATT" if solid_rgb else "L-SITE-HATCH"}
                h = self.msp.add_hatch(dxfattribs=attribs)
                if solid_rgb:
                    h.rgb = solid_rgb
                else:
                    name, scale = HATCH_PATTERN[hatch]
                    h.set_pattern_fill(name, scale=scale)
                    h.rgb = HATCH_RGB[hatch]
                h.paths.add_polyline_path(
                    [self.pt(x, y) for x, y in ring_of(p.exterior)], is_closed=True, flags=1
                )
                for i in p.interiors:
                    h.paths.add_polyline_path(
                        [self.pt(x, y) for x, y in ring_of(i)], is_closed=True, flags=16
                    )

    # ------------------------------------------------------------------ blocks
    def block(self, name: str, shapes, layer: str) -> str:
        if name not in self.blocks:
            blk = self.doc.blocks.new(name=name)
            for s in shapes:
                if s[0] == "line":
                    pts = [(x, -y) for x, y in s[1]]
                    blk.add_lwpolyline(pts, close=s[2], dxfattribs={"layer": "0"})
                elif s[0] == "circle":
                    blk.add_circle((s[1][0], -s[1][1]), s[2], dxfattribs={"layer": "0"})
            self.blocks.add(name)
        return name

    def fixtures(self) -> None:
        for f in self.st.fixtures:
            if f.furniture and not self.furniture:
                continue
            draw = BLOCKS.get(f.kind)
            if draw is None:
                continue
            name = f"{f.kind.upper()}_{f.w}x{f.d}"
            layer = "A-FURN" if f.furniture else "A-FLOR-FIXT"
            self.block(name, draw(f.w, f.d), layer)
            self.msp.add_blockref(
                name, self.pt(f.x, f.y), dxfattribs={"layer": layer, "rotation": -f.rotation}
            )

    def door_block(self, o: Opening) -> str:
        w = o.width
        if o.operation == "sliding":
            name = f"DOOR_SLIDING_{w}"
            if name not in self.blocks:
                blk = self.doc.blocks.new(name=name)
                p = 0.55 * w
                blk.add_lwpolyline([(0, -50), (p, -50), (p, -15), (0, -15)], close=True)
                blk.add_lwpolyline([(w - p, 15), (w, 15), (w, 50), (w - p, 50)], close=True)
                self.blocks.add(name)
            return name
        leaves = 2 if o.operation == "double" else 1
        name = f"DOOR_HINGED_{w}" + ("_DOUBLE" if leaves == 2 else "")
        if name not in self.blocks:
            blk = self.doc.blocks.new(name=name)
            # closed position along +x from the hinge at the origin, opening towards +y
            if leaves == 1:
                blk.add_line((0, 0), (0, w))
                blk.add_arc((0, 0), w, 0, 90)
            else:
                r = w / 2
                blk.add_line((0, 0), (0, r))
                blk.add_arc((0, 0), r, 0, 90)
                blk.add_line((w, 0), (w, r))
                blk.add_arc((w, 0), r, 90, 180)
            self.blocks.add(name)
        return name

    def openings(self) -> None:
        polys = {r.id: Polygon(r.polygon) for r in self.st.rooms}
        for o in self.st.openings:
            w = self.st.wall(o.wall)
            if o.kind == "window":
                self.window(w, o)
                continue
            self.door(w, o, polys)

    def _span(self, w: Wall, o: Opening):
        if w.horizontal:
            cx, cy = w.a[0] + o.offset, w.a[1]
            return (cx - o.width / 2, cy), (cx + o.width / 2, cy), (1, 0), (0, 1)
        cx, cy = w.a[0], w.a[1] + o.offset
        return (cx, cy - o.width / 2), (cx, cy + o.width / 2), (0, 1), (1, 0)

    def window(self, w: Wall, o: Opening) -> None:
        name = f"WINDOW_{o.width}x{w.thickness}"
        if name not in self.blocks:
            blk = self.doc.blocks.new(name=name)
            h = w.thickness / 2
            for off in (-h, h, -h * 0.18, h * 0.18):
                blk.add_line((0, off), (o.width, off))
            blk.add_line((0, -h), (0, h))
            blk.add_line((o.width, -h), (o.width, h))
            self.blocks.add(name)
        a, _, _, _ = self._span(w, o)
        # block runs along +x; a vertical wall (along +y on the plan = -Y in the DXF)
        rot = 0 if w.horizontal else -90
        self.msp.add_blockref(name, self.pt(*a), dxfattribs={"layer": "A-GLAZ", "rotation": rot})

    def door(self, w: Wall, o: Opening, polys) -> None:
        a, b, u, n = self._span(w, o)
        h = w.thickness / 2
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        side = 1.0
        into = o.rooms[0]
        if into and into in polys:
            c = polys[into].representative_point()
            side = 1.0 if (c.x - mid[0]) * n[0] + (c.y - mid[1]) * n[1] > 0 else -1.0
        name = self.door_block(o)
        start, end = (b, a) if o.hinge == "end" else (a, b)
        face = (start[0] + n[0] * h * side, start[1] + n[1] * h * side)
        # plan direction along the wall (start -> end) and into the swing room, as DXF angles
        along = (end[0] - start[0], -(end[1] - start[1]))
        into_v = (n[0] * side, -(n[1] * side))
        rot = math.degrees(math.atan2(along[1], along[0]))
        # mirror the block when the swing side is clockwise from the wall direction
        cross = along[0] * into_v[1] - along[1] * into_v[0]
        attribs = {"layer": "A-DOOR", "rotation": rot}
        if cross < 0:
            attribs["yscale"] = -1
        insert = face if o.operation != "sliding" else (start[0], start[1])
        self.msp.add_blockref(name, self.pt(*insert), dxfattribs=attribs)

    # ------------------------------------------------------------------ geometry
    def walls(self) -> None:
        rects = {w.id: box(*_wall_rect(w, self.st.walls)) for w in self.st.walls}
        cuts = []
        for o in self.st.openings:
            w = self.st.wall(o.wall)
            a, b, _, n = self._span(w, o)
            h = w.thickness / 2 + 5
            cuts.append(
                box(
                    min(a[0], b[0]) - n[0] * h,
                    min(a[1], b[1]) - n[1] * h,
                    max(a[0], b[0]) + n[0] * h,
                    max(a[1], b[1]) + n[1] * h,
                )
            )
        cut = unary_union(cuts) if cuts else Polygon()
        ext = unary_union([rects[w.id] for w in self.st.walls if w.kind == "exterior"])
        inner = unary_union(
            [rects[w.id] for w in self.st.walls if w.kind != "exterior"]
        ).difference(ext)
        self.poly(ext.difference(cut), "A-WALL-EXTR", solid_rgb=(46, 46, 46))
        self.poly(inner.difference(cut), "A-WALL-INTR", solid_rgb=(140, 140, 140))

    def site(self) -> None:
        site = self.b.site
        foot = unary_union([Polygon(r.polygon) for r in self.st.rooms]).buffer(
            100, join_style="mitre"
        )
        for e in site.elements:
            poly = Polygon(e.polygon).difference(foot)
            if poly.is_empty:
                continue
            if e.kind == "boundary_wall":
                self.poly(poly, "L-SITE-WALL", solid_rgb=(200, 200, 200))
            elif e.kind == "gate":
                continue
            elif e.kind == "pool" and e.water:
                water = Polygon(e.water)
                self.poly(poly.difference(water), "L-SITE", hatch="paving")
                self.poly(water, "L-SITE", hatch="water")
            else:
                kind = e.kind if e.kind in HATCH_PATTERN else "paving"
                self.poly(poly, "L-SITE", hatch=kind)
            if e.name and e.kind not in ("paving", "boundary_wall", "gate"):
                c = (Polygon(e.water) if e.water else poly).representative_point()
                self.label(
                    [e.name.upper(), fmt_area(poly.area / 1e6, self.unit)], c.x, c.y, "L-SITE"
                )
        plot = [(0, 0), (site.width, 0), (site.width, site.depth), (0, site.depth)]
        self.msp.add_lwpolyline(
            [self.pt(*p) for p in plot],
            close=True,
            dxfattribs={"layer": "C-PROP", "ltscale": self.scale / 10},
        )
        from app.modules.ai.floorplan.model.build import setback_box

        x0, y0, x1, y1 = setback_box(site)
        if (x0, y0, x1, y1) != (0, 0, site.width, site.depth):
            pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            self.msp.add_lwpolyline(
                [self.pt(*p) for p in pts],
                close=True,
                dxfattribs={"layer": "C-PROP-SETB", "ltscale": self.scale / 10},
            )

    def stairs(self) -> None:
        for s in self.st.stairs:
            for f in s.flights:
                pts = [(f.x, f.y), (f.x + f.w, f.y), (f.x + f.w, f.y + f.h), (f.x, f.y + f.h)]
                self.msp.add_lwpolyline(
                    [self.pt(*p) for p in pts], close=True, dxfattribs={"layer": "A-FLOR-STRS"}
                )
                n = max(1, f.risers - 1)
                for k in range(1, n):
                    if f.axis == "x":
                        x = f.x + f.w * k / n
                        self.msp.add_line(
                            self.pt(x, f.y),
                            self.pt(x, f.y + f.h),
                            dxfattribs={"layer": "A-FLOR-STRS"},
                        )
                    else:
                        y = f.y + f.h * k / n
                        self.msp.add_line(
                            self.pt(f.x, y),
                            self.pt(f.x + f.w, y),
                            dxfattribs={"layer": "A-FLOR-STRS"},
                        )
            first = s.flights[0]
            x = first.x + first.w / 2
            y = first.y + (150 if first.up == 1 else first.h - 150)
            self.msp.add_text(
                "UP", height=self.small_h, dxfattribs={"layer": "A-FLOR-STRS", "style": "PLAN"}
            ).set_placement(self.pt(x, y), align=TextEntityAlignment.MIDDLE_CENTER)

    def label(self, lines: list[str], x: float, y: float, layer: str) -> None:
        hs = [self.text_h] + [self.small_h] * (len(lines) - 1)
        total = sum(h * 1.4 for h in hs)
        cy = y - total / 2
        for t, h in zip(lines, hs, strict=True):
            cy += h * 1.4
            self.msp.add_text(
                t, height=h, dxfattribs={"layer": layer, "style": "PLAN"}
            ).set_placement(self.pt(x, cy - h * 0.4), align=TextEntityAlignment.MIDDLE_CENTER)

    def room_labels(self) -> None:
        for r in self.st.rooms:
            xs, ys = [p[0] for p in r.polygon], [p[1] for p in r.polygon]
            cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
            if r.type == "shaft":
                self.label(["DUCT"], cx, cy, "A-AREA-IDEN")
                continue
            dims = (
                f"{fmt_len(max(xs) - min(xs), self.unit)} x {fmt_len(max(ys) - min(ys), self.unit)}"
            )
            self.label(
                [r.name.upper(), dims, fmt_area(r.net_area_m2, self.unit)], cx, cy, "A-AREA-IDEN"
            )

    # ------------------------------------------------------------------ dimensions
    def dimensions(self) -> None:
        dim = self.doc.dimstyles.new("PLAN_DIM")
        dim.dxf.dimtxsty = "PLAN"
        dim.dxf.dimtxt = 1.8 * self.scale
        dim.dxf.dimasz = 1.2 * self.scale
        dim.dxf.dimtsz = 1.2 * self.scale  # architectural ticks
        dim.dxf.dimexo = 0.8 * self.scale
        dim.dxf.dimexe = 1.0 * self.scale
        dim.dxf.dimgap = 0.6 * self.scale
        dim.dxf.dimdec = 0
        dim.dxf.dimtad = 1
        comp = _Composer(self.b, "A3", self.furniture, self.unit)
        comp.choose_scale()
        foot = unary_union([Polygon(r.polygon) for r in self.st.rooms]).buffer(
            100, join_style="mitre"
        )
        fx0, fy0, fx1, fy1 = foot.bounds
        site = self.b.site
        step = 1500.0
        for side in ("north", "south", "west", "east"):
            horizontal = side in ("north", "south")
            pts = comp._facade_points(side, foot)
            sign = -1 if side in ("north", "west") else 1
            edge = {"north": fy0, "south": fy1, "west": fx0, "east": fx1}[side]
            plot_edge = {"north": 0, "south": site.depth, "west": 0, "east": site.width}[side]
            for k, chain in enumerate((pts, [pts[0], pts[-1]])):
                self.chain(chain, edge + sign * step * 0.4 * (k + 1), horizontal)
            whole = [0.0, float(site.width if horizontal else site.depth)]
            self.chain(whole, plot_edge + sign * step * 0.6, horizontal)

    def chain(self, pts: list[float], pos: float, horizontal: bool) -> None:
        pts = sorted(set(pts))
        labels = chain_labels(pts, self.unit)
        for (a, b), text in zip(zip(pts, pts[1:], strict=False), labels, strict=True):
            if horizontal:
                p1, p2, base, angle = self.pt(a, pos), self.pt(b, pos), self.pt(a, pos), 0
            else:
                p1, p2, base, angle = self.pt(pos, a), self.pt(pos, b), self.pt(pos, a), 90
            d = self.msp.add_linear_dim(
                base=base,
                p1=p1,
                p2=p2,
                angle=angle,
                dimstyle="PLAN_DIM",
                text=text,
                dxfattribs={"layer": "A-ANNO-DIMS"},
            )
            d.render()

    # ------------------------------------------------------------------ paper space
    def layout(self) -> None:
        sheet = "A1" if self.sheet.width > 500 else "A3"
        w, h = (841, 594) if sheet == "A1" else (420, 297)
        lay = self.doc.layouts.new(sheet)
        lay.page_setup(size=(w, h), margins=(0, 0, 0, 0), units="mm")
        k = w / 420
        vw, vh = w - (8 + 98 + 8) * k, h - 16 * k
        vx, vy = 8 * k + vw / 2, 8 * k + vh / 2
        site = self.b.site
        lay.add_viewport(
            center=(vx, vy),
            size=(vw, vh),
            view_center_point=(site.width / 2, site.depth / 2),
            view_height=vh * self.scale,
        )
        x0 = w - (8 + 98) * k
        lay.add_lwpolyline(
            [(8 * k, 8 * k), (w - 8 * k, 8 * k), (w - 8 * k, h - 8 * k), (8 * k, h - 8 * k)],
            close=True,
            dxfattribs={"layer": "G-ANNO-TTLB"},
        )
        lay.add_line((x0, 8 * k), (x0, h - 8 * k), dxfattribs={"layer": "G-ANNO-TTLB"})
        m = self.b.meta
        rows = [
            ("PROJECT", m.project or "-"),
            ("CLIENT", m.client or "-"),
            ("DRAWING", m.title),
            ("DRAWING NO.", f"{m.drawing_number} V{m.version}"),
            ("SCALE", f"1:{self.scale} @ {sheet}"),
            ("DATE", m.date),
            *[("", line) for line in area_lines(self.b.areas, self.unit)],
            ("", "FOR DESIGN PURPOSES ONLY, NOT FOR CONSTRUCTION"),
        ]
        y = h - 30 * k
        for name, value in rows:
            lay.add_text(
                name, height=1.5 * k, dxfattribs={"layer": "G-ANNO-TTLB", "style": "PLAN"}
            ).set_placement((x0 + 3 * k, y))
            lay.add_text(
                value, height=1.8 * k, dxfattribs={"layer": "G-ANNO-TTLB", "style": "PLAN"}
            ).set_placement((x0 + 25 * k if name else x0 + 3 * k, y))
            y -= 5 * k
        for rev in m.revisions[-5:]:
            lay.add_text(
                f"{rev.rev}  {rev.date}  {rev.description[:40]}",
                height=1.5 * k,
                dxfattribs={"layer": "G-ANNO-TTLB", "style": "PLAN"},
            ).set_placement((x0 + 3 * k, y))
            y -= 3.5 * k

    def render(self) -> bytes:
        self.site()
        self.walls()
        self.openings()
        self.stairs()
        self.fixtures()
        self.room_labels()
        self.dimensions()
        self.layout()
        buf = io.StringIO()
        self.doc.write(buf)
        return buf.getvalue().encode("utf-8")


def ring_of(ring) -> list[tuple[float, float]]:
    return list(ring.coords)[:-1]


def building_dxf(b: Building, *, sheet: str | None = None, furniture: bool | None = None) -> bytes:
    return _Dxf(b, sheet, furniture).render()


__all__ = ["building_dxf", "LAYERS", "colors"]
