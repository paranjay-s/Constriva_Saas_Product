"""Fixture and furniture blocks, drawn once in real millimetres.

Origin at the fixture's centre; rotation 0 has the back against the north side (y < 0,
y grows south). Shapes are simple line drawings at true size: the sheet scales them, the
DXF inserts them as named blocks (WC, BASIN, ...). Each block is a list of
("line", [points], closed) | ("circle", (x, y), r) | ("arc", (x, y), r, start, end).
"""

import math

Shape = tuple


def _rect(x0: float, y0: float, x1: float, y1: float) -> Shape:
    return ("line", [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], True)


def _ellipse(cx: float, cy: float, rx: float, ry: float, n: int = 24) -> Shape:
    pts = [
        (cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]
    return ("line", pts, True)


def wc(w: float, d: float) -> list[Shape]:
    hw, hd = w / 2, d / 2
    tank = 0.28 * d
    return [
        _rect(-hw * 0.9, -hd, hw * 0.9, -hd + tank),
        _ellipse(0, -hd + tank + (d - tank) * 0.48, hw * 0.75, (d - tank) * 0.48),
    ]


def basin(w: float, d: float) -> list[Shape]:
    hw, hd = w / 2, d / 2
    return [_rect(-hw, -hd, hw, hd), _ellipse(0, 0.05 * d, hw * 0.65, hd * 0.6)]


def shower(w: float, d: float) -> list[Shape]:
    hw, hd = w / 2, d / 2
    return [
        _rect(-hw, -hd, hw, hd),
        ("line", [(-hw, -hd), (hw, hd)], False),
        ("line", [(hw, -hd), (-hw, hd)], False),
        ("circle", (0, 0), min(w, d) * 0.06),
    ]


def bath(w: float, d: float) -> list[Shape]:
    hw, hd = w / 2, d / 2
    i = min(w, d) * 0.1
    return [
        _rect(-hw, -hd, hw, hd),
        _rect(-hw + i, -hd + i, hw - i, hd - i),
        ("circle", (hw - 2.2 * i, 0), i * 0.5),
    ]


def counter(w: float, d: float) -> list[Shape]:
    hw, hd = w / 2, d / 2
    return [_rect(-hw, -hd, hw, hd), ("line", [(-hw, hd - 50), (hw, hd - 50)], False)]


def sink(w: float, d: float) -> list[Shape]:
    hw, hd = w / 2, d / 2
    return [
        _rect(-hw, -hd, hw, hd),
        _rect(-hw + 40, -hd + 60, -20, hd - 50),
        _rect(20, -hd + 60, hw - 40, hd - 50),
        ("circle", (0, -hd + 35), 15),
    ]


def hob(w: float, d: float) -> list[Shape]:
    hw, hd = w / 2, d / 2
    r = min(w, d) * 0.15
    return [_rect(-hw, -hd, hw, hd)] + [
        ("circle", (sx * w * 0.22, sy * d * 0.22), r) for sx in (-1, 1) for sy in (-1, 1)
    ]


def fridge(w: float, d: float) -> list[Shape]:
    hw, hd = w / 2, d / 2
    return [_rect(-hw, -hd, hw, hd), ("line", [(-hw, hd - 60), (hw, hd - 60)], False)]


def wardrobe(w: float, d: float) -> list[Shape]:
    hw, hd = w / 2, d / 2
    shapes = [_rect(-hw, -hd, hw, hd), ("line", [(-hw, 0), (hw, 0)], False)]
    n = max(2, int(w // 500))
    for i in range(1, n):
        x = -hw + w * i / n
        shapes.append(("line", [(x, -hd), (x, hd)], False))
    return shapes


def bed(w: float, d: float, pillows: int) -> list[Shape]:
    hw, hd = w / 2, d / 2
    pw = (w - 120) / pillows
    shapes = [
        _rect(-hw, -hd, hw, hd),
        ("line", [(-hw, -hd + 0.36 * d), (hw, -hd + 0.36 * d)], False),
    ]
    for i in range(pillows):
        x0 = -hw + 60 + i * pw
        shapes.append(_rect(x0 + 20, -hd + 60, x0 + pw - 20, -hd + 60 + 0.18 * d))
    shapes.append(("line", [(hw - 0.3 * w, -hd + 0.36 * d), (hw, -hd + 0.5 * d)], False))
    return shapes


def side_table(w: float, d: float) -> list[Shape]:
    hw, hd = w / 2, d / 2
    return [_rect(-hw, -hd, hw, hd), ("circle", (0, 0), min(w, d) * 0.22)]


def sofa(w: float, d: float) -> list[Shape]:
    hw, hd = w / 2, d / 2
    arm = min(180.0, w * 0.12)
    back = 0.25 * d
    shapes = [
        _rect(-hw, -hd, hw, hd),
        ("line", [(-hw + arm, -hd + back), (hw - arm, -hd + back)], False),
        ("line", [(-hw + arm, -hd + back), (-hw + arm, hd)], False),
        ("line", [(hw - arm, -hd + back), (hw - arm, hd)], False),
    ]
    seats = 3 if w > 1600 else 2
    for i in range(1, seats):
        x = -hw + arm + (w - 2 * arm) * i / seats
        shapes.append(("line", [(x, -hd + back), (x, hd)], False))
    return shapes


def armchair(w: float, d: float) -> list[Shape]:
    return sofa(w, d)[:4]


def coffee_table(w: float, d: float) -> list[Shape]:
    return [_rect(-w / 2, -d / 2, w / 2, d / 2)]


def dining_table(w: float, d: float) -> list[Shape]:
    hw, hd = w / 2, d / 2
    tw, td = w - 900, d - 900  # chairs around
    tw, td = max(tw, w * 0.5), max(td, d * 0.4)
    shapes = [_rect(-tw / 2, -td / 2, tw / 2, td / 2)]
    n = max(1, int(tw // 650))
    for i in range(n):
        x = -tw / 2 + tw * (i + 0.5) / n
        shapes.append(_rect(x - 210, -td / 2 - 420, x + 210, -td / 2 - 40))
        shapes.append(_rect(x - 210, td / 2 + 40, x + 210, td / 2 + 420))
    if hw > 0 and hd > 0:
        return shapes
    return shapes


def desk(w: float, d: float) -> list[Shape]:
    hw, hd = w / 2, d / 2
    return [_rect(-hw, -hd, hw, hd), ("circle", (0, hd + 250), 220)]


def tree(w: float, d: float) -> list[Shape]:
    r = min(w, d) / 2
    shapes: list[Shape] = [("circle", (0, 0), r), ("circle", (0, 0), r * 0.12)]
    for i in range(8):
        a = 2 * math.pi * i / 8
        shapes.append(
            (
                "line",
                [
                    (r * 0.15 * math.cos(a), r * 0.15 * math.sin(a)),
                    (r * 0.8 * math.cos(a), r * 0.8 * math.sin(a)),
                ],
                False,
            )
        )
    return shapes


def plant(w: float, d: float) -> list[Shape]:
    r = min(w, d) / 2
    return [("circle", (0, 0), r), ("circle", (0, 0), r * 0.45)]


def washer(w: float, d: float) -> list[Shape]:
    hw, hd = w / 2, d / 2
    return [_rect(-hw, -hd, hw, hd), ("circle", (0, 0), min(w, d) * 0.33)]


BLOCKS = {
    "wc": wc,
    "basin": basin,
    "shower": shower,
    "bath": bath,
    "counter": counter,
    "sink": sink,
    "hob": hob,
    "fridge": fridge,
    "wardrobe": wardrobe,
    "bed_double": lambda w, d: bed(w, d, 2),
    "bed_single": lambda w, d: bed(w, d, 1),
    "side_table": side_table,
    "sofa": sofa,
    "armchair": armchair,
    "coffee_table": coffee_table,
    "dining_table": dining_table,
    "desk": desk,
    "tree": tree,
    "plant": plant,
    "washer": washer,
}

BLOCK_NAMES = {k: k.upper() for k in BLOCKS}


def place(shapes: list[Shape], cx: float, cy: float, rotation: int) -> list[Shape]:
    """Rotate (clockwise on the sheet, y down) about the origin and move to (cx, cy)."""
    a = math.radians(rotation)
    ca, sa = math.cos(a), math.sin(a)

    def tf(p):
        x, y = p
        return (cx + x * ca - y * sa, cy + x * sa + y * ca)

    out: list[Shape] = []
    for s in shapes:
        if s[0] == "line":
            out.append(("line", [tf(p) for p in s[1]], s[2]))
        elif s[0] == "circle":
            out.append(("circle", tf(s[1]), s[2]))
        else:
            out.append(("arc", tf(s[1]), s[2], s[3] + rotation, s[4] + rotation))
    return out
