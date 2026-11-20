"""Curved walls and round rooms (feat/pro_2, C3.1). Pure Python: the detector, the furnisher and the Blender
builder share it, and it is tested without Blender (tests/test_curves.py).

Plan format (feet, +y up, angles in degrees anticlockwise from +x):
    floor["arcs"]  = [{"c": [cx, cy], "r": r, "t": t, "a0": a0, "a1": a1}]   a curved wall: centre line of radius r,
                     thickness t, from angle a0 to a1 (a1 > a0; a full circle is 0..360)
    room["circle"] = [cx, cy, r]   a round room (r to the inside wall face). Its "rects" stay as thin row slices of
                     the disc (disc_rects), so everything that works with rectangles (furniture, the walker, the
                     review page) still works; the 3D shell follows the circle itself.
"""
import math

SEG_DEG = 6.0           # mesh pieces along a curve
SLICE_FT = 0.5          # row slices of a round room


def arc_points(cx, cy, r, a0, a1, step=SEG_DEG):
    """points along an arc, ends included"""
    n = max(2, int(math.ceil(abs(a1 - a0) / step)) + 1)
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / (n - 1))),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / (n - 1)))) for k in range(n)]


def ring_sector(cx, cy, r_in, r_out, a0, a1, step=SEG_DEG):
    """the outline of a curved wall (or a ring) as a polygon: outer arc forwards, inner arc back"""
    return arc_points(cx, cy, r_out, a0, a1, step) + list(reversed(arc_points(cx, cy, r_in, a0, a1, step)))


def sector_quads(cx, cy, r_in, r_out, a0, a1, step=SEG_DEG):
    """the same band as quads [(p_in0, p_out0, p_out1, p_in1)], for building a mesh piece by piece"""
    outer, inner = arc_points(cx, cy, r_out, a0, a1, step), arc_points(cx, cy, r_in, a0, a1, step)
    return [(inner[k], outer[k], outer[k + 1], inner[k + 1]) for k in range(len(outer) - 1)]


def disc_rects(cx, cy, r, h=SLICE_FT):
    """a disc as row slices [x0, x1, y0, y1]: each slice as wide as the disc at its narrower edge (inside it)"""
    out = []
    y = cy - r
    while y < cy + r - 1e-6:
        y1 = min(cy + r, y + h)
        edge = max(abs(y - cy), abs(y1 - cy))
        half = math.sqrt(max(0.0, r * r - edge * edge))
        if half > 0.05:
            out.append([round(cx - half, 3), round(cx + half, 3), round(y, 3), round(y1, 3)])
        y = y1
    return out


def arc_blocks(cx, cy, r_in, r_out, a0, a1, cell):
    """small axis-aligned boxes covering a curved wall band (for a flood fill on a grid of `cell`)"""
    out = []
    step = max(1.0, math.degrees(cell / max(r_out, 1e-6)))
    a = a0
    while a <= a1 + 1e-6:
        for rr in (r_in, (r_in + r_out) / 2, r_out):
            x, y = cx + rr * math.cos(math.radians(a)), cy + rr * math.sin(math.radians(a))
            out.append((x - cell * 0.75, x + cell * 0.75, y - cell * 0.75, y + cell * 0.75))
        a += step
    return out


def _angle(cx, cy, p):
    return math.degrees(math.atan2(p[1] - cy, p[0] - cx)) % 360


def angle_span(cx, cy, pts):
    """the angles a curve covers, as (a0, a1) with a1 > a0 (0..360 for a whole circle). `pts` are the end points
    of the curve's pieces, two per piece (as the detector's arcs() collects them): each piece covers the shorter
    way between its two ends, and the pieces' union is what the curve covers."""
    if len(pts) < 2:
        return (0.0, 360.0)
    ivs = []
    for p, q in zip(pts[0::2], pts[1::2]):
        a, b = _angle(cx, cy, p), _angle(cx, cy, q)
        lo, hi = (a, b) if (b - a) % 360 <= 180 else (b, a)
        span = (hi - lo) % 360
        ivs += [(lo, lo + span)] if lo + span <= 360 else [(lo, 360.0), (0.0, lo + span - 360)]
    ivs.sort()
    merged = []
    for lo, hi in ivs:
        if merged and lo <= merged[-1][1] + 3:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    covered = sum(hi - lo for lo, hi in merged)
    if covered >= 355:
        return (0.0, 360.0)
    # the largest gap between covered stretches (round the circle) is where the curve is open
    gaps = [(merged[(k + 1) % len(merged)][0] + (360 if k + 1 == len(merged) else 0) - merged[k][1], k)
            for k in range(len(merged))]
    _, k = max(gaps)
    a0 = merged[(k + 1) % len(merged)][0]
    a1 = merged[k][1]
    if a1 <= a0:
        a1 += 360
    return (round(a0, 2), round(a1, 2))


def curved_walls(circles, T, s):
    """the detector's circles (page units: (cx, cy, r, points)) -> curved walls: two concentric arcs a wall's
    thickness apart (from 0.5 to 2.5 times the plan's wall thickness T) with a radius of at least 3 ft (door
    swings are single arcs, never a concentric pair). -> [(cx, cy, r_in, r_out, points)] in page units."""
    out, used = [], set()
    for i, a in enumerate(circles):
        if i in used or a[2] < 3 * s:
            continue
        best = None
        for j, b in enumerate(circles):
            if j == i or j in used:
                continue
            if math.dist(a[:2], b[:2]) > 0.3 * T:
                continue
            dr = abs(a[2] - b[2])
            if 0.5 * T <= dr <= 2.5 * T and (best is None or dr < best[0]):
                best = (dr, j)
        if best is None:
            continue
        b = circles[best[1]]
        used |= {i, best[1]}
        cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        out.append((cx, cy, min(a[2], b[2]), max(a[2], b[2]), list(a[3]) + list(b[3])))
    return out


def in_arc_band(x, y, arc):
    """is (x, y) (feet) inside a plan arc wall {"c", "r", "t", "a0", "a1"}?"""
    cx, cy = arc["c"]
    d = math.hypot(x - cx, y - cy)
    if abs(d - arc["r"]) > arc["t"] / 2:
        return False
    a = math.degrees(math.atan2(y - cy, x - cx)) % 360
    a0, a1 = arc["a0"], arc["a1"]
    return a0 <= a <= a1 or a0 <= a + 360 <= a1


def round_room(rects, arcs_ft):
    """a room whose area and outline fit the inside of one curved wall -> [cx, cy, r_inner], else None.
    rects: the room's slices (feet); arcs_ft: the floor's arcs."""
    if not rects:
        return None
    area = sum((q[1] - q[0]) * (q[3] - q[2]) for q in rects)
    x0, x1 = min(q[0] for q in rects), max(q[1] for q in rects)
    y0, y1 = min(q[2] for q in rects), max(q[3] for q in rects)
    for a in arcs_ft:
        cx, cy = a["c"]
        r_in = a["r"] - a["t"] / 2
        if not (x0 - 0.5 <= cx <= x1 + 0.5 and y0 - 0.5 <= cy <= y1 + 0.5):
            continue
        if a["a1"] - a["a0"] < 300:       # a part circle: the room is not round, it has a curved side
            continue
        if abs(area - math.pi * r_in * r_in) <= 0.25 * math.pi * r_in * r_in and \
                abs((x1 - x0) - 2 * r_in) <= 0.2 * r_in and abs((y1 - y0) - 2 * r_in) <= 0.2 * r_in:
            return [round(cx, 3), round(cy, 3), round(r_in, 3)]
    return None
