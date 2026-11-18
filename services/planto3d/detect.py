"""2D plan (CAD-exported PDF) -> plan JSON: floors with walls, doors, windows, openings, rooms, stairs.
No machine learning: walls are pairs of parallel lines, openings are gaps between collinear walls,
doors are swing arcs at a gap, windows are glass lines inside a gap, rooms are flood-filled regions
named by the text inside them, and the scale comes from room size labels such as 14'x12'8".

Usage: python3 detect.py plan.pdf [out.json]      (python3 tools/dbg_plan.py draws the result over the page)
Output units are FEET; per floor, origin = lower-left of the walls, +x right, +y up the page.
"""
import json, math, re, sys
from collections import defaultdict

import rooms, vector

VOCAB_PHRASES = rooms.VOCAB["phrases"]

class PlanError(ValueError):
    """the drawing cannot be read as a plan; the message is shown to the person who uploaded it"""


# ------------------------------------------------------------------ room names
# room types and the labels that name them: web/rooms.json, matched by rooms.classify (whole words, abbreviations,
# near spellings). ROOM_TYPES keeps the old shape for code that lists the types.
ROOM_TYPES = [(t, VOCAB_PHRASES.get(t, [])) for t in rooms.TYPES]
OUTDOOR = rooms.kinds("outdoor", "covered", "void", "water")
DIM = re.compile(r"""^(\d+)'?(?:-?(\d+)"?)?\s*[xX×]\s*(\d+)'?(?:-?(\d+)"?)?$""")
FT = re.compile(r"""^(\d+)'(?:-?(\d+)"?)?$""")


def room_type(words):
    """the room type a label names, or None (rooms.classify)"""
    return rooms.classify(" ".join(words))[0]


METRIC = re.compile(r"^(\d+(?:\.\d+)?)(MM|CM|M)?[X×](\d+(?:\.\d+)?)(MM|CM|M)?$")
AREA = re.compile(r"^(\d[\d,]*(?:\.\d+)?)(SQ\.?M(?:T|TR)?\.?|M2|M²|SQ\.?FT\.?|SFT|FT2|FT²)$")
TO_FT = {"ft": 1.0, "m": 1 / 0.3048, "cm": 1 / 30.48, "mm": 1 / 304.8}


def parse_size(s):
    """a room size label -> (a, b, unit), a and b in feet. unit is 'ft', 'm', 'cm' or 'mm' when the label says so,
    'm?' for unmarked decimals (4.20x3.60) and 'cm?' for unmarked numbers above 60 (420 X 360, could be mm): no room
    is 420 ft long, and feet drawings mark feet or write small whole numbers. scale_from_labels settles the guesses."""
    s = s.replace("’", "'").replace("”", '"').replace("′", "'").replace("″", '"').replace(" ", "")
    m = DIM.match(s)
    if m and ("'" in s or '"' in s or max(int(m.group(1)), int(m.group(3))) <= 60):
        a = int(m.group(1)) + int(m.group(2) or 0) / 12
        b = int(m.group(3)) + int(m.group(4) or 0) / 12
        return (a, b, "ft") if a > 0 and b > 0 else None
    m = METRIC.match(s.upper())
    if not m:
        return None
    a, b = float(m.group(1)), float(m.group(3))
    unit = (m.group(2) or m.group(4) or "").lower()
    if not unit:
        if "." in s:
            unit = "m?"
        elif min(a, b) > 60:
            unit = "cm?"
        else:
            return None        # 61-99 x 40: neither feet nor a believable room in centimetres
    f = TO_FT[unit.rstrip("?")]
    return (a * f, b * f, unit) if a > 0 and b > 0 else None


def parse_dims(s):
    r = parse_size(s)
    return r[:2] if r else None


def parse_area(s):
    """an area label (15.1 m², 15.1 sqm, 163 sq.ft, 1,172 SQ.FT) -> square feet"""
    m = AREA.match(s.replace(" ", "").upper())
    if not m:
        return None
    v = float(m.group(1).replace(",", ""))
    return v * (1 if "F" in m.group(2) else 1 / 0.3048 ** 2) if v > 0 else None


assert parse_dims("14'x12'8") == (14, 12 + 8 / 12) and parse_dims("5X6'8") == (5, 6 + 8 / 12)
assert parse_size("4.20 x 3.60 m")[2] == "m" and parse_size("420X360")[2] == "cm?" and parse_size("4200 x 3600 mm")[2] == "mm"
assert parse_size("4.2x3.6")[2] == "m?" and parse_size("14x12")[2] == "ft" and abs(parse_area("15.1 m²") - 162.5) < 0.1
assert parse_dims("11'4X4'4") and parse_dims('10\'-6"x12\'') == (10.5, 12) and room_type(["DRESS/TOI."]) == "toilet"


# ------------------------------------------------------------------ lines
def join_dashes(lines, gap):
    """join collinear pieces less than `gap` apart (dashed lines: ventilators, hidden edges)"""
    out = {}
    for o, ls in lines.items():
        by = defaultdict(list)
        for c, a0, a1 in ls:
            by[c].append((a0, a1))
        res = []
        for c, iv in by.items():
            iv.sort()
            a0, a1 = iv[0]
            for b0, b1 in iv[1:]:
                if b0 <= a1 + gap:
                    a1 = max(a1, b1)
                else:
                    res.append((c, a0, a1)); a0, a1 = b0, b1
            res.append((c, a0, a1))
        out[o] = res
    return out


def axis_lines(segs, min_len=1.0):
    """merge collinear axis-aligned segments -> {'h': [(c, a0, a1)], 'v': [...]}: c = fixed coord."""
    raw = {"h": defaultdict(list), "v": defaultdict(list)}
    for x0, y0, x1, y1, *_ in segs:
        if abs(y0 - y1) < 0.05 and abs(x1 - x0) > 0.05:
            raw["h"][round((y0 + y1) / 2, 1)].append((min(x0, x1), max(x0, x1)))
        elif abs(x0 - x1) < 0.05 and abs(y1 - y0) > 0.05:
            raw["v"][round((x0 + x1) / 2, 1)].append((min(y0, y1), max(y0, y1)))
    out = {}
    for o, by in raw.items():
        lines = []
        for c, iv in by.items():
            iv.sort()
            a0, a1 = iv[0]
            for b0, b1 in iv[1:]:
                if b0 <= a1 + 0.3:
                    a1 = max(a1, b1)
                else:
                    lines.append((c, a0, a1)); a0, a1 = b0, b1
            lines.append((c, a0, a1))
        out[o] = [l for l in lines if l[2] - l[1] >= min_len]
    return out


def nearest(lines, gmax):
    """for each line i and side (+1 above / -1 below): pieces [(a0, a1, j, gap)] of its nearest
    overlapping parallel line within gmax."""
    by_c = sorted(range(len(lines)), key=lambda i: lines[i][0])
    cs = [lines[i][0] for i in by_c]
    import bisect
    res = {}
    for i, (c, a0, a1) in enumerate(lines):
        for side in (1, -1):
            if side > 0:
                lo, hi = bisect.bisect_right(cs, c + 1e-6), bisect.bisect_right(cs, c + gmax)
                cand = [by_c[k] for k in range(lo, hi)]
            else:
                lo, hi = bisect.bisect_left(cs, c - gmax), bisect.bisect_left(cs, c - 1e-6)
                cand = [by_c[k] for k in range(lo, hi)][::-1]
            free, pieces = [(a0, a1)], []
            for j in cand:
                cj, b0, b1 = lines[j]
                nf = []
                for f0, f1 in free:
                    o0, o1 = max(f0, b0), min(f1, b1)
                    if o1 - o0 > 0.05:
                        pieces.append((o0, o1, j, abs(cj - c)))
                        if o0 > f0: nf.append((f0, o0))
                        if o1 < f1: nf.append((o1, f1))
                    else:
                        nf.append((f0, f1))
                free = nf
                if not free:
                    break
            res[i, side] = pieces
    return res


def wall_pairs(lines, gmax):
    """mutual-nearest line pairs that are not part of an evenly spaced hatch (windows, stairs, tiles).
    -> walls [(c0, c1, a0, a1)], hatch pieces [(c, a0, a1)]"""
    nb = nearest(lines, gmax)

    def at(i, side, a0, a1):
        """partner pieces of line i on side overlapping [a0, a1]"""
        return [(max(p0, a0), min(p1, a1), j, g) for p0, p1, j, g in nb[i, side] if min(p1, a1) - max(p0, a0) > 0.05]

    walls, hatch = [], []
    for i, (c, _, _) in enumerate(lines):
        for p0, p1, j, g in nb[i, 1]:
            for q0, q1, k, g2 in at(j, -1, p0, p1):     # mutual: j's nearest below is i
                if k != i:
                    continue
                # hatch test: another line at a similar spacing just beyond either side
                cut = [(r0, r1) for side, line in ((-1, i), (1, j))
                       for r0, r1, _, g3 in at(line, side, q0, q1) if abs(g3 - g) < 0.35 * g]
                pieces = [(q0, q1)]
                for r0, r1 in cut:
                    pieces = [x for a, b in pieces for x in ((a, min(b, r0)), (max(a, r1), b)) if x[1] - x[0] > 0.05]
                for a, b in pieces:
                    walls.append((c, lines[j][0], a, b))
                for r0, r1 in cut:
                    hatch.append((c, lines[j][0], max(q0, r0), min(q1, r1)))
    return walls, hatch


def boundary_lines(segs, s):
    """single drawn lines that can separate rooms (door thresholds, open-kitchen edges, floor-finish edges):
    axis lines >= 1.2 ft, minus evenly spaced families of the same pen (tile grids, hatches, treads, glass)."""
    by_pen = defaultdict(list)
    for g in segs:
        by_pen[g[4], round(g[5], 2)].append(g)
    out = {"h": [], "v": []}
    for (col, _), gs in by_pen.items():
        if 0.3 * col[0] + 0.59 * col[1] + 0.11 * col[2] > 190:
            continue        # pale pens: tile grids, outlines of colour fills
        L = axis_lines(gs, min_len=0.5)
        for o in ("h", "v"):
            lines = L[o]
            nb = nearest(lines, 5 * s)

            def gap(i, side):      # (gap, line) of the partner overlapping most of line i on this side
                c, a0, a1 = lines[i]
                best = max(nb[i, side], key=lambda p: p[1] - p[0], default=None)
                return (best[3], best[2]) if best and best[1] - best[0] > 0.5 * (a1 - a0) else (None, None)
            for i, (c, a0, a1) in enumerate(lines):
                if a1 - a0 < 1.2 * s:
                    continue
                (g1, j1), (g2, j2) = gap(i, 1), gap(i, -1)
                # CAD grids / hatches are exactly evenly spaced; rooms only by chance, so a tight tolerance
                eq = lambda a, b: a is not None and b is not None and abs(a - b) < 0.03 * max(a, b) + 0.3
                if eq(g1, g2) or (g1 and eq(g1, gap(j1, 1)[0])) or (g2 and eq(g2, gap(j2, -1)[0])):
                    continue        # one of >= 3 evenly spaced lines
                out[o].append((c, a0, a1))
    return out


def fill_columns(fills, walls, T):
    """solid-filled rectangles the size of a wall end (RCC columns), touching a wall -> wall rects.
    Fills come as triangles: same-colour triangles that touch are joined; a rectangle's pieces fill its bbox."""
    by_col = defaultdict(list)
    for pts, col in fills:
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        a = abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts)))) / 2
        by_col[col].append([min(xs), max(xs), min(ys), max(ys), a])
    out = []
    for tris in by_col.values():
        groups = [t[:] for t in tris]
        merged = True
        while merged:
            merged = False
            for i in range(len(groups)):
                for j in range(i + 1, len(groups)):
                    a, b = groups[i], groups[j]
                    if a[0] <= b[1] + 0.2 and b[0] <= a[1] + 0.2 and a[2] <= b[3] + 0.2 and b[2] <= a[3] + 0.2:
                        groups[i] = [min(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), max(a[3], b[3]), a[4] + b[4]]
                        groups.pop(j)
                        merged = True
                        break
                if merged:
                    break
                if len(groups) > 4000:
                    break
        for x0, x1, y0, y1, a in groups:
            w, h = x1 - x0, y1 - y0
            if 0.8 * T <= min(w, h) and max(w, h) <= 6 * T and abs(a - w * h) < 0.08 * w * h and \
                    any(x0 <= r[1] + 0.5 * T and r[0] <= x1 + 0.5 * T and y0 <= r[3] + 0.5 * T and r[2] <= y1 + 0.5 * T
                        for r in walls):
                out.append((x0, x1, y0, y1))
    return out


def thickness_mode(walls):
    """length-weighted mode of the pair gaps (the main wall thickness, in points)."""
    h = defaultdict(float)
    for c0, c1, a0, a1 in walls:
        h[round(c1 - c0, 1)] += a1 - a0
    best = max(h, key=lambda g: sum(v for k, v in h.items() if abs(k - g) <= 0.3))
    return best


# ------------------------------------------------------------------ geometry in plan units
def rect(o, w):
    """wall/hatch tuple in its orientation -> (x0, x1, y0, y1) page points"""
    c0, c1, a0, a1 = w
    return (a0, a1, c0, c1) if o == "h" else (c0, c1, a0, a1)


def merge_rects(rs, tol=0.2):
    """join rects that share a full edge (same band, touching or overlapping along the axis)."""
    rs = list(rs)
    changed = True
    while changed:
        changed = False
        out = []
        for r in rs:
            for k, q in enumerate(out):
                same_y = abs(r[2] - q[2]) < tol and abs(r[3] - q[3]) < tol
                same_x = abs(r[0] - q[0]) < tol and abs(r[1] - q[1]) < tol
                if same_y and r[0] <= q[1] + tol and q[0] <= r[1] + tol:
                    out[k] = (min(r[0], q[0]), max(r[1], q[1]), min(r[2], q[2]), max(r[3], q[3])); changed = True; break
                if same_x and r[2] <= q[3] + tol and q[2] <= r[3] + tol:
                    out[k] = (min(r[0], q[0]), max(r[1], q[1]), min(r[2], q[2]), max(r[3], q[3])); changed = True; break
            else:
                out.append(r)
        rs = out
    return rs


def cut_windows(walls, lines, T, cuts):
    """glass / frame lines (any pen) running inside a wall band mark a window: cut that span out of the wall
    (the spans are appended to `cuts` as (rect, orientation))."""
    out = []
    for w in walls:
        o = "h" if horiz(w) else "v"
        lo, hi, b0, b1 = (w[0], w[1], w[2], w[3]) if o == "h" else (w[2], w[3], w[0], w[1])
        spans = sorted((max(a0, lo), min(a1, hi)) for c, a0, a1 in lines[o]
                       if b0 + 0.12 * (b1 - b0) < c < b1 - 0.12 * (b1 - b0) and a1 - a0 >= 3 * T
                       and a0 >= lo - 0.5 and a1 <= hi + 0.5)
        pieces = [(lo, hi)]
        for a0, a1 in spans:
            pieces = [x for p0, p1 in pieces for x in ((p0, min(p1, a0)), (max(p0, a1), p1)) if x[1] - x[0] > 0.3]
            cuts.append(((a0, a1, b0, b1) if o == "h" else (b0, b1, a0, a1), o))
        out += [(p0, p1, b0, b1) if o == "h" else (b0, b1, p0, p1) for p0, p1 in pieces]
    return out


def pale(col):
    return 0.3 * col[0] + 0.59 * col[1] + 0.11 * col[2] > 190


def fill_outlines(fills):
    """edges of the pale colour fills (floor finishes), keyed by colour and end points rounded to 0.1 pt"""
    out = set()
    for pts, col in fills:
        if not isinstance(col, tuple) or not pale(col):
            continue
        for a, b in zip(pts, pts[1:] + pts[:1]):
            p, q = (round(a[0], 1), round(a[1], 1)), (round(b[0], 1), round(b[1], 1))
            out.add((col, min(p, q), max(p, q)))
    return out


def is_outline(g, outline):
    """a stroke in a fill's own pale colour along that fill's edge outlines the fill (a floor colour running into
    a doorway): it is not a glass or frame line, and two of them made bare doorways look like windows"""
    p, q = (round(g[0], 1), round(g[1], 1)), (round(g[2], 1), round(g[3], 1))
    return (g[4], min(p, q), max(p, q)) in outline


def horiz(r):
    return (r[1] - r[0]) >= (r[3] - r[2])


def close_corners(walls, T0):
    """extend wall ends into a perpendicular wall that stops just short of them (L / T corners)."""
    out = []
    for r in walls:
        x0, x1, y0, y1 = r
        for q in walls:
            if q is r or horiz(q) == horiz(r):
                continue
            # (reach across the perpendicular wall's own thickness: outer walls can be twice the main one)
            T = max(T0, min(q[1] - q[0], q[3] - q[2]))
            if horiz(r):
                if q[2] - 1.2 * T <= y1 and y0 <= q[3] + 1.2 * T:      # q spans our band (or nearly)
                    if -0.2 <= q[1] - x0 and x0 - q[0] <= 1.6 * T + 0.2 and q[0] < x0:   # left end
                        x0 = min(x0, q[0])
                    if -0.2 <= x1 - q[0] and q[1] - x1 <= 1.6 * T + 0.2 and q[1] > x1:
                        x1 = max(x1, q[1])
            else:
                if q[0] - 1.2 * T <= x1 and x0 <= q[1] + 1.2 * T:
                    if -0.2 <= q[3] - y0 and y0 - q[2] <= 1.6 * T + 0.2 and q[2] < y0:
                        y0 = min(y0, q[2])
                    if -0.2 <= y1 - q[2] and q[3] - y1 <= 1.6 * T + 0.2 and q[3] > y1:
                        y1 = max(y1, q[3])
        out.append((x0, x1, y0, y1))
    return out


# ------------------------------------------------------------------ arcs (door swings)
def arcs(curves):
    """cubic bezier quarter-arcs -> (cx, cy, r, p0, p1): center from the end tangents' normals."""
    out = []
    for p0, p1, p2, p3, *_ in curves:
        t0 = (p1[0] - p0[0], p1[1] - p0[1])
        t1 = (p3[0] - p2[0], p3[1] - p2[1])
        # center c: (c - p0).t0 = 0 and (c - p3).t1 = 0
        det = t0[0] * t1[1] - t0[1] * t1[0]
        if abs(det) < 1e-9:
            continue
        b0 = t0[0] * p0[0] + t0[1] * p0[1]
        b1 = t1[0] * p3[0] + t1[1] * p3[1]
        cx = (b0 * t1[1] - b1 * t0[1]) / det
        cy = (t0[0] * b1 - t1[0] * b0) / det
        r0, r1 = math.dist((cx, cy), p0), math.dist((cx, cy), p3)
        if r0 < 1 or abs(r0 - r1) > 0.08 * r0:
            continue
        out.append((cx, cy, (r0 + r1) / 2, p0, p3))
    # merge pieces of the same circle
    merged = []
    for a in out:
        for k, b in enumerate(merged):
            if math.dist(a[:2], b[0][:2]) < 0.05 * a[2] and abs(a[2] - b[0][2]) < 0.05 * a[2]:
                b[1].extend([a[3], a[4]]); break
        else:
            merged.append([a, [a[3], a[4]]])
    res = []
    for a, pts in merged:
        cx, cy, r = a[:3]
        angs = sorted(math.atan2(p[1] - cy, p[0] - cx) for p in pts)
        res.append((cx, cy, r, pts))
    return res


def wall_pens(segs):
    """stroke styles that can draw walls: CAD draws walls with the heaviest pen. Styles carrying >= 5% of the
    axis-aligned ink, and at least 60% as wide as the widest such style (thin tile grids / hatches drop out)."""
    ink = defaultdict(float)
    for x0, y0, x1, y1, col, w in segs:
        if abs(x0 - x1) < 0.05 or abs(y0 - y1) < 0.05:
            ink[col, round(w, 2)] += abs(x1 - x0) + abs(y1 - y0)
    total = sum(ink.values()) or 1
    big = {k: v for k, v in ink.items() if v >= 0.05 * total}
    if not big:
        return set()        # nothing stroked along the axes (walls may be solid bands: band_segs)
    wmax = max(k[1] for k in big)
    pens = {k for k in ink if k[1] >= 0.6 * wmax}
    # walls are plotted in black / grey; coloured wide pens are window frames, columns, beams
    grey = {k for k in pens if isinstance(k[0], tuple) and max(k[0]) - min(k[0]) < 30}
    if sum(ink[k] for k in grey) >= 0.5 * sum(ink[k] for k in pens):
        pens = grey
    return pens


def band_segs(fills):
    """the outlines of solid dark fills as line segments. Some exporters (presentation sheets, our own plan
    generator) draw a wall as a filled band with no outline pen: the band's two faces are then the edges of the
    fill, and they pair up like double-line walls. Only colours darker than mid grey that carry a good share of
    the dark area: pale fills are rooms and paper, a little dark ink is furniture detail or arrow heads."""
    area = defaultdict(float)
    for pts, col in fills:
        if isinstance(col, tuple) and 0.3 * col[0] + 0.59 * col[1] + 0.11 * col[2] < 128:
            area[col] += abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts)))) / 2
    cols = {c for c, a in area.items() if a >= 0.25 * max(area.values())}
    return [(*p, *q, col, 0.0) for pts, col in fills if col in cols for p, q in zip(pts, pts[1:] + pts[:1])]


# ------------------------------------------------------------------ text
def phrases(words):
    """join words into phrases (same line, small gap); vertical text is joined top-to-bottom."""
    ws = sorted(words, key=lambda w: (round((w[1] + w[3]) / 2), w[0]))
    out = []
    for x0, y0, x1, y1, t in ws:
        vert = (y1 - y0) > 1.6 * (x1 - x0) and len(t) > 2
        for p in out:
            if p["vert"] != vert:
                continue
            h = min(p["h"], (x1 - x0) if vert else (y1 - y0))
            if not vert and abs((p["y0"] + p["y1"]) / 2 - (y0 + y1) / 2) < 0.4 * h and -0.5 * h < x0 - p["x1"] < 1.2 * h:
                p.update(x1=x1, text=p["text"] + " " + t); break
            if vert and abs((p["x0"] + p["x1"]) / 2 - (x0 + x1) / 2) < 0.4 * h and -0.5 * h < y0 - p["y1"] < 1.2 * h:
                p.update(y1=y1, text=t + " " + p["text"]); break     # CAD vertical text reads bottom-to-top
        else:
            out.append(dict(x0=x0, y0=y0, x1=x1, y1=y1, text=t, vert=vert, h=(x1 - x0) if vert else (y1 - y0)))
    for p in out:
        p["cx"], p["cy"] = (p["x0"] + p["x1"]) / 2, (p["y0"] + p["y1"]) / 2
        size = parse_size(p["text"])
        p["dims"], p["unit"] = (size[:2], size[2]) if size else (None, None)
        p["area"] = None if size else parse_area(p["text"])
    return out


# ------------------------------------------------------------------ floors (one sheet can hold several plans)
def clusters(walls, gap):
    parent = list(range(len(walls)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, a in enumerate(walls):
        for j in range(i + 1, len(walls)):
            b = walls[j]
            if a[0] - gap <= b[1] and b[0] - gap <= a[1] and a[2] - gap <= b[3] and b[2] - gap <= a[3]:
                parent[find(i)] = find(j)
    groups = defaultdict(list)
    for i, w in enumerate(walls):
        groups[find(i)].append(w)
    return list(groups.values())


def plan_groups(walls, T):
    """touching walls form fragments; fragments whose bounding boxes overlap belong to the same plan."""
    groups = [(bbox(c), c) for c in clusters(walls, 1.5 * T)]
    merged = True
    while merged:
        merged = False
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                a, b = groups[i][0], groups[j][0]
                if a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]:
                    c = groups[i][1] + groups[j][1]
                    groups[i] = (bbox(c), c)
                    groups.pop(j)
                    merged = True
                    break
            if merged:
                break
    return [g[1] for g in groups]


def same_line(a, b, T, most=14.0):
    """two wall pieces of one wall line: the same band (faces within 0.2 T) and end to end with a gap of at most
    `most` wall thicknesses (a door or a window)"""
    if horiz(a) != horiz(b):
        return False
    if horiz(a):
        band = abs(a[2] - b[2]) < 0.2 * T and abs(a[3] - b[3]) < 0.2 * T
        gap = max(b[0] - a[1], a[0] - b[1])
    else:
        band = abs(a[0] - b[0]) < 0.2 * T and abs(a[1] - b[1]) < 0.2 * T
        gap = max(b[2] - a[3], a[2] - b[3])
    return band and 0 <= gap <= most * T


def opening_links(walls, lines, arcs_, T):
    """the gap between two pieces of one wall band that holds a door swing or window glass. Drawings that cut
    their walls at every door and window (solid wall bands) leave the pieces of one house touching only across
    its openings: these gaps tie the pieces to one plan."""
    out = []
    for a in walls:
        o = "h" if horiz(a) else "v"
        lo, hi, b0, b1 = (a[0], a[1], a[2], a[3]) if o == "h" else (a[2], a[3], a[0], a[1])
        nxt = min((c[0] if o == "h" else c[2] for c in walls if c is not a and horiz(c) == horiz(a)
                   and abs((c[2] if o == "h" else c[0]) - b0) < 0.2 * T and abs((c[3] if o == "h" else c[1]) - b1) < 0.2 * T
                   and (c[0] if o == "h" else c[2]) > hi + 0.3), default=None)
        if nxt is None or nxt - hi > 40 * T:
            continue
        r = (hi, nxt, b0, b1) if o == "h" else (b0, b1, hi, nxt)
        if classify(r, o, lines, arcs_, T, None)[0] != "opening":
            out.append(r)
    return out


def overlap_rect(a, b, m=0.0):
    return a[0] < b[1] + m and b[0] < a[1] + m and a[2] < b[3] + m and b[2] < a[3] + m


def bbox(rs):
    return (min(r[0] for r in rs), max(r[1] for r in rs), min(r[2] for r in rs), max(r[3] for r in rs))


def inside(p, b, m=0.0):
    return b[0] - m <= p[0] <= b[1] + m and b[2] - m <= p[1] <= b[3] + m


# ------------------------------------------------------------------ scale
def scale_from_labels(walls, phr, T=None):
    """points per foot: distance between the walls around a room label vs the size written in it.
    CAD drawings write the clear size (between the wall faces); generated plans write the size between the wall
    centre lines. Both are measured; the reading more labels agree on wins (the clear size on a tie).
    Labels in metres, centimetres or millimetres count as their feet (parse_size). When most labels do not say their
    unit, T (the main wall thickness in points) settles it: the reading that gives a believable wall wins. Without any
    size label, room areas (15.1 m², 163 sq.ft) give the scale, if at least two rooms agree."""
    s, est = _scale_from_sizes(walls, phr)
    units = [p.get("unit") for p in phr if p["dims"]]
    guessed = [u for u in units if u and u.endswith("?")]
    if s and T and len(guessed) > len(units) / 2:
        # the other reading is 10x off (cm vs mm) or 3.28x off (decimals in metres vs feet)
        f = 10.0 if max(set(guessed), key=guessed.count) == "cm?" else 1 / 0.3048
        ok = lambda v: 0.33 <= T / v <= 1.6        # a main wall between 4 and 19 inches
        if not ok(s) and ok(s * f):
            s *= f
    if s is None:
        area_est = []
        for p in phr:
            if p.get("area"):
                box = _room_box(walls, p)
                if box:
                    area_est.append(((box[1] - box[0]) * (box[3] - box[2]) / p["area"]) ** 0.5)
        if len(area_est) >= 2:
            best = max(area_est, key=lambda e: (sum(abs(f - e) < 0.02 * e for f in area_est), -e))
            good = [e for e in area_est if abs(e - best) < 0.02 * best]
            if len(good) >= 2:
                return sum(good) / len(good), area_est
    return s, est


def _room_box(walls, p):
    """the clear box between the nearest walls left, right, above and below a label, or None"""
    cx, cy = p["cx"], p["cy"]
    L = max((w[1] for w in walls if w[2] <= cy <= w[3] and w[1] <= cx), default=None)
    R = min((w[0] for w in walls if w[2] <= cy <= w[3] and w[0] >= cx), default=None)
    U = max((w[3] for w in walls if w[0] <= cx <= w[1] and w[3] <= cy), default=None)
    D = min((w[2] for w in walls if w[0] <= cx <= w[1] and w[2] >= cy), default=None)
    return None if None in (L, R, U, D) else (L, R, U, D)


def _scale_from_sizes(walls, phr):
    reads = []
    for centre in (False, True):
        est = []
        for p in phr:
            if not p["dims"]:
                continue
            cx, cy = p["cx"], p["cy"]
            L = max((w for w in walls if w[2] <= cy <= w[3] and w[1] <= cx), key=lambda w: w[1], default=None)
            R = min((w for w in walls if w[2] <= cy <= w[3] and w[0] >= cx), key=lambda w: w[0], default=None)
            U = max((w for w in walls if w[0] <= cx <= w[1] and w[3] <= cy), key=lambda w: w[3], default=None)
            D = min((w for w in walls if w[0] <= cx <= w[1] and w[2] >= cy), key=lambda w: w[2], default=None)
            if None in (L, R, U, D):
                continue
            if centre:
                w, h = (R[0] + R[1] - L[0] - L[1]) / 2, (D[2] + D[3] - U[2] - U[3]) / 2
            else:
                w, h = R[0] - L[1], D[2] - U[3]
            a, b = p["dims"]
            for r1, r2 in ((w / a, h / b), (w / b, h / a)):
                if abs(r1 - r2) < 0.03 * max(r1, r2):
                    est.append((r1 + r2) / 2)
        good = []
        if len(est) >= 2:
            # mode: the estimate with the most others within 2% (rays leaking through openings give scattered values)
            best = max(est, key=lambda e: (sum(abs(f - e) < 0.02 * e for f in est), -e))
            good = [e for e in est if abs(e - best) < 0.02 * best]
        reads.append((len(good) if len(good) >= 2 else 0, good, est))
    n, good, est = max(reads, key=lambda r: r[0])       # (max keeps the first, the clear size, on a tie)
    return (sum(good) / n, est) if n else (None, reads[0][2])


# ------------------------------------------------------------------ openings
def openings(walls, lines, arcs_, T, s, bl):
    """gaps along a wall line -> doors / windows / plain openings. s = points per foot, bl = boundary lines."""
    out = []
    for o in ("h", "v"):
        for a in (w for w in walls if horiz(w) == (o == "h") and not is_column(w, T)):
            # in the wall's own frame: along = (lo, hi), band = (b0, b1)
            lo, hi, b0, b1 = (a[0], a[1], a[2], a[3]) if o == "h" else (a[2], a[3], a[0], a[1])
            for d in (1, -1):        # the gap after the wall's high end, and before its low end
                end, corner, skip = (hi if d > 0 else lo), False, {id(a)}
                while True:
                    best, closer = None, None
                    for c in walls:
                        clo, chi, cb0, cb1 = (c[0], c[1], c[2], c[3]) if o == "h" else (c[2], c[3], c[0], c[1])
                        if id(c) in skip or cb0 >= b1 - 0.2 * T or cb1 <= b0 + 0.2 * T:
                            continue
                        if clo - 0.3 <= end <= chi + 0.3:      # this end runs into another wall: closed
                            closer = (c, clo, chi)
                            break
                        g = clo - end if d > 0 else end - chi
                        if g > 0 and (best is None or g < best[0]):
                            best = (g, c, cb0, cb1)
                    if closer is None:
                        break
                    c, clo, chi = closer
                    # an L corner where our wall stops: the gap may continue straight past the corner
                    if horiz(c) != horiz(a) and not corner and (abs(chi - end) < 1.6 * T if d > 0 else abs(clo - end) < 1.6 * T):
                        end, corner = (chi if d > 0 else clo), True
                        skip.add(id(c))
                        continue
                    best = None
                    break
                if not best or not 1.4 <= best[0] / s <= 12.5:
                    continue
                g, c, cb0, cb1 = best
                same_line = horiz(c) == horiz(a)
                band = (max(b0, cb0), min(b1, cb1)) if same_line else (b0, b1)
                g0 = end if d > 0 else end - g
                r = (g0, g0 + g, *band) if o == "h" else (band[0], band[1], g0, g0 + g)
                kind, info = classify(r, o, lines, arcs_, T, s)
                if corner and not (info.get("glass") or info.get("leaves") or threshold(r, o, bl, T)):
                    continue      # past a corner we need a drawn sill / threshold line as evidence
                if kind == "opening":
                    # many drawings show doors as a bare gap: in a straight wall, or closed by a drawn line
                    # (a wall end facing a side wall with nothing drawn between is just a passage)
                    if g / s <= 4.6 and threshold(r, o, bl, T):
                        kind, info = "door", dict(leaves=[])
                    elif not (same_line and g / s <= 8):
                        continue
                out.append(dict(type=kind, rect=r, axis=o, **info))
    return out


def is_column(w, T):
    a, b = sorted((w[1] - w[0], w[3] - w[2]))
    return b <= 3.2 * T and a >= 0.55 * b


def threshold(r, o, lines, T):
    """a line drawn along the wall band (on a face or inside) across most of the gap"""
    lo, hi, b0, b1 = (r[0], r[1], r[2], r[3]) if o == "h" else (r[2], r[3], r[0], r[1])
    return any(b0 - 0.3 * T <= c <= b1 + 0.3 * T and min(a1, hi) - max(a0, lo) > 0.7 * (hi - lo) for c, a0, a1 in lines[o])


def classify(r, o, lines, arcs_, T, s):
    lo, hi, b0, b1 = (r[0], r[1], r[2], r[3]) if o == "h" else (r[2], r[3], r[0], r[1])
    g = hi - lo
    # glass lines: parallel lines strictly inside the wall band covering most of the gap
    # (glass ends at the jambs; floor-tile grid lines run on through; ventilators are drawn dashed)
    cs = sorted(c for c, a0, a1 in lines[o]       # (frame lines may sit on the faces)
                if b0 - 0.1 * T < c < b1 + 0.1 * T and min(a1, hi) - max(a0, lo) > 0.5 * g
                and a0 > lo - 2 * T and a1 < hi + 2 * T)
    glass = sum(1 for k, c in enumerate(cs) if k == 0 or c - cs[k - 1] > 0.2 * T)   # one per position (pens overlap)
    # door swing arcs hinged at one end of the gap
    leaves = []
    for cx, cy, rad, pts in arcs_:
        along, across = (cx, cy) if o == "h" else (cy, cx)
        if not (b0 - 1.5 * T <= across <= b1 + 1.5 * T):
            continue
        for end in (lo, hi):
            if abs(along - end) < 1.2 * T and (0.7 * g <= rad <= 1.2 * g or 0.38 * g <= rad <= 0.62 * g):
                # a leaf line from the hinge along this gap that stops short of the far jamb (or at its middle)
                # is the open leaf of a door in the wall meeting this one at the hinge: same corner, same arc
                tip, far = along + (rad if end == lo else -rad), (hi if end == lo else lo)
                if (rad < 0.62 * g or abs(tip - far) > 0.6 * T) and any(
                        abs(c - across) < 0.3 * T and a0 < min(along, tip) + 0.3 * T and a1 > max(along, tip) - 0.3 * T
                        for c, a0, a1 in lines[o]):
                    continue
                # swing side: where the arc points lie relative to the band
                side = sum((p[1] if o == "h" else p[0]) - (b0 + b1) / 2 for p in pts)
                leaves.append(dict(hinge=(cx, cy), radius=rad, side=1 if side > 0 else -1, at=end))
    if leaves:
        return "door", dict(leaves=leaves[:2])
    if glass >= 2:      # frame + glass lines stop at the jambs (wall faces and floor-tile joints run on through)
        return "window", dict(glass=glass)
    return "opening", {}


# ------------------------------------------------------------------ rooms
def flood_rooms(walls, blocks, box, cell):
    """label the free cells enclosed by walls+openings. -> (grid of region ids, regions{id: cells}, outside id)"""
    x0, x1, y0, y1 = box
    nx, ny = int((x1 - x0) / cell) + 3, int((y1 - y0) / cell) + 3
    ox, oy = x0 - cell, y0 - cell
    grid = [bytearray(nx) for _ in range(ny)]
    for r in walls + blocks:
        i0, i1 = max(0, int((r[0] - ox) / cell)), min(nx - 1, int((r[1] - ox) / cell))
        j0, j1 = max(0, int((r[2] - oy) / cell)), min(ny - 1, int((r[3] - oy) / cell))
        for j in range(j0, j1 + 1):
            grid[j][i0:i1 + 1] = b"\x01" * (i1 - i0 + 1)
    lab = [[0] * nx for _ in range(ny)]
    regions, nid = {}, 0
    from collections import deque
    for sj in range(ny):
        for si in range(nx):
            if grid[sj][si] or lab[sj][si]:
                continue
            nid += 1
            q, cells = deque([(si, sj)]), []
            lab[sj][si] = nid
            while q:
                i, j = q.popleft()
                cells.append((i, j))
                for a, b in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                    if 0 <= a < nx and 0 <= b < ny and not grid[b][a] and not lab[b][a]:
                        lab[b][a] = nid
                        q.append((a, b))
            regions[nid] = cells
    return dict(lab=lab, regions=regions, outside=lab[0][0], ox=ox, oy=oy, cell=cell, nx=nx, ny=ny)


def region_rects(cells, F):
    """cells of one region -> few axis-aligned rects (page points), rows merged greedily."""
    rows = defaultdict(list)
    for i, j in cells:
        rows[j].append(i)
    runs = {}
    for j, xs in rows.items():
        xs.sort()
        rr, a = [], xs[0]
        for k in range(1, len(xs)):
            if xs[k] != xs[k - 1] + 1:
                rr.append((a, xs[k - 1])); a = xs[k]
        rr.append((a, xs[-1]))
        runs[j] = rr
    rects, open_ = [], {}
    for j in sorted(runs):
        cur = {}
        for run in runs[j]:
            if run in open_ and open_[run][1] == j - 1:
                cur[run] = (open_[run][0], j)
            else:
                cur[run] = (j, j)
        for run, (j0, j1) in open_.items():
            if run not in cur or cur[run][0] != j0:
                rects.append((run, j0, j1))
        open_ = cur
    rects += [(run, j0, j1) for run, (j0, j1) in open_.items()]
    c, ox, oy = F["cell"], F["ox"], F["oy"]
    return [(ox + a * c, ox + (b + 1) * c, oy + j0 * c, oy + (j1 + 1) * c) for (a, b), j0, j1 in rects]


def line_cells(bl, C, ox, oy):
    """grid cells under the boundary lines (each stretched one cell at both ends to close tiny gaps)"""
    out = set()
    for c, a0, a1 in bl["h"]:
        j = int((c - oy) / C)
        out.update((i, j) for i in range(int((a0 - ox) / C) - 1, int((a1 - ox) / C) + 2))
    for c, a0, a1 in bl["v"]:
        i = int((c - ox) / C)
        out.update((i, j) for j in range(int((a0 - oy) / C) - 1, int((a1 - oy) / C) + 2))
    return out


def fine_parts(cells, seed_cells, line):
    """split a walled region along drawn lines, then merge every unlabeled piece into the neighbour it shares the
    longest line with (furniture outlines, tile edges...). -> [(cells, [seed indices])], each with a seed."""
    from collections import deque
    cellset, comp, parts = set(cells), {}, []
    nbrs = lambda q: ((q[0] + 1, q[1]), (q[0] - 1, q[1]), (q[0], q[1] + 1), (q[0], q[1] - 1))
    for q in cells:
        if q in line or q in comp:
            continue
        comp[q], stack, part = len(parts), [q], []
        while stack:
            a = stack.pop()
            part.append(a)
            for b in nbrs(a):
                if b in cellset and b not in line and b not in comp:
                    comp[b] = comp[q]
                    stack.append(b)
        parts.append(part)
    if not parts:
        return [(cells, list(range(len(seed_cells))))]
    fr = deque(comp)            # line cells join the piece beside them
    while fr:
        a = fr.popleft()
        for b in nbrs(a):
            if b in cellset and b not in comp:
                comp[b] = comp[a]
                parts[comp[a]].append(b)
                fr.append(b)
    nb = defaultdict(lambda: defaultdict(int))
    for a in cells:
        for b in ((a[0] + 1, a[1]), (a[0], a[1] + 1)):
            if b in comp and comp[b] != comp[a]:
                nb[comp[a]][comp[b]] += 1
                nb[comp[b]][comp[a]] += 1
    lab = defaultdict(list)
    for k, sc in enumerate(seed_cells):
        lab[comp.get(sc, 0)].append(k)
    alive = set(range(len(parts)))
    while True:
        un = [k for k in alive if not lab[k] and nb[k]]
        if not un:
            break
        u = min(un, key=lambda k: len(parts[k]))
        v = max(nb[u], key=nb[u].get)
        for w, n in nb.pop(u).items():
            del nb[w][u]
            if w != v:
                nb[v][w] += n
                nb[w][v] += n
        parts[v] += parts[u]
        alive.remove(u)
    return [(parts[k], lab[k]) for k in alive if lab[k]]


def split_zones(cells, idx, seeds, lines, C, ox, oy, out):
    """split an open-plan region between its name labels with straight cuts, preferring a drawn line
    (floor-finish edge) between the labels, else the midpoint. Recursive; out[seed index] = cells."""
    if len(idx) == 1:
        out[idx[0]] = cells
        return
    xs = [ox + (i + 0.5) * C for i, j in cells]
    ys = [oy + (j + 0.5) * C for i, j in cells]
    ext = {"v": (min(ys), max(ys)), "h": (min(xs), max(xs))}
    best = None
    for o, k in (("v", 0), ("h", 1)):        # 'v' line = cut at constant x
        order = sorted(idx, key=lambda q: seeds[q][k])
        for a, b in zip(order, order[1:]):
            lo, hi = seeds[a][k], seeds[b][k]
            if hi - lo < 2 * C:
                continue
            e0, e1 = ext[o]
            cand = [(min(a1, e1) - max(a0, e0), c) for c, a0, a1 in lines[o] if lo < c < hi]
            cov, c = max(cand, default=(0, (lo + hi) / 2))
            frac = cov / max(e1 - e0, 1e-6)
            if frac < 0.3:
                c, frac = (lo + hi) / 2, 0
            n_lo = sum(1 for q in idx if seeds[q][k] < c)
            span = (max(xs) - min(xs)) if k == 0 else (max(ys) - min(ys))
            score = frac + 0.3 * min(n_lo, len(idx) - n_lo) / len(idx) + 0.5 * (hi - lo) / max(span, 1e-6)
            if not best or score > best[0]:
                best = (score, k, c)
    if not best:
        # labels on top of each other: nearest label
        for q in idx:
            out[q] = []
        for i, j in cells:
            x, y = ox + (i + 0.5) * C, oy + (j + 0.5) * C
            out[min(idx, key=lambda q: (x - seeds[q][0]) ** 2 + (y - seeds[q][1]) ** 2)].append((i, j))
        return
    _, k, c = best
    lo_cells = [(i, j) for i, j in cells if (ox + (i + 0.5) * C if k == 0 else oy + (j + 0.5) * C) < c]
    hi_cells = [(i, j) for i, j in cells if (ox + (i + 0.5) * C if k == 0 else oy + (j + 0.5) * C) >= c]
    split_zones(lo_cells, [q for q in idx if seeds[q][k] < c], seeds, lines, C, ox, oy, out)
    split_zones(hi_cells, [q for q in idx if seeds[q][k] >= c], seeds, lines, C, ox, oy, out)


# ------------------------------------------------------------------ stairs
def stair_flights(hatch, T, s, phr):
    """runs of evenly spaced parallel treads (0.6-1.3 ft apart, 2.5-6 ft long) next to an UP / DN word."""
    groups = []
    for o in ("h", "v"):
        # join dashed pieces of the same strip (hidden upper flights are drawn dashed)
        strips = defaultdict(list)
        for c0, c1, a0, a1 in hatch[o]:
            strips[round(c0, 1), round(c1, 1)].append((a0, a1))
        hs = []
        for (c0, c1), iv in strips.items():
            iv.sort()
            a0, a1 = iv[0]
            for b0, b1 in iv[1:]:
                if b0 <= a1 + 2 * T:
                    a1 = max(a1, b1)
                else:
                    hs.append((c0, c1, a0, a1)); a0, a1 = b0, b1
            hs.append((c0, c1, a0, a1))
        hs.sort(key=lambda h: h[0])
        for c0, c1, a0, a1 in hs:
            sp, ln = (c1 - c0) / s, (a1 - a0) / s
            if not (0.55 <= sp <= 1.35 and 2.4 <= ln <= 7):
                continue
            for gr in groups:
                if gr["o"] == o and abs(gr["a0"] - a0) < T and abs(gr["a1"] - a1) < T and abs(gr["c1"] - c0) < 0.5:
                    gr["c1"] = c1; gr["n"] += 1; break
            else:
                groups.append(dict(o=o, a0=a0, a1=a1, c0=c0, c1=c1, n=1))
    words = [p for p in phr if p["text"].strip(".").upper() in ("UP", "DN", "DOWN")]
    fl = []
    for gr in groups:
        if gr["n"] < 4:
            continue
        r = (gr["a0"], gr["a1"], gr["c0"], gr["c1"]) if gr["o"] == "h" else (gr["c0"], gr["c1"], gr["a0"], gr["a1"])
        near = [p for p in words if inside((p["cx"], p["cy"]), r, 4 * s)]
        if near:
            fl.append(dict(rect=r, axis="y" if gr["o"] == "h" else "x", n=gr["n"] + 1,
                           up=any(p["text"].upper().startswith("UP") for p in near),
                           words=[(p["text"].upper(), p["cx"], p["cy"]) for p in near]))
    return fl


# ------------------------------------------------------------------ main
def detect_page(page):
    pens = wall_pens(page["segs"])
    L = axis_lines([s for s in page["segs"] if (s[4], round(s[5], 2)) in pens])
    ALL = axis_lines(page["segs"], min_len=0.5)
    gmax = 0.025 * math.hypot(page["width"], page["height"])
    walls = {o: wall_pairs(L[o], gmax)[0] for o in ("h", "v")}
    # walls drawn as solid bands: read the fills' outlines instead when they pair up into clearly more wall
    band = band_segs(page["fills"])
    BL_ = axis_lines(band)
    bwalls = {o: wall_pairs(BL_[o], gmax)[0] for o in ("h", "v")}
    run = lambda ws: sum(w[3] - w[2] for o in ("h", "v") for w in ws[o])
    solid = run(bwalls) > 1.5 * run(walls)
    if solid:
        walls = bwalls
    _, hatch_all = zip(*(wall_pairs(ALL[o], gmax) for o in ("h", "v")))
    hatch_all = dict(h=hatch_all[0], v=hatch_all[1])
    if not walls["h"] + walls["v"]:
        raise PlanError("no walls found (need double-line walls or solid wall bands)")
    T = thickness_mode(walls["h"] + walls["v"])
    by_pen = defaultdict(list)          # lines per pen with dashes joined (a window frame drawn on a wall face stays its own line)
    outline = fill_outlines(page["fills"])
    for g in page["segs"]:
        if not is_outline(g, outline):
            by_pen[g[4], round(g[5], 2)].append(g)
    PEN = {"h": [], "v": []}
    for gs in by_pen.values():
        for o, ls in join_dashes(axis_lines(gs, min_len=0.5), 0.8 * T).items():
            PEN[o] += ls
    W = [rect(o, w) for o in ("h", "v") for w in walls[o] if 0.45 * T <= w[1] - w[0] <= 2.6 * T and w[3] - w[2] >= 0.8 * T]
    W = merge_rects(W)
    W_solid = W                                  # windows not cut yet: label rays stop at window walls
    CUTS = []
    W = [w for w in cut_windows(W, PEN, T, CUTS) if max(w[1] - w[0], w[3] - w[2]) >= 0.5 * T]   # keep jambs beside windows
    # (with solid walls, only the wall colour can be a column: pale furniture fills stand against walls too)
    W += fill_columns([f for f in page["fills"] if f[1] in {g[4] for g in band}] if solid else page["fills"], W, T)
    phr = phrases(page["words"])
    A = arcs(page["curves"])
    groups = plan_groups(W, T)
    named = lambda g: sum(1 for p in phr if inside((p["cx"], p["cy"]), bbox(g)) and room_type([p["text"]]))
    # pieces of one wall line broken by doors and windows (drawn with another pen, so not joined into one wall):
    # walls in the same band, end to end across a gap of an opening's width, belong to one plan
    for _ in range(len(groups)):
        merged = False
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                # (two groups that each hold a plan's room names are two plans side by side, not one)
                if min(named(groups[i]), named(groups[j])) < 2 and any(same_line(a, b, T) for a in groups[i] for b in groups[j]):
                    groups[i] = groups[i] + groups[j]
                    del groups[j]
                    merged = True
                    break
            if merged:
                break
        if not merged:
            break
    for r in opening_links(W, PEN, A, T):     # pieces of one wall either side of a door or window: one plan
        hit = [g for g in groups if any(overlap_rect(r, w, 0.5) for w in g)]
        if len(hit) > 1:
            groups = [g for g in groups if all(g is not h for h in hit)] + [sum(hit, [])]
    # floors: wall clusters that contain at least two room names
    floors = []
    for cl in groups:
        b = bbox(cl)
        names = [p for p in phr if inside((p["cx"], p["cy"]), b) and room_type([p["text"]])]
        if len(names) >= 2:
            floors.append(dict(walls=cl, bbox=b))
    if not floors:
        raise PlanError("no floor plan found (need double-line walls and room names)")
    s, est = scale_from_labels([w for w in W_solid if any(inside(((w[0] + w[1]) / 2, (w[2] + w[3]) / 2), f["bbox"])
                                                           for f in floors)], phr, T)
    scale_src = "labels"
    if not s:
        s, scale_src = T / 0.375, "assumed"     # assume the main wall is 4.5" thick
    BL = boundary_lines(page["segs"], s)
    out = []
    for f in floors:
        f["walls"] = close_corners(f["walls"], T)
        out.append(detect_floor(f, T, s, phr, PEN, hatch_all, A, BL, CUTS, page["fills"]))
    out.sort(key=lambda f: f["_x"])
    return dict(T=T, scale=s, scale_source=scale_src, scale_estimates=est, floors=out)


def blue(col):
    """a water colour: clearly blue-cyan (hue 170-230 degrees) and not grey"""
    if not isinstance(col, tuple):
        return False
    r, g, b = (c / 255 for c in col[:3])
    hi, lo = max(r, g, b), min(r, g, b)
    if hi - lo < 0.12 or hi < 0.35:
        return False
    h = (60 * ((g - b) / (hi - lo)) % 360 if hi == r else 60 * ((b - r) / (hi - lo)) + 120 if hi == g
         else 60 * ((r - g) / (hi - lo)) + 240)
    return 170 <= h <= 230


def in_poly(x, y, poly):
    inside_ = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside_ = not inside_
    return inside_


def detect_floor(f, T, s, phr, lines, hatch, A, zone_lines, cuts=(), fills=()):
    b, walls = f["bbox"], f["walls"]
    ops = [o for o in openings(walls, lines, A, T, s, zone_lines) if inside(((o["rect"][0] + o["rect"][1]) / 2,
                                                                  (o["rect"][2] + o["rect"][3]) / 2), b)]
    # one opening per gap (found from both of its ends)
    uniq = []
    for o in ops:
        if not any(abs(o["rect"][0] - u["rect"][0]) < T and abs(o["rect"][1] - u["rect"][1]) < T and
                   abs(o["rect"][2] - u["rect"][2]) < T and abs(o["rect"][3] - u["rect"][3]) < T for u in uniq):
            uniq.append(o)
    ops = uniq
    # glass drawn inside an unbroken wall is a window even when the gap search finds no wall on both sides
    for r, o in cuts:
        c = ((r[0] + r[1]) / 2, (r[2] + r[3]) / 2)
        if inside(c, b) and not any(overlap_rect(r, u["rect"], -0.5) for u in ops) \
                and not any(inside(c, w) for w in walls):      # (glass running on behind a column)
            ops.append(dict(type="window", rect=r, axis=o, glass=1))
    flights = [fl for fl in stair_flights(hatch, T, s, phr) if inside(((fl["rect"][0] + fl["rect"][1]) / 2,
                                                                        (fl["rect"][2] + fl["rect"][3]) / 2), b)]
    # walls drawn between / inside the flights are stair parts (mid wall, landing edge): make them low
    stair_box = bbox([fl["rect"] for fl in flights]) if flights else None
    if stair_box:   # stair parts (landing edges, mid walls) are not doors
        ax = flights[0]["axis"]
        sb = (stair_box[0] - 4.5 * s, stair_box[1] + 4.5 * s, *stair_box[2:]) if ax == "x" else \
             (*stair_box[:2], stair_box[2] - 4.5 * s, stair_box[3] + 4.5 * s)
        ops = [o for o in ops if not inside(((o["rect"][0] + o["rect"][1]) / 2, (o["rect"][2] + o["rect"][3]) / 2), sb)]
    border = [(b[0] - T, b[0], b[2] - T, b[3] + T), (b[1], b[1] + T, b[2] - T, b[3] + T),
              (b[0] - T, b[1] + T, b[2] - T, b[2]), (b[0] - T, b[1] + T, b[3], b[3] + T)]
    F = flood_rooms(walls, [o["rect"] for o in ops if o["type"] != "opening"] + border, (b[0] - T, b[1] + T, b[2] - T, b[3] + T), max(T / 3, 0.5))
    names = [p for p in phr if inside((p["cx"], p["cy"]), b)]
    rooms, zone_of = [], {}        # zone_of[cell] = room index (open plans are split per name label)
    C, ox, oy = F["cell"], F["ox"], F["oy"]
    cell_of = lambda x, y: (int((x - ox) / C), int((y - oy) / C))
    # an open passage in a wall line parts the rooms either side of it as the wall it interrupts does (drawings
    # with no line across the passage): its centre line, run on along that wall line, separates zones
    zone_lines = {k: list(v) for k, v in zone_lines.items()}
    for op in ops:
        if op["type"] != "opening":
            continue
        k, r = op["axis"], op["rect"]
        lo, hi, b0, b1 = (r[0], r[1], r[2], r[3]) if k == "h" else (r[2], r[3], r[0], r[1])
        line = [q if k == "h" else (q[2], q[3], q[0], q[1]) for q in walls + [o["rect"] for o in ops]]
        line = [(q[0], q[1]) for q in line if abs(q[2] - b0) < 0.2 * T and abs(q[3] - b1) < 0.2 * T]
        grown = True
        while grown:
            grown = False
            for q0, q1 in line:
                if q0 <= hi + 0.5 and q1 >= lo - 0.5 and (q0 < lo or q1 > hi):
                    lo, hi, grown = min(lo, q0), max(hi, q1), True
        zone_lines[k].append(((b0 + b1) / 2, lo, hi))
    lcells = line_cells(zone_lines, C, ox, oy)
    for rid, cells in F["regions"].items():
        if rid == F["outside"]:
            continue
        area = len(cells) * (C / s) ** 2
        if area < 2.0:
            continue
        cellset = set(cells)
        inner = [p for p in names if cell_of(p["cx"], p["cy"]) in cellset]
        seeds = [(p["cx"], p["cy"], room_type([p["text"]]), p) for p in inner if room_type([p["text"]])]
        seeds = [sd for sd in seeds if sd[2] != "stair"]
        for fl in flights:      # (the middle of a dog-leg is its mid wall, so seed on a flight)
            sc = ((fl["rect"][0] + fl["rect"][1]) / 2, (fl["rect"][2] + fl["rect"][3]) / 2)
            if cell_of(*sc) in cellset:
                seeds.append((*sc, "stair", None))
                break
        if not seeds:
            xs = [ox + i * C for i, j in cells]
            ys = [oy + j * C for i, j in cells]
            edge = min(xs) <= b[0] + T or max(xs) >= b[1] - T or min(ys) <= b[2] + T or max(ys) >= b[3] - T
            door = any(cell_of(x, y) in cellset for o in ops if o["type"] == "door"
                       for x, y in (((o["rect"][0] + o["rect"][1]) / 2, o["rect"][2] - 1.5 * C),
                                    ((o["rect"][0] + o["rect"][1]) / 2, o["rect"][3] + 1.5 * C),
                                    (o["rect"][0] - 1.5 * C, (o["rect"][2] + o["rect"][3]) / 2),
                                    (o["rect"][1] + 1.5 * C, (o["rect"][2] + o["rect"][3]) / 2)))
            # a door into it makes it a lobby; ducts are walled all round; a region filled with water blue is water
            # (a pool drawn without a name)
            xs0, xs1, ys0, ys1 = min(xs), max(xs) + C, min(ys), max(ys) + C
            wet = [poly for poly, col in fills if blue(col) and len(poly) >= 3 and min(q[0] for q in poly) < xs1
                   and max(q[0] for q in poly) > xs0 and min(q[1] for q in poly) < ys1 and max(q[1] for q in poly) > ys0]
            sample = cells[::max(1, len(cells) // 200)]
            water = bool(wet) and area >= 20 and sum(any(in_poly(ox + (i + 0.5) * C, oy + (j + 0.5) * C, q) for q in wet)
                                                     for i, j in sample) >= 0.6 * len(sample)
            seeds = [(0, 0, "pool" if water else "yard" if edge else "passage" if door else "duct" if area < 12 else "room", None)]
        groups = {}
        for pc, idx in fine_parts(cells, [cell_of(sd[0], sd[1]) for sd in seeds], lcells) if seeds[0][3] or len(seeds) > 1 \
                else [(cells, [0])]:
            split_zones(pc, idx, seeds, zone_lines, C, ox, oy, groups)
        for k, zc in groups.items():
            p = seeds[k][3]
            dims = None
            if p:     # the size label written just under / after the name
                near = [q for q in inner if q["dims"] and abs(q["cx"] - p["cx"]) < 4 * p["h"] and 0 <= q["cy"] - p["cy"] < 3 * p["h"]]
                dims = near[0] if near else None
            for c in zc:
                zone_of[c] = len(rooms)
            rooms.append(dict(region=rid, type=seeds[k][2], area=round(len(zc) * (C / s) ** 2, 1),
                              label=" ".join(t["text"] for t in (p, dims) if t) if p else "",
                              dims=dims["dims"] if dims else None, rects=region_rects(zc, F)))
    # walls with outdoor space (or nothing) on both sides are boundary / parapet walls -> low
    def type_at(x, y):
        k = zone_of.get(cell_of(x, y))
        return rooms[k]["type"] if k is not None else None
    # (sampled along the wall: a long outer wall can have a room on part of it; an open shaft keeps full walls)
    out_walls = []
    for w in walls:
        sides = []
        # a stub left between an opening and a cross wall can be thicker than long: it runs the way the opening
        # beside it in the same band runs
        hz = next((o["axis"] == "h" for o in ops if overlap_rect(o["rect"], w, 0.5) and (
            abs(o["rect"][2] - w[2]) < 0.2 * T and abs(o["rect"][3] - w[3]) < 0.2 * T if o["axis"] == "h" else
            abs(o["rect"][0] - w[0]) < 0.2 * T and abs(o["rect"][1] - w[1]) < 0.2 * T)), horiz(w))
        for t in (0.1, 0.3, 0.5, 0.7, 0.9):
            if hz:
                m = w[0] + t * (w[1] - w[0])
                sides += [type_at(m, w[2] - 1.5 * C), type_at(m, w[3] + 1.5 * C)]
            else:
                m = w[2] + t * (w[3] - w[2])
                sides += [type_at(w[0] - 1.5 * C, m), type_at(w[1] + 1.5 * C, m)]
        low = all(sd is None or (sd in OUTDOOR and sd != "open") for sd in sides)
        if stair_box:
            c = ((w[0] + w[1]) / 2, (w[2] + w[3]) / 2)
            # between the flights and short across them (dashed pieces included): the mid wall, not an end wall
            lo_, hi_, w0, w1 = (stair_box[2], stair_box[3], w[2], w[3]) if ax == "x" else (stair_box[0], stair_box[1], w[0], w[1])
            mid = lo_ + T < (w0 + w1) / 2 < hi_ - T and w1 - w0 < 0.5 * (hi_ - lo_)
            if inside(c, stair_box, -0.5 * T) or (mid and inside(c, sb)):
                low = True          # mid wall between the flights (it may run on across the landing)
            elif inside(c, sb):
                low = False         # the stairwell's own walls rise with the stair
        out_walls.append((w, low))
    # page points -> feet: origin at the lower-left of the walls, +y up the page
    X0, Y1 = b[0], b[3]
    P = lambda x, y: (round((x - X0) / s, 3), round((Y1 - y) / s, 3))
    R = lambda r: [round((r[0] - X0) / s, 3), round((r[1] - X0) / s, 3), round((Y1 - r[3]) / s, 3), round((Y1 - r[2]) / s, 3)]
    title = next((p["text"] for p in phr if "FLOOR" in p["text"].upper() and b[0] <= p["cx"] <= b[1]
                  and 0 < p["cy"] - b[3] < 8 * s), None)
    ops_out = []
    for o in ops:
        d = dict(type=o["type"], rect=R(o["rect"]), axis="x" if o["axis"] == "h" else "y")
        if o["type"] == "door" and o["leaves"]:
            lf = o["leaves"][0]
            d["hinge"] = P(*lf["hinge"])
            d["swing"] = -lf["side"] if o["axis"] == "h" else lf["side"]   # +1: towards +y (or +x)
            d["double"] = len(o["leaves"]) > 1 or lf["radius"] < 0.62 * ((o["rect"][1] - o["rect"][0]) if o["axis"] == "h" else (o["rect"][3] - o["rect"][2]))
        ops_out.append(d)
    return dict(
        _x=b[0], title=title, origin_pt=[X0, Y1], size=[round((b[1] - b[0]) / s, 2), round((b[3] - b[2]) / s, 2)],
        walls=[R(w) + [1 if low else 0] for w, low in out_walls],
        openings=ops_out,
        rooms=[dict(r, rects=[R(q) for q in r["rects"]]) for r in rooms],
        stairs=[dict(rect=R(fl["rect"]), axis=fl["axis"], steps=fl["n"], up=fl["up"],
                     words=[(t, *P(x, y)) for t, x, y in fl["words"]]) for fl in flights],
        labels=[dict(text=p["text"], at=P(p["cx"], p["cy"])) for p in names],
    )


def detect(pdf):
    pages = []
    for k in range(1, vector.page_count(pdf) + 1):
        try:
            pg = detect_page(vector.read_page(pdf, k))
        except PlanError:
            continue
        for f in pg["floors"]:
            f["page"] = k
        pages.append(pg)
    if not pages:
        raise PlanError("No floor plan was found in this PDF. The drawing needs double-line walls and room names.")
    floors = [f for p in pages for f in p["floors"]]
    # order: by the title (ground, first, second...) else left-to-right, page order
    order = ["BASEMENT", "STILT", "GROUND", "FIRST", "SECOND", "THIRD", "FOURTH", "TERRACE"]
    def rank(f):
        t = (f["title"] or "").upper()
        return next((i for i, k in enumerate(order) if k in t), 99)
    if all(rank(f) < 99 for f in floors):
        floors.sort(key=rank)
    for i, f in enumerate(floors):
        f.pop("_x")
        f["level"] = i
        f["name"] = (f["title"] or f"Floor {i}").title().replace(" Plan", "")
    p0 = pages[0]
    return dict(version=1, source=pdf.rsplit("/", 1)[-1], units="ft", scale_pt_per_ft=round(p0["scale"], 4),
                scale_source=p0["scale_source"], wall_pt=round(p0["T"], 2), floor_height=10.0, slab=0.5,
                floors=floors)


if __name__ == "__main__":
    pdf = sys.argv[1]
    plan = detect(pdf)
    out = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
    js = json.dumps(plan, indent=1)
    if out:
        open(out, "w").write(js)
    for f in plan["floors"]:
        print(f["name"], f["size"], "walls", len(f["walls"]), "openings",
              {t: sum(o["type"] == t for o in f["openings"]) for t in ("door", "window", "opening")},
              "rooms", len(f["rooms"]), "stairs", len(f["stairs"]))
    print("scale", plan["scale_pt_per_ft"], plan["scale_source"])
