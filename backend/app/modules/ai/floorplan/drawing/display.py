"""The display list: what is drawn on the sheet, in paper millimetres (y grows down).

Composed once (drawing/compose.py) and written out by the SVG and PDF emitters, so the
in-app preview, the PDF and the PNG are the same drawing. Every primitive carries the CAD
layer it belongs to (US National CAD Standard names, see RULES.md).
"""

from dataclasses import dataclass, field

Pt = tuple[float, float]


@dataclass
class Line:
    pts: list[Pt]
    width: float
    layer: str
    color: str = "#1a1a1a"
    dash: tuple[float, ...] | None = None
    closed: bool = False


@dataclass
class Area:
    """A filled polygon (with holes), optionally outlined."""

    rings: list[list[Pt]]  # first ring outside, the rest holes
    fill: str | None
    layer: str
    stroke: str | None = None
    width: float = 0.0


@dataclass
class Arc:
    centre: Pt
    radius: float
    start_deg: float  # paper angles: 0 = +x, 90 = +y (down)
    end_deg: float
    width: float
    layer: str
    color: str = "#1a1a1a"
    dash: tuple[float, ...] | None = None


@dataclass
class Circle:
    centre: Pt
    radius: float
    width: float
    layer: str
    color: str = "#1a1a1a"
    fill: str | None = None


@dataclass
class Text:
    x: float
    y: float  # baseline
    text: str
    size: float
    layer: str
    bold: bool = False
    anchor: str = "middle"  # start, middle, end
    rotation: float = 0.0  # degrees, counter-clockwise on paper
    color: str = "#1a1a1a"


@dataclass
class Sheet:
    width: float
    height: float
    scale: int
    items: list = field(default_factory=list)
    title: str = ""

    def add(self, *items) -> None:
        self.items.extend(items)
