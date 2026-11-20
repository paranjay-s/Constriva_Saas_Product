"""Fixture symbol library, drawn once as neutral primitives.

Each symbol is a footprint `w` x `d` (cm) centred on (0, 0), y grows south. At
rotation 0 the back of the fixture (bed headboard, toilet cistern, counter back) is
against the north side (y = -d/2). The same primitives feed the SVG `<symbol>` and,
later, the DXF block, so both outputs always match.

All symbols are original drawings made from basic shapes; no third-party CAD blocks.
"""

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float
    fill: str | None = None  # a FILLS key; None = outline only


@dataclass(frozen=True)
class Circle:
    cx: float
    cy: float
    r: float
    fill: str | None = None


@dataclass(frozen=True)
class Line:
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class Arc:
    """Circular arc from start_deg to end_deg, counter-clockwise in y-up maths terms."""

    cx: float
    cy: float
    r: float
    start_deg: float
    end_deg: float


@dataclass(frozen=True)
class Poly:
    points: tuple[tuple[float, float], ...]
    closed: bool = True
    fill: str | None = None


Primitive = Rect | Circle | Line | Arc | Poly

# Material colours for the drawing (SVG/PDF/PNG). The DXF keeps line-only blocks.
FILLS: dict[str, str] = {
    "white": "#FFFFFF",
    "linen": "#F3ECE0",
    "duvet": "#BFD3E6",
    "wood": "#C99D6E",
    "wood_dark": "#8A6447",
    "fabric": "#B7C3CE",
    "fabric_dark": "#7F8F9E",
    "chair": "#EBDDCB",
    "stone": "#E4E7EA",
    "metal": "#A9B4BE",
    "dark": "#4E5358",
    "water": "#CDE5F2",
    "leaf": "#9FCF8F",
    "leaf_dark": "#5E9E52",
    "pot": "#C08A5B",
}


@dataclass(frozen=True)
class Symbol:
    name: str
    w: float
    d: float
    prims: tuple[Primitive, ...] = field(default_factory=tuple)


def _oval(cx: float, cy: float, rx: float, ry: float, n: int = 20, fill: str | None = None) -> Poly:
    pts = tuple(
        (
            round(cx + rx * math.cos(2 * math.pi * i / n), 2),
            round(cy + ry * math.sin(2 * math.pi * i / n), 2),
        )
        for i in range(n)
    )
    return Poly(pts, closed=True, fill=fill)


def _rounded_rect(
    x: float, y: float, w: float, h: float, r: float, n: int = 4, fill: str | None = None
) -> Poly:
    pts: list[tuple[float, float]] = []
    corners = [
        (x + w - r, y + r, -90),
        (x + w - r, y + h - r, 0),
        (x + r, y + h - r, 90),
        (x + r, y + r, 180),
    ]
    for cx, cy, a0 in corners:
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((round(cx + r * math.cos(a), 2), round(cy + r * math.sin(a), 2)))
    return Poly(tuple(pts), closed=True, fill=fill)


def _bed(w: float, pillows: int) -> tuple[Primitive, ...]:
    d = 200
    x0, y0 = -w / 2, -d / 2
    prims: list[Primitive] = [
        Rect(x0, y0, w, d, fill="linen"),  # mattress
        Rect(x0, y0, w, 12, fill="wood_dark"),  # headboard
    ]
    gap = 8
    pw = (w - gap * (pillows + 1)) / pillows
    for i in range(pillows):
        prims.append(_rounded_rect(x0 + gap + i * (pw + gap), y0 + 18, pw, 34, 8, fill="white"))
    prims.append(Rect(x0 + 2, y0 + 66, w - 4, d - 68, fill="duvet"))  # duvet
    prims.append(Rect(x0 + 2, y0 + 66, w - 4, 20, fill="white"))  # turned-down sheet
    prims.append(
        Poly(
            ((x0 + w - 2, y0 + 86), (x0 + w - 42, y0 + 126), (x0 + w - 2, y0 + 126)),
            closed=True,
            fill="linen",
        )
    )
    return tuple(prims)


def _chair(cx: float, cy: float, facing: str, w: float = 44, d: float = 40) -> tuple:
    """Dining chair centred at (cx, cy); its back is on the side away from the table."""
    if facing in ("down", "up"):
        seat = _rounded_rect(cx - w / 2, cy - d / 2, w, d, 6, fill="chair")
        by = cy - d / 2 if facing == "down" else cy + d / 2 - 8
        back = Rect(cx - w / 2 + 3, by, w - 6, 8, fill="wood_dark")
    else:
        seat = _rounded_rect(cx - d / 2, cy - w / 2, d, w, 6, fill="chair")
        bx = cx - d / 2 if facing == "right" else cx + d / 2 - 8
        back = Rect(bx, cy - w / 2 + 3, 8, w - 6, fill="wood_dark")
    return (seat, back)


def _build() -> dict[str, Symbol]:
    s: dict[str, Symbol] = {}

    s["bed_double"] = Symbol("bed_double", 160, 200, _bed(160, 2))
    s["bed_single"] = Symbol("bed_single", 90, 200, _bed(90, 1))

    s["wardrobe"] = Symbol(
        "wardrobe",
        180,
        60,
        (
            Rect(-90, -30, 180, 60, fill="wood"),
            Line(-30, -30, -30, 30),
            Line(30, -30, 30, 30),
            Rect(-90, 22, 180, 8, fill="wood_dark"),  # door fronts
            Circle(-36, 12, 2.5, fill="dark"),
            Circle(-24, 12, 2.5, fill="dark"),
            Circle(24, 12, 2.5, fill="dark"),
            Circle(36, 12, 2.5, fill="dark"),
        ),
    )

    s["side_table"] = Symbol(
        "side_table",
        45,
        40,
        (
            _rounded_rect(-22.5, -20, 45, 40, 4, fill="wood"),
            Circle(0, 2, 10, fill="white"),  # lamp shade
            Circle(0, 2, 3.5, fill="dark"),
        ),
    )

    s["sofa_3"] = Symbol(
        "sofa_3",
        210,
        90,
        (
            _rounded_rect(-105, -45, 210, 90, 10, fill="fabric_dark"),
            _rounded_rect(-83, -21, 54, 62, 6, fill="fabric"),
            _rounded_rect(-27, -21, 54, 62, 6, fill="fabric"),
            _rounded_rect(29, -21, 54, 62, 6, fill="fabric"),
            _rounded_rect(-70, -38, 40, 16, 6, fill="white"),  # cushions
            _rounded_rect(30, -38, 40, 16, 6, fill="white"),
        ),
    )
    s["armchair"] = Symbol(
        "armchair",
        80,
        80,
        (
            _rounded_rect(-40, -40, 80, 80, 10, fill="fabric_dark"),
            _rounded_rect(-26, -20, 52, 56, 6, fill="fabric"),
        ),
    )
    s["coffee_table"] = Symbol(
        "coffee_table",
        100,
        60,
        (
            _rounded_rect(-50, -30, 100, 60, 8, fill="wood"),
            _rounded_rect(-40, -20, 80, 40, 5, fill="water"),  # glass top
        ),
    )

    s["dining_4"] = Symbol(
        "dining_4",
        170,
        170,
        (
            *_chair(0, -65, "down"),
            *_chair(0, 65, "up"),
            *_chair(-65, 0, "right"),
            *_chair(65, 0, "left"),
            _rounded_rect(-45, -45, 90, 90, 8, fill="wood"),
            Circle(0, 0, 14, fill="leaf"),  # table centrepiece
        ),
    )
    s["dining_6"] = Symbol(
        "dining_6",
        180,
        170,
        (
            *(c for cx in (-58, 0, 58) for c in _chair(cx, -65, "down")),
            *(c for cx in (-58, 0, 58) for c in _chair(cx, 65, "up")),
            _rounded_rect(-90, -45, 180, 90, 8, fill="wood"),
            Circle(0, 0, 14, fill="leaf"),
        ),
    )

    s["kitchen_counter"] = Symbol(
        "kitchen_counter",
        240,
        60,
        (
            Rect(-120, -30, 240, 60, fill="stone"),
            _rounded_rect(-90, -22, 64, 42, 6, fill="metal"),  # sink
            _rounded_rect(-85, -18, 54, 34, 6, fill="water"),
            Circle(-58, -25, 3, fill="dark"),  # tap
            _rounded_rect(28, -24, 64, 48, 4, fill="dark"),  # hob
            Circle(45, -10, 9, fill="metal"),
            Circle(75, -10, 9, fill="metal"),
            Circle(45, 12, 7, fill="metal"),
            Circle(75, 12, 7, fill="metal"),
        ),
    )

    s["fridge"] = Symbol("fridge", 70, 65, (Rect(-35, -32.5, 70, 65, fill="metal"),))

    s["toilet"] = Symbol(
        "toilet",
        40,
        70,
        (
            _rounded_rect(-20, -35, 40, 18, 4, fill="white"),
            _oval(0, 8, 17, 23, fill="white"),
            _oval(0, 10, 11, 15, fill="water"),
        ),
    )
    s["basin"] = Symbol(
        "basin",
        50,
        40,
        (
            Rect(-25, -20, 50, 40, fill="stone"),
            _oval(0, 2, 18, 13, fill="white"),
            _oval(0, 3, 12, 8, fill="water"),
            Circle(0, -13, 2.5, fill="dark"),
        ),
    )
    s["bathtub"] = Symbol(
        "bathtub",
        170,
        75,
        (
            Rect(-85, -37.5, 170, 75, fill="white"),
            _rounded_rect(-78, -30, 156, 60, 22, fill="water"),
            Circle(-62, 0, 3, fill="dark"),
        ),
    )
    s["shower"] = Symbol(
        "shower",
        90,
        90,
        (
            Rect(-45, -45, 90, 90, fill="water"),
            Line(-45, -45, 45, 45),
            Line(45, -45, -45, 45),
            Circle(0, 0, 5, fill="metal"),
        ),
    )
    s["desk"] = Symbol(
        "desk",
        120,
        100,
        (Rect(-60, -50, 120, 60, fill="wood"), *_chair(0, 30, "up")),
    )

    leaves = tuple(
        Line(
            round(18 * math.cos(math.radians(a)), 2),
            round(18 * math.sin(math.radians(a)), 2),
            round(64 * math.cos(math.radians(a)), 2),
            round(64 * math.sin(math.radians(a)), 2),
        )
        for a in range(0, 360, 30)
    )
    s["tree"] = Symbol(
        "tree",
        150,
        150,
        (Circle(0, 0, 72, fill="leaf"), *leaves, Circle(0, 0, 16, fill="leaf_dark")),
    )
    s["plant"] = Symbol(
        "plant",
        60,
        60,
        (
            Circle(0, 0, 28, fill="pot"),
            Circle(0, 0, 21, fill="leaf"),
            Line(-15, 0, 15, 0),
            Line(0, -15, 0, 15),
            Circle(0, 0, 6, fill="leaf_dark"),
        ),
    )
    return s


SYMBOLS: dict[str, Symbol] = _build()


def footprint(symbol: str, rotation: int) -> tuple[float, float]:
    """Width and depth of a placed symbol after rotation."""
    sym = SYMBOLS[symbol]
    return (sym.d, sym.w) if rotation in (90, 270) else (sym.w, sym.d)
