"""The drawing's look: ISO 128 pens, greys, light landscape hatches, fixed text sizes.

All sizes are millimetres on paper. Black and greys on white; colour only as light
hatches for water, lawn and paving; no room fills. One font: Jost (SIL OFL 1.1).
"""

from pathlib import Path

FONT_DIR = Path(__file__).parent / "fonts"
FONT_REGULAR = FONT_DIR / "Jost-Regular.ttf"
FONT_BOLD = FONT_DIR / "Jost-SemiBold.ttf"
FONT_FAMILY = "Jost"

# ISO 128 line widths (mm) at the stated scale
PEN = {
    "extra": 1.0,  # sheet frame
    "thick": 0.7,  # cut exterior walls
    "wide": 0.5,  # cut interior walls, plot boundary
    "medium": 0.35,  # title block rules
    "normal": 0.25,  # door leaves, window frames, stairs, site walls
    "thin": 0.18,  # arcs, glazing, fixtures, furniture, setback line
    "fine": 0.13,  # hatches, dimension and extension lines
}

INK = "#1a1a1a"
GREY = {
    "wall_ext": "#2e2e2e",  # poché of cut exterior walls
    "wall_int": "#8c8c8c",  # poché of cut interior walls
    "wall_part": "#a6a6a6",
    "site_wall": "#c8c8c8",
    "furniture": "#555555",
    "text_muted": "#5a5a5a",
    "rule": "#9a9a9a",
}
# light hatches: the only colour on the sheet
HATCH = {
    "lawn": {"color": "#a9bb9b", "angle": 45, "gap": 1.6, "dash": (0.6, 1.2)},
    "garden": {"color": "#a9bb9b", "angle": 45, "gap": 2.2, "dash": (0.6, 1.6)},
    "water": {"color": "#93b3c8", "angle": 0, "gap": 1.3, "dash": None},
    "paving": {"color": "#cbc6bd", "grid": 4.0},
    "coping": {"color": "#c2bdb4", "grid": 2.0},
    "deck": {"color": "#c9bba3", "angle": 0, "gap": 1.0, "dash": None},
    "parking": {"color": "#cbc6bd", "grid": 6.0},
}

# ISO 3098 text heights (mm); nothing else is used
TEXT = {"title": 5.0, "heading": 3.5, "room": 2.5, "label": 1.8, "small": 1.5}

SHEETS = {"A3": (420.0, 297.0), "A1": (841.0, 594.0)}
SCALES = (50, 75, 100, 125, 150, 200, 250, 300, 400, 500)
