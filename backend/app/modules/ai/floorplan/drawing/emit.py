"""Sheet -> SVG, PDF (vector, true scale, Jost embedded) and PNG.

The same display list drives all three, so the in-app preview, the PDF and the PNG match.
SVG groups primitives by CAD layer (<g id="A-WALL">...). The downloadable SVG embeds the
font; the preview SVG names it and the frontend serves the same font file.
"""

import base64
import math
from functools import lru_cache
from xml.sax.saxutils import escape

import pymupdf

from app.modules.ai.floorplan.drawing.display import Arc, Area, Circle, Line, Sheet, Text
from app.modules.ai.floorplan.drawing.style import FONT_BOLD, FONT_FAMILY, FONT_REGULAR

PT_PER_MM = 72 / 25.4
FONT_STACK = f"{FONT_FAMILY}, 'Century Gothic', 'Avenir Next', Arial, sans-serif"


def _n(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


@lru_cache(maxsize=1)
def _font_face() -> str:
    # subsets (Latin and the drawing's symbols) keep every SVG small
    reg = base64.b64encode(FONT_REGULAR.with_name("Jost-Regular-web.ttf").read_bytes()).decode()
    bold = base64.b64encode(FONT_BOLD.with_name("Jost-SemiBold-web.ttf").read_bytes()).decode()
    return (
        f"@font-face{{font-family:{FONT_FAMILY};font-weight:400;"
        f"src:url(data:font/ttf;base64,{reg}) format('truetype');}}"
        f"@font-face{{font-family:{FONT_FAMILY};font-weight:600;"
        f"src:url(data:font/ttf;base64,{bold}) format('truetype');}}"
    )


def to_svg(sheet: Sheet, *, embed_font: bool = False) -> str:
    W, H = sheet.width, sheet.height
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_n(W)}mm" height="{_n(H)}mm" '
        f'viewBox="0 0 {_n(W)} {_n(H)}" data-scale="1:{sheet.scale}">',
        "<style>"
        + (_font_face() if embed_font else "")
        + f"text{{font-family:{FONT_STACK};}}"
        + "</style>",
        f'<rect x="0" y="0" width="{_n(W)}" height="{_n(H)}" fill="#ffffff"/>',
    ]
    layer = None
    for item in sheet.items:
        if item.layer != layer:
            if layer is not None:
                out.append("</g>")
            layer = item.layer
            out.append(f'<g id="{escape(layer)}" class="layer">')
        out.append(_svg_item(item))
    if layer is not None:
        out.append("</g>")
    out.append("</svg>")
    return "\n".join(out)


def _dash(d) -> str:
    return f' stroke-dasharray="{" ".join(_n(v) for v in d)}"' if d else ""


def _svg_item(it) -> str:
    if isinstance(it, Line):
        pts = " ".join(f"{_n(x)},{_n(y)}" for x, y in it.pts)
        tag = "polygon" if it.closed else "polyline"
        return (
            f'<{tag} points="{pts}" fill="none" stroke="{it.color}" '
            f'stroke-width="{_n(it.width)}" stroke-linecap="butt" stroke-linejoin="miter"'
            f"{_dash(it.dash)}/>"
        )
    if isinstance(it, Area):
        d = " ".join(
            "M" + " L".join(f"{_n(x)} {_n(y)}" for x, y in ring) + " Z" for ring in it.rings
        )
        stroke = (
            f' stroke="{it.stroke}" stroke-width="{_n(it.width)}" stroke-linejoin="miter"'
            if it.stroke
            else ""
        )
        return f'<path d="{d}" fill="{it.fill or "none"}" fill-rule="evenodd"{stroke}/>'
    if isinstance(it, Arc):
        cx, cy = it.centre
        a0, a1 = math.radians(it.start_deg), math.radians(it.end_deg)
        x0, y0 = cx + it.radius * math.cos(a0), cy + it.radius * math.sin(a0)
        x1, y1 = cx + it.radius * math.cos(a1), cy + it.radius * math.sin(a1)
        large = 1 if (it.end_deg - it.start_deg) % 360 > 180 else 0
        return (
            f'<path d="M{_n(x0)} {_n(y0)} A{_n(it.radius)} {_n(it.radius)} 0 {large} 1 '
            f'{_n(x1)} {_n(y1)}" fill="none" stroke="{it.color}" stroke-width="{_n(it.width)}"'
            f"{_dash(it.dash)}/>"
        )
    if isinstance(it, Circle):
        return (
            f'<circle cx="{_n(it.centre[0])}" cy="{_n(it.centre[1])}" r="{_n(it.radius)}" '
            f'fill="{it.fill or "none"}" stroke="{it.color}" stroke-width="{_n(it.width)}"/>'
        )
    if isinstance(it, Text):
        rot = (
            f' transform="rotate({_n(-it.rotation)} {_n(it.x)} {_n(it.y)})"' if it.rotation else ""
        )
        weight = ' font-weight="600"' if it.bold else ""
        return (
            f'<text x="{_n(it.x)}" y="{_n(it.y)}" font-size="{_n(it.size)}" '
            f'text-anchor="{it.anchor}" fill="{it.color}"{weight}{rot}>{escape(it.text)}</text>'
        )
    raise TypeError(type(it))


def _rgb(hex_color: str | None):
    if not hex_color:
        return None
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))


def _dashes(d) -> str | None:
    if not d:
        return None
    return "[" + " ".join(f"{v * PT_PER_MM:.2f}" for v in d) + "] 0"


def to_pdf(sheet: Sheet, *, title: str = "", keywords: str = "") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=sheet.width * PT_PER_MM, height=sheet.height * PT_PER_MM)
    k = PT_PER_MM

    def P(p):
        return pymupdf.Point(p[0] * k, p[1] * k)

    shape = page.new_shape()
    texts: list[Text] = []
    for it in sheet.items:
        if isinstance(it, Text):
            texts.append(it)
            continue
        if isinstance(it, Line):
            if len(it.pts) < 2:
                continue
            shape.draw_polyline([P(p) for p in it.pts])
            shape.finish(
                color=_rgb(it.color),
                width=it.width * k,
                dashes=_dashes(it.dash),
                closePath=it.closed,
                lineCap=0,
                lineJoin=0,
            )
        elif isinstance(it, Area):
            for ring in it.rings:
                shape.draw_polyline([P(p) for p in ring] + [P(ring[0])])
            shape.finish(
                fill=_rgb(it.fill),
                color=_rgb(it.stroke) if it.stroke else None,
                width=it.width * k if it.stroke else 0,
                even_odd=True,
                closePath=True,
            )
        elif isinstance(it, Arc):
            cx, cy = it.centre
            a0 = math.radians(it.start_deg)
            start = (cx + it.radius * math.cos(a0), cy + it.radius * math.sin(a0))
            shape.draw_sector(P(it.centre), P(start), it.end_deg - it.start_deg, fullSector=False)
            shape.finish(color=_rgb(it.color), width=it.width * k, dashes=_dashes(it.dash))
        elif isinstance(it, Circle):
            shape.draw_circle(P(it.centre), it.radius * k)
            shape.finish(color=_rgb(it.color), fill=_rgb(it.fill), width=it.width * k)
    shape.commit()
    fonts = {False: ("jost", str(FONT_REGULAR)), True: ("jostb", str(FONT_BOLD))}
    metrics = {b: pymupdf.Font(fontfile=f) for b, (_, f) in fonts.items()}
    for t in texts:
        name, file = fonts[t.bold]
        size = t.size * k
        w = metrics[t.bold].text_length(t.text, fontsize=size)
        shift = {"start": 0.0, "middle": w / 2, "end": w}.get(t.anchor, 0.0)
        if t.rotation % 360 == 90:
            point = pymupdf.Point(t.x * k, t.y * k + shift)
            rotate = 90
        else:
            point = pymupdf.Point(t.x * k - shift, t.y * k)
            rotate = 0
        page.insert_text(
            point,
            t.text,
            fontsize=size,
            fontname=name,
            fontfile=file,
            color=_rgb(t.color),
            rotate=rotate,
        )
    doc.set_metadata(
        {
            "title": title or sheet.title,
            "creator": "Constriva floor plan generator",
            "producer": "Constriva floor plan generator",
            "keywords": keywords,
            "subject": f"Scale 1:{sheet.scale}",
        }
    )
    return doc.tobytes(garbage=3, deflate=True)


def to_png(pdf: bytes, dpi: int = 200) -> bytes:
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        return doc[0].get_pixmap(dpi=max(50, min(dpi, 600))).tobytes("png")
