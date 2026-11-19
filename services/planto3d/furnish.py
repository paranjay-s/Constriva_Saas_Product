"""Rule-based furniture layout (no ML): for each detected room zone pick items for its type and place them against
real walls, away from doors, windows (for tall items), each other, and other rooms.
Pure python so it can be tested without Blender. Units: feet. Output items are calls into blender/lib.py.

Rotation (lib.py convention): 0 = item front faces -y (back to a wall on +y), 90 = +x, 180 = +y, 270 = -x.
"""
import math

SIDES = {   # side of the room rect -> (rot of an item backed onto it, axis along the wall)
    "N": 0, "S": 180, "E": 270, "W": 90,
}
import rooms

INDOOR = rooms.kinds("indoor")      # web/rooms.json


def area(r):
    return (r[1] - r[0]) * (r[3] - r[2])


def overlap(a, b, m=0.0):
    return a[0] < b[1] - m and b[0] < a[1] - m and a[2] < b[3] - m and b[2] < a[3] - m


def inside(a, b, m=0.05):
    return a[0] >= b[0] - m and a[1] <= b[1] + m and a[2] >= b[2] - m and a[3] <= b[3] + m


def subtract_iv(ivs, a, b):
    return [x for p, q in ivs for x in ((p, min(q, a)), (max(p, b), q)) if x[1] - x[0] > 0.05]


def subtract_ivs(ivs, cuts):
    """intervals minus every interval in cuts"""
    for a, b in cuts:
        ivs = subtract_iv(ivs, a, b)
    return ivs


def union_iv(ivs):
    out = []
    for a, b in sorted(ivs):
        if out and a <= out[-1][1] + 0.3:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def max_rect(rects, exclude=None, g=0.25):
    """largest axis-aligned rectangle inside the union of rects (minus `exclude`): rooms come as row slices"""
    x0, y0 = min(r[0] for r in rects), min(r[2] for r in rects)
    nx, ny = int(round((max(r[1] for r in rects) - x0) / g)), int(round((max(r[3] for r in rects) - y0) / g))
    grid = [[False] * nx for _ in range(ny)]
    for r in rects:
        for j in range(int(round((r[2] - y0) / g)), int(round((r[3] - y0) / g))):
            for i in range(int(round((r[0] - x0) / g)), int(round((r[1] - x0) / g))):
                grid[j][i] = True
    if exclude:
        for j in range(ny):
            for i in range(nx):
                x, y = x0 + (i + 0.5) * g, y0 + (j + 0.5) * g
                if exclude[0] < x < exclude[1] and exclude[2] < y < exclude[3]:
                    grid[j][i] = False
    best, hts = (0, None), [0] * nx
    for j in range(ny):
        hts = [h + 1 if grid[j][i] else 0 for i, h in enumerate(hts)]
        st = []
        for i in range(nx + 1):         # largest rectangle in a histogram
            h = hts[i] if i < nx else 0
            while st and hts[st[-1]] >= h:
                top = st.pop()
                left = st[-1] + 1 if st else 0
                a = hts[top] * (i - left)
                if a > best[0]:
                    best = (a, (x0 + left * g, x0 + i * g, y0 + (j + 1 - hts[top]) * g, y0 + (j + 1) * g))
            st.append(i)
    return best[1]


class Room:
    def __init__(self, zone, floor):
        self.zone, self.type, self.floor = zone, zone["type"], floor
        self.rect = max_rect(zone["rects"]) or max(zone["rects"], key=area)
        x0, x1, y0, y1 = self.rect
        self.w, self.d = x1 - x0, y1 - y0
        self.items, self.keepout = [], []
        walls = [w for w in floor["walls"]]
        ops = floor["openings"]
        self.free = {}       # side -> {"low": intervals, "tall": intervals}  (positions along the side)
        self.open_ways = []  # stretches of the room's edge with no wall into another room (open plan)
        for side in "NSEW":
            along = (x0, x1) if side in "NS" else (y0, y1)
            face = {"N": y1, "S": y0, "E": x1, "W": x0}[side]
            # wall coverage along this side (open-plan boundaries have no wall)
            cov = []     # walls, and windows (a counter or bed can stand under a sill; tall items are cut below)
            for w in walls + [list(o["rect"]) + [0] for o in ops if o["type"] == "window"]:
                if side in "NS":
                    near_ = (w[2] - 0.6 <= face <= w[3] + 0.6) and (w[2] >= face - 0.25 if side == "N" else w[3] <= face + 0.25)
                    if near_ and w[4] == 0:
                        cov.append((max(w[0], along[0]), min(w[1], along[1])))
                else:
                    near_ = (w[0] - 0.6 <= face <= w[1] + 0.6) and (w[0] >= face - 0.25 if side == "E" else w[1] <= face + 0.25)
                    if near_ and w[4] == 0:
                        cov.append((max(w[2], along[0]), min(w[3], along[1])))
            cov = union_iv([c for c in cov if c[1] - c[0] > 0.2])
            low, tall = cov, cov
            for o in ops:
                r = o["rect"]
                if side in "NS":
                    hit = r[2] - 0.8 <= face <= r[3] + 0.8 and r[1] > along[0] and r[0] < along[1]
                    a, b = r[0], r[1]
                else:
                    hit = r[0] - 0.8 <= face <= r[1] + 0.8 and r[3] > along[0] and r[2] < along[1]
                    a, b = r[2], r[3]
                if not hit:
                    continue
                if o["type"] == "window":
                    tall = subtract_iv(tall, a - 0.2, b + 0.2)
                else:
                    low = subtract_iv(low, a - 0.4, b + 0.4)
                    tall = subtract_iv(tall, a - 0.4, b + 0.4)
            self.free[side] = {"low": low, "tall": tall}
            # an open edge (no wall, no window: an open-plan boundary with the next zone) keeps a strip of half a
            # passage clear inside the room, so two zones side by side leave 0.9 m (3 ft) between their furniture
            doors_here = [(o["rect"][0], o["rect"][1]) if side in "NS" else (o["rect"][2], o["rect"][3]) for o in ops
                          if o["type"] != "window" and overlap(o["rect"], (x0 - 1, x1 + 1, y0 - 1, y1 + 1))]
            for a, b in subtract_ivs([along], cov + [(d0 - 0.5, d1 + 0.5) for d0, d1 in doors_here]):
                m = (a + b) / 2
                past = {"N": (m, y1 + 0.75), "S": (m, y0 - 0.75), "E": (x1 + 0.75, m), "W": (x0 - 0.75, m)}[side]
                into = any(z is not zone and any(q[0] <= past[0] <= q[1] and q[2] <= past[1] <= q[3] for q in z["rects"])
                           for z in floor["rooms"])
                if into and b - a >= 2.5:       # an open way into the next room: kept as passable as a door
                    self.open_ways.append({"N": (a, b, y1 - 0.5, y1), "S": (a, b, y0, y0 + 0.5),
                                           "E": (x1 - 0.5, x1, a, b), "W": (x0, x0 + 0.5, a, b)}[side])
                beyond = zone["type"] in INDOOR and any(
                    z is not zone and z["type"] in INDOOR and any(q[0] <= past[0] <= q[1] and q[2] <= past[1] <= q[3] for q in z["rects"])
                    for z in floor["rooms"])
                if b - a >= 4.0 and beyond:
                    self.keepout.append({"N": (a, b, y1 - 1.5, y1), "S": (a, b, y0, y0 + 1.5),
                                         "E": (x1 - 1.5, x1, a, b), "W": (x0, x0 + 1.5, a, b)}[side])
        # fridges and wardrobes must not stand in front of a window on a neighbouring wall either
        self.win_front = []
        for o in ops:
            if o["type"] == "window":
                r = o["rect"]
                self.win_front.append((r[0] - 0.1, r[1] + 0.1, r[2] - 2.0, r[3] + 2.0) if o["axis"] == "x" else
                                      (r[0] - 2.0, r[1] + 2.0, r[2] - 0.1, r[3] + 0.1))
        # stair flights and their landing strip are walkways
        for st in floor.get("stairs", []):
            r = st["rect"]
            self.keepout.append((r[0] - 0.1, r[1] + 0.1, r[2] - 0.1, r[3] + 0.1))
        if floor.get("stairs"):
            xs = [v for st in floor["stairs"] for v in st["rect"][:2]]
            ys = [v for st in floor["stairs"] for v in st["rect"][2:]]
            ax = floor["stairs"][0]["axis"]
            pad = 4.0
            self.keepout.append((min(xs) - (pad if ax == "x" else 0), max(xs) + (pad if ax == "x" else 0),
                                 min(ys) - (pad if ax == "y" else 0), max(ys) + (pad if ax == "y" else 0)))
        # door swing / walkway keep-out boxes (both sides of every door touching this room)
        for o in ops:
            if o["type"] == "window":
                continue
            r = o["rect"]
            box = (r[0] - 0.2, r[1] + 0.2, r[2] - 3.0, r[3] + 3.0) if o["axis"] == "x" else \
                  (r[0] - 3.0, r[1] + 3.0, r[2] - 0.2, r[3] + 0.2)
            if overlap(box, self.rect):
                self.keepout.append(box)
        # doors of this room: on its edge, with their middle inside the room's span (not a neighbour's door at a corner)
        x0, x1, y0, y1 = self.rect
        self.doors = [o for o in ops if o["type"] != "window" and overlap(
            (o["rect"][0] - 0.8, o["rect"][1] + 0.8, o["rect"][2] - 0.8, o["rect"][3] + 0.8), self.rect)
            and (x0 < (o["rect"][0] + o["rect"][1]) / 2 < x1 if o["axis"] == "x" else y0 < (o["rect"][2] + o["rect"][3]) / 2 < y1)]

    # ---- placement against a side
    def spot(self, side, w, d, tall=False, align="center", gap=0.0):
        """best position (center) for an item of width w / depth d with its back on `side` -> (x, y, rot, box)"""
        x0, x1, y0, y1 = self.rect
        best = None
        for a, b in self.free[side]["tall" if tall else "low"]:
            if b - a < w + 2 * gap:
                continue
            if align == "start":
                c = a + gap + w / 2
            elif align == "end":
                c = b - gap - w / 2
            else:
                c = (a + b) / 2
            for c in (c, a + gap + w / 2, b - gap - w / 2):
                if side == "N":
                    box, xy = (c - w / 2, c + w / 2, y1 - d, y1), (c, y1 - d / 2)
                elif side == "S":
                    box, xy = (c - w / 2, c + w / 2, y0, y0 + d), (c, y0 + d / 2)
                elif side == "E":
                    box, xy = (x1 - d, x1, c - w / 2, c + w / 2), (x1 - d / 2, c)
                else:
                    box, xy = (x0, x0 + d, c - w / 2, c + w / 2), (x0 + d / 2, c)
                if self.fits(box) and not (tall and 2 <= d <= 3 and any(overlap(box, k, 0.02) for k in self.win_front)):
                    score = b - a
                    if not best or score > best[0]:
                        best = (score, (*xy, SIDES[side], box))
                    break
        return best[1] if best else None

    def fits(self, box, ignore_keepout=False):
        if not inside(box, self.rect):
            return False
        if any(overlap(box, it["box"], 0.02) for it in self.items if it.get("solid", True)):
            return False
        if not ignore_keepout and any(overlap(box, k, 0.02) for k in self.keepout):
            return False
        return True

    def add(self, fn, box, *args, solid=True, **kw):
        self.items.append(dict(fn=fn, args=list(args), kw=kw, box=box, solid=solid, room=self.zone.get("label") or self.type))

    def sides_by(self, key, tall=False):
        """sides sorted by their longest free run (desc)"""
        lens = {s: max((b - a for a, b in self.free[s]["tall" if tall else "low"]), default=0) for s in "NSEW"}
        return sorted("NSEW", key=lambda s: -lens[s] if key == "long" else lens[s])

    def door_side(self):
        """side of the rect nearest to the (first) door"""
        if not self.doors:
            return None
        r = self.doors[0]["rect"]
        cx, cy = (r[0] + r[1]) / 2, (r[2] + r[3]) / 2
        x0, x1, y0, y1 = self.rect
        return min({"W": abs(cx - x0), "E": abs(cx - x1), "S": abs(cy - y0), "N": abs(cy - y1)}.items(),
                   key=lambda kv: kv[1])[0]


OPP = {"N": "S", "S": "N", "E": "W", "W": "E"}
FRONT = {"N": "-y", "S": "+y", "E": "-x", "W": "+x"}     # the way a counter on that wall faces


def front_offset(side, xy, dist):
    """point `dist` feet in front of an item at xy backed onto `side`"""
    dx, dy = {"N": (0, -1), "S": (0, 1), "E": (-1, 0), "W": (1, 0)}[side]
    return xy[0] + dx * dist, xy[1] + dy * dist


def rect_at(c, w, d, side):
    """item box of width w (along wall) and depth d centred at c, for an item backed onto `side`"""
    if side in "NS":
        return (c[0] - w / 2, c[0] + w / 2, c[1] - d / 2, c[1] + d / 2)
    return (c[0] - d / 2, c[0] + d / 2, c[1] - w / 2, c[1] + w / 2)


# ------------------------------------------------------------------ rules per room type
def bedroom(R):
    double = min(R.w, R.d) >= 9.0
    bw, bl = (5.0, 6.6) if double else (3.5, 6.5)
    for side in R.sides_by("long", tall=True):
        depth_room = R.d if side in "NS" else R.w
        if depth_room < bl + 2.2:
            continue
        p = R.spot(side, bw + 2 * 1.6, bl, tall=True)
        stands = p is not None
        p = p or R.spot(side, bw, bl, tall=True)
        if not p:
            continue
        x, y, rot, box = p
        bb = rect_at((x, y), bw, bl, side)
        # wood panel behind the bed: only as wide as the wall that is free there (never past a door or wall end)
        c = x if side in "NS" else y
        iv = next(((a, b) for a, b in R.free[side]["tall"] if a - 0.01 <= c <= b + 0.01), (c - bw / 2, c + bw / 2))
        panel = max(0.0, min(bw + 3.2 if stands else bw + 1.0, 2 * min(c - iv[0], iv[1] - c) - 0.2))
        R.add("bed", bb, x, y, rot, w=bw, l=bl, panel=round(panel, 2))
        if stands:
            for s in (-1, 1):
                off = (bw / 2 + 0.8) * s
                cx, cy = (x + off, y) if side in "NS" else (x, y + off)
                cx, cy = front_offset(side, (cx, cy), -(bl / 2 - 0.8))
                R.add("nightstand", rect_at((cx, cy), 1.5, 1.4, side), cx, cy, rot)
        break
    # wardrobe on another wall, towards a corner
    for side in R.sides_by("long", tall=True):
        for w in (6.0, 5.0, 4.0):
            p = R.spot(side, w, 2.0, tall=True, align="end", gap=0.1)
            if p:
                x, y, rot, box = p
                R.add("wardrobe", box, x, y, rot, w=w, d=2.0, h=7.0)
                break
        else:
            continue
        break
    if R.w * R.d > 120:
        p = None
        for side in R.sides_by("long"):
            p = R.spot(side, 3.5, 2.0)
            if p:
                R.add("desk", p[3], p[0], p[1], p[2])
                break
    # the bed's wall panel stops short of anything else standing against that wall (wardrobe, desk)
    for bed in [i for i in R.items if i["fn"] == "bed"]:
        bx, by, rot = bed["args"]
        side = next(k for k, v in SIDES.items() if v == rot)
        c, face = (bx, {"N": R.rect[3], "S": R.rect[2]}.get(side)) if side in "NS" else (by, {"E": R.rect[1], "W": R.rect[0]}[side])
        half = bed["kw"]["panel"] / 2
        for it in R.items:
            if it is bed or it["fn"] == "nightstand":
                continue
            b = it["box"]
            lo, hi, n0, n1 = (b[0], b[1], b[2], b[3]) if side in "NS" else (b[2], b[3], b[0], b[1])
            if n0 - 0.3 <= face <= n1 + 0.3:
                if hi <= c:
                    half = min(half, c - hi - 0.05)
                elif lo >= c:
                    half = min(half, lo - c - 0.05)
        bed["kw"]["panel"] = round(max(0.0, 2 * half), 2)


def along(R, side, w, d, from_hi, tall=False, gap=0.0):
    """first spot for a w x d item backed onto `side`, scanning along the wall from one end
    (from_hi: start at the high-x / high-y end). gap: clear space kept on both sides of the item."""
    x0, x1, y0, y1 = R.rect
    lo, hi = (x0, x1) if side in "NS" else (y0, y1)
    n = int((hi - lo - w) / 0.25) + 1
    for k in range(max(n, 0)):
        c = (hi - w / 2 - k * 0.25) if from_hi else (lo + w / 2 + k * 0.25)
        if not any(a - 0.01 <= c - w / 2 and c + w / 2 <= b + 0.01 for a, b in R.free[side]["tall" if tall else "low"]):
            continue
        box = rect_at(((c, {"N": y1 - d / 2, "S": y0 + d / 2}[side]) if side in "NS" else
                       ({"E": x1 - d / 2, "W": x0 + d / 2}[side], c)), w, d, side)
        roomy = rect_at(((box[0] + box[1]) / 2, (box[2] + box[3]) / 2), w + 2 * gap, d, side)
        if R.fits(box) and not any(overlap(roomy, it["box"], 0.02) for it in R.items if it.get("solid", True)):
            return ((box[0] + box[1]) / 2, (box[2] + box[3]) / 2, SIDES[side], box)
    return None


def toilet(R):
    """basin by the door, then the WC, then the shower in the far corner - one wall if it is long enough,
    so the WC never faces the basin across a small room"""
    ds = R.door_side()
    door = R.doors[0]["rect"] if R.doors else None
    walls = [s for s in R.sides_by("long") if s != ds]
    placed = False
    for side in walls:
        if door:      # which end of this wall is nearer the door
            dc = (door[0] + door[1]) / 2 if side in "NS" else (door[2] + door[3]) / 2
            lo, hi = (R.rect[0], R.rect[1]) if side in "NS" else (R.rect[2], R.rect[3])
            near_hi = abs(dc - hi) < abs(dc - lo)
        else:
            near_hi = False
        v = along(R, side, 2.4, 1.7, near_hi, tall=True)
        if not v:
            continue
        R.add("vanity", v[3], v[0], v[1], v[2], w=2.2)
        wc = along(R, side, 1.6, 2.2, near_hi, gap=0.4)
        if not wc:            # WC beside the basin wall, at the far corner
            R.items.pop()
            continue
        R.add("wc2", wc[3], wc[0], wc[1], wc[2])
        placed = True
        break
    if not placed:            # small room: WC facing the door, basin on a side wall next to the door
        order = [OPP[ds]] + [s for s in "NSEW" if s not in (ds, OPP[ds])] if ds else list("NSEW")
        for side in order:
            p = R.spot(side, 1.6, 2.2, align="end", gap=0.3)
            if p:
                R.add("wc2", p[3], p[0], p[1], p[2])
                break
        for side in order[1:]:
            p = R.spot(side, 2.4, 1.7, tall=True, align="start", gap=0.2)
            if p:
                R.add("vanity", p[3], p[0], p[1], p[2], w=2.2)
                break
    for side in [s for s in R.sides_by("long") if s != ds] + ([ds] if ds else []):   # shower in a free corner
        for from_hi in (True, False):
            p = along(R, side, 2.6, 2.6, from_hi)
            if p and (abs(p[3][0] - R.rect[0]) < 0.05 or abs(p[3][1] - R.rect[1]) < 0.05 or
                      abs(p[3][2] - R.rect[2]) < 0.05 or abs(p[3][3] - R.rect[3]) < 0.05) and \
                    sum(abs(v - e) < 0.05 for v, e in zip(p[3], R.rect)) >= 2:
                x, y, rot, box = p
                wx, wy = {"N": (x, box[3]), "S": (x, box[2]), "E": (box[1], y), "W": (box[0], y)}[side]
                R.add("shower2", box, wx, wy, rot)
                R.add("geyser", box, wx, wy, rot, solid=False)
                return


def kitchen(R):
    """L-shaped platform: the main run on the window wall with the sink under the window, the return run (hob +
    chimney) on the side wall away from the door; fridge on a free tall wall; nothing on the door's wall."""
    ds = R.door_side()
    x0, x1, y0, y1 = R.rect
    FRONT = {"N": "-y", "S": "+y", "E": "-x", "W": "+x"}

    def window_at(side):           # centre of a window on this wall (a gap in the tall-free spans), or None
        t = R.free[side]["tall"]
        gaps = [((p + q) / 2, q - p) for p, q in zip([v[1] for v in t], [v[0] for v in t[1:]])]
        if not t and R.free[side]["low"]:
            a_, b_ = max(R.free[side]["low"], key=lambda iv: iv[1] - iv[0])
            gaps = [((a_ + b_) / 2, b_ - a_)]
        return max(gaps, key=lambda g: g[1])[0] if gaps else None

    def box_on(side, a_, b_):
        return {"N": (a_, b_, y1 - 2.0, y1), "S": (a_, b_, y0, y0 + 2.0), "E": (x1 - 2.0, x1, a_, b_),
                "W": (x0, x0 + 2.0, a_, b_)}[side]

    def fit_run(side, a_, b_, keep, min_len):
        """shrink [a_, b_] from the end away from `keep` ('lo' / 'hi' / None) until it fits"""
        while b_ - a_ >= min_len:
            if R.fits(box_on(side, a_, b_)):
                return a_, b_
            if keep == "hi" or (keep is None and (b_ - a_) % 1.0 < 0.5):
                a_ += 0.5
            else:
                b_ -= 0.5
        return None

    def score(side):
        length = max((q - p for p, q in R.free[side]["low"]), default=0)
        return length + 5 * (window_at(side) is not None) + 3 * (side == OPP.get(ds)) - 8 * (side == ds)

    main = None
    for side in sorted("NSEW", key=score, reverse=True):
        if side == ds or not R.free[side]["low"]:
            continue
        a_, b_ = max(R.free[side]["low"], key=lambda iv: iv[1] - iv[0])
        r = fit_run(side, a_, b_, None, 4.5)
        if r:
            main = (side, *r)
            break
    if not main:
        return fridge(R)
    side, a_, b_ = main
    win = window_at(side)
    sink = win if win is not None and a_ + 1.2 < win < b_ - 1.2 else None
    # return run on a side wall, starting in the corner next to the main run, on the end away from the door
    ret = None
    cross = "EW" if side in "NS" else "NS"
    face = {"N": y1, "S": y0, "E": x1, "W": x0}[side]
    for s2 in sorted(cross, key=lambda q: q == ds):
        if s2 == ds:
            continue
        corner_hi = face in (y1, x1)          # the main run sits at the high end of this side wall
        for p, q in R.free[s2]["low"]:
            if corner_hi:
                q2 = min(q, face - 2.0)
                if abs(q - face) > 0.3 or q2 - p < 3.0:
                    continue
                r = fit_run(s2, max(p, q2 - 6.0), q2, "hi", 3.0)
            else:
                p2 = max(p, face + 2.0)
                if abs(p - face) > 0.3 or q - p2 < 3.0:
                    continue
                r = fit_run(s2, p2, min(q, p2 + 6.0), "lo", 3.0)
            if r:
                ret = (s2, *r)
                break
        if ret:
            break
    # which end of the main run touches the return (the hob goes there if there is no return)
    hob_main = None
    if not ret:
        hob_main = (b_ - 1.6) if sink is None or abs((b_ - 1.6) - sink) > 2.6 else (a_ + 1.6)
        if sink is not None and abs(hob_main - sink) < 2.6:
            hob_main = None
    R.add("kitchen_run", box_on(side, a_, b_), *box_on(side, a_, b_), FRONT[side],
          sink=sink if sink is not None else (a_ + 1.4 if ret is None else (a_ + b_) / 2), hob=hob_main)
    runs = [(side, a_, b_, hob_main)]
    if ret:
        s2, p, q = ret
        hob = (p + q) / 2
        R.add("kitchen_run", box_on(s2, p, q), *box_on(s2, p, q), FRONT[s2], sink=None, hob=hob)
        runs.append((s2, p, q, hob))
    for sd, p, q, hob in runs:
        if hob is not None:
            hx, hy = {"N": (hob, y1), "S": (hob, y0), "E": (x1, hob), "W": (x0, hob)}[sd]
            R.add("chimney", (0, 0, 0, 0), hx, hy, SIDES[sd], solid=False)
        for u0, v0 in R.free[sd]["tall"]:          # wall cabinets where the wall is solid, not over the hob
            segs = [(max(u0, p), min(v0, q))]
            if hob is not None:
                segs = subtract_iv(segs, hob - 1.4, hob + 1.4)
            for u, v in segs:
                if v - u >= 1.5:
                    box = {"N": (u, v, y1 - 1.1, y1), "S": (u, v, y0, y0 + 1.1), "E": (x1 - 1.1, x1, u, v), "W": (x0, x0 + 1.1, u, v)}[sd]
                    R.add("wall_cab2", (0, 0, 0, 0), *box, FRONT[sd], solid=False)
    fridge(R)
    island(R, side, a_, b_)


ISLAND_AISLE, ISLAND_DEPTH, ISLAND_BEHIND, STOOL_ROOM = 3.5, 3.0, 3.0, 2.0      # feet


def island(R, side, a_, b_):
    """a kitchen island parallel to the main run, a working aisle away from it, where the room leaves a way past it
    (ISLAND_BEHIND) and nothing is in the way; counter stools on the far side when there is room for them too"""
    x0, x1, y0, y1 = R.rect
    length = min(8.0, b_ - a_ - 1.0)
    if length < 5.0:
        return
    c = (a_ + b_) / 2
    inward = {"N": -1, "S": 1, "E": -1, "W": 1}[side]
    near = {"N": y1, "S": y0, "E": x1, "W": x0}[side] + inward * (2.0 + ISLAND_AISLE)
    far = near + inward * ISLAND_DEPTH
    behind = abs({"N": y0, "S": y1, "E": x0, "W": x1}[side] - far)
    if behind < ISLAND_BEHIND:
        return
    lo, hi = sorted((near, far))
    box = (c - length / 2, c + length / 2, lo, hi) if side in "NS" else (lo, hi, c - length / 2, c + length / 2)
    if not R.fits(box):
        return
    stools = behind >= ISLAND_BEHIND + STOOL_ROOM
    face = {"N": "-y", "S": "+y", "E": "-x", "W": "+x"}[side] if stools else None
    R.add("kitchen_island", box, *box, face)
    if stools:
        n = max(2, int(length // 2.0))
        for k in range(n):
            u = c - length / 2 + (k + 0.5) * length / n
            v = far + inward * 1.0
            x, y = (u, v) if side in "NS" else (v, u)
            rot = {"N": 0, "S": 180, "E": 90, "W": 270}[side]
            R.add("bar_stool", (x - 0.6, x + 0.6, y - 0.6, y + 0.6), x, y, rot, solid=False)


def fridge(R):
    ds = R.door_side()
    for side in sorted(R.sides_by("long", tall=True), key=lambda q: q == ds):
        p = R.spot(side, 2.4, 2.3, tall=True, align="end", gap=0.1)
        if p:
            R.add("fridge2", p[3], p[0], p[1], p[2])
            return


def living(R):
    for side in R.sides_by("long"):
        for w in (7.0, 6.0, 5.0):
            p = R.spot(side, w, 3.0)
            if not p:
                continue
            x, y, rot, box = p
            ct = front_offset(side, (x, y), 3.0)
            cbox = rect_at(ct, 3.6, 2.0, side)
            if not R.fits(cbox):
                continue
            R.add("sofa", box, x, y, rot, w=w)
            R.add("coffee_table", cbox, ct[0], ct[1], rot)
            rbox = rect_at(ct, w + 0.5, 5.5, side)
            R.add("rug", rbox, *rbox, solid=False)
            # TV on the opposite wall if it is a wall
            q = R.spot(OPP[side], 5.0, 1.4)
            if q:
                R.add("tv_unit", q[3], q[0], q[1], q[2])
            return


def dining(R):
    # a "DRG./DIN." room is drawing + dining: sofa set first. Only when the label names both: a large dining area
    # in an open plan has its living room next to it, with its own sofas
    if rooms.names(R.zone.get("label") or "", "living") and R.zone.get("area", R.w * R.d) >= 150:
        living(R)
        if not dining_table(R):            # no room left beside the sofa: the table goes in the L's other arm
            r = max_rect(R.zone["rects"], exclude=R.rect)
            if r and min(r[1] - r[0], r[3] - r[2]) >= 6.0:
                R2 = Room(dict(R.zone, rects=[r]), R.floor)
                if dining_table(R2):
                    R.items += R2.items
        return
    dining_table(R)


def dining_table(R):
    long_x = R.w >= R.d
    # (table w, l, seats, chair clearance); slide along the long axis from the centre outwards
    for tw, tl, n, m in ((6.0, 3.2, 6, 2.2), (4.5, 3.0, 4, 2.2), (4.5, 3.0, 4, 1.8), (3.0, 3.0, 2, 1.8)):
        for t, u in sorted(((k / 40, j / 40) for k in range(4, 37) for j in range(14, 27)),
                           key=lambda q: abs(q[0] - 0.5) + 2 * abs(q[1] - 0.5)):
            cx = R.rect[0] + R.w * (t if long_x else u)
            cy = R.rect[2] + R.d * (u if long_x else t)
            a, b = (tw, tl) if long_x else (tl, tw)
            box = (cx - a / 2 - m, cx + a / 2 + m, cy - b / 2 - m, cy + b / 2 + m)
            if R.fits(box):
                R.add("dining_set", (cx - a / 2 - 1.6, cx + a / 2 + 1.6, cy - b / 2 - 1.6, cy + b / 2 + 1.6),
                      cx, cy, 0 if long_x else 90, w=tw, d=tl, seats=n)
                return True
    return False


def dress(R):
    """walk-in dressing room: wardrobes along the free walls"""
    for side in R.sides_by("long", tall=True)[:2]:
        for w in (6.0, 5.0, 4.0, 3.0):
            p = R.spot(side, w, 2.0, tall=True)
            if p:
                R.add("wardrobe", p[3], p[0], p[1], p[2], w=w, d=2.0, h=7.0)
                break


def puja(R):
    ds = R.door_side()
    for side in ([OPP[ds]] if ds else []) + list("NSEW"):
        for w in (3.6, 3.0, 2.4):
            p = R.spot(side, w, 1.6, tall=True)
            if p:
                R.add("puja_mandir", p[3], p[0], p[1], p[2], w=w)
                return


def wash(R):
    for side in R.sides_by("long"):
        p = R.spot(side, 2.1, 2.0, align="end", gap=0.2)
        if p:
            R.add("washer2", p[3], p[0], p[1], p[2])
            return


def parking(R):
    """as many cars as fit side by side across the room (a double garage holds two), parked along its long side"""
    along_y = R.d >= R.w
    L, W, gap = 14.5, 6.2, 1.5
    span = R.w if along_y else R.d
    n = max(1, min(4, int((span - gap) // (W + gap))))
    for k in range(n, 0, -1):            # the most cars that fit, centred across the room
        boxes = []
        for i in range(k):
            c = (R.rect[0] if along_y else R.rect[2]) + span / 2 + (i - (k - 1) / 2) * (W + gap)
            m = (R.rect[2] + R.rect[3]) / 2 if along_y else (R.rect[0] + R.rect[1]) / 2
            boxes.append((c - W / 2, c + W / 2, m - L / 2, m + L / 2) if along_y else (m - L / 2, m + L / 2, c - W / 2, c + W / 2))
        if all(R.fits(b) for b in boxes):
            for b in boxes:
                R.add("car", b, (b[0] + b[1]) / 2, (b[2] + b[3]) / 2, 0 if along_y else 90)
            return


def breakfast(R):
    """a small table and chairs (two to four seats), by a window when there is one"""
    for tw, tl, n, m in ((4.5, 3.0, 4, 1.8), (3.0, 3.0, 2, 1.8)):
        cx, cy = (R.rect[0] + R.rect[1]) / 2, (R.rect[2] + R.rect[3]) / 2
        a, b = (tw, tl) if R.w >= R.d else (tl, tw)
        box = (cx - a / 2 - m, cx + a / 2 + m, cy - b / 2 - m, cy + b / 2 + m)
        if R.fits(box):
            R.add("dining_set", (cx - a / 2 - 1.6, cx + a / 2 + 1.6, cy - b / 2 - 1.6, cy + b / 2 + 1.6),
                  cx, cy, 0 if R.w >= R.d else 90, w=tw, d=tl, seats=n)
            return


def bar(R):
    """a counter along the longest free wall"""
    for side in R.sides_by("long"):
        for w in (8.0, 6.0, 4.0):
            p = R.spot(side, w, 2.0)
            if p:
                box = p[3]
                R.add("kitchen_run", box, *box, FRONT[side], sink=None, hob=None)
                return


def foyer(R):
    """a console against a wall and a plant: an entrance, never a bed"""
    for side in R.sides_by("long"):
        p = R.spot(side, 4.0, 1.4)
        if p:
            R.add("tv_unit", p[3], p[0], p[1], p[2])
            break
    plants(R, 1)


def store(R):
    """shelving (closed cabinets) along the long walls"""
    for side in R.sides_by("long")[:2]:
        for w in (8.0, 6.0, 4.0, 3.0):
            p = R.spot(side, w, 1.6, tall=True)
            if p:
                R.add("wardrobe", p[3], p[0], p[1], p[2], w=w, d=1.6, h=7.0)
                break


def gym(R):
    """an exercise mat: equipment models are not in the library yet"""
    cx, cy = (R.rect[0] + R.rect[1]) / 2, (R.rect[2] + R.rect[3]) / 2
    a, b = min(8.0, R.w - 3), min(6.0, R.d - 3)
    if a > 2 and b > 2:
        R.add("rug", (cx - a / 2, cx + a / 2, cy - b / 2, cy + b / 2), cx - a / 2, cx + a / 2, cy - b / 2, cy + b / 2, solid=False)


def balcony(R):
    for side in R.sides_by("long"):
        p = R.spot(side, 4.0, 3.5)
        if p:
            R.add("outdoor_set", p[3], p[0], p[1], p[2])
            break
    plants(R, 2)


def garden(R):
    plants(R, max(1, int(max(R.w, R.d) / 6)))


def plants(R, n):
    x0, x1, y0, y1 = R.rect
    long_x = R.w >= R.d
    for k in range(n):
        t = (k + 0.5) / n
        x, y = (x0 + (x1 - x0) * t, (y0 + y1) / 2) if long_x else ((x0 + x1) / 2, y0 + (y1 - y0) * t)
        box = (x - 0.8, x + 0.8, y - 0.8, y + 0.8)
        if R.fits(box):
            R.add("plant", box, x, y, k * 70)


RULES = dict(dress=dress, bedroom=bedroom, toilet=toilet, kitchen=kitchen, living=living, dining=dining, puja=puja, wash=wash,
             parking=parking, balcony=balcony, garden=garden, study=lambda R: bedroom_study(R), breakfast=breakfast,
             bar=bar, foyer=foyer, store=store, gym=gym, cinema=living)
# every furnish rule named in web/rooms.json must exist here
assert {v["furnish"] for v in rooms.TYPES.values() if v["furnish"]} <= set(RULES), "rooms.json names a missing rule"


def bedroom_study(R):
    for side in R.sides_by("long"):
        p = R.spot(side, 3.5, 2.0)
        if p:
            R.add("desk", p[3], p[0], p[1], p[2])
            return


def furnish_floor(floor):
    """-> list of items {fn, args, kw, box, solid, room} for one floor"""
    out = []
    for z in floor["rooms"]:
        if z["type"] not in RULES or not z["rects"]:
            continue
        R = Room(z, floor)
        if R.w < 2.5 or R.d < 2.5:
            continue
        RULES[z["type"]](R)
        keep_passages(R)
        if z["type"] in ART_ROOMS:
            wall_art(R)
        out += R.items
    return out


ART_ROOMS = {"living", "bedroom", "dining"}
NO_ART_OVER = {"wardrobe", "tv_unit", "kitchen_run", "wall_cab2", "fridge2", "puja_mandir", "chimney", "desk"}


def wall_art(R):
    """one framed canvas on the room's longest wall stretch with no window or door (at least 4 ft), at eye height; not
    behind a wardrobe, a TV or anything else that stands tall against that wall"""
    x0, x1, y0, y1 = R.rect
    best = None
    for side in "NSEW":
        for a, b in R.free[side]["tall"]:
            if b - a < 4.0:
                continue
            near = {"N": (a, b, y1 - 2.5, y1), "S": (a, b, y0, y0 + 2.5), "E": (x1 - 2.5, x1, a, b), "W": (x0, x0 + 2.5, a, b)}[side]
            if any(it["fn"] in NO_ART_OVER and overlap(near, it["box"], 0.0) for it in R.items):
                continue
            if best is None or b - a > best[2] - best[1]:
                best = (side, a, b)
    if not best:
        return
    side, a, b = best
    w, c = min(5.0, 0.6 * (b - a)), (a + b) / 2
    box = {"N": (c - w / 2, c + w / 2, y1 - 0.15, y1), "S": (c - w / 2, c + w / 2, y0, y0 + 0.15),
           "E": (x1 - 0.15, x1, c - w / 2, c + w / 2), "W": (x0, x0 + 0.15, c - w / 2, c + w / 2)}[side]
    front = {"N": "-y", "S": "+y", "E": "-x", "W": "+x"}[side]
    R.add("wall_art", (0, 0, 0, 0), *box, front, int(abs(x0 * 31 + y0 * 17)) % 997, solid=False)


def connected_doors(R, items, g=0.5, body=0.75):
    """can someone (0.75 ft from their centre to their shoulder) walk between every door of the room, round its
    solid furniture? A grid over the room's rectangles; a door counts as reached at any free cell next to it."""
    cells = set()
    for x0, x1, y0, y1 in R.zone["rects"]:
        for i in range(int((x1 - x0) / g)):
            for j in range(int((y1 - y0) / g)):
                cx, cy = x0 + (i + 0.5) * g, y0 + (j + 0.5) * g
                # (keep off the walls too: the rects are the clear space, a walker's shoulder is 0.75 ft wide;
                # an edge shared with the next part of the same room or an open way is no wall)
                if any(abs(c - e) < body and not _open_edge(R, cx, cy) for c, e in ((cx, x0), (cx, x1), (cy, y0), (cy, y1))):
                    continue
                if any(it["solid"] and it["box"][0] - body < cx < it["box"][1] + body and it["box"][2] - body < cy < it["box"][3] + body
                       for it in items):
                    continue
                cells.add((round(cx / g), round(cy / g)))
    targets = []
    # every door on any part of the room (an L-shaped room's doors on its short arm too), and its open ways
    doors = [o["rect"] for o in R.floor["openings"] if o["type"] != "window" and any(
        q[0] - 1 <= (o["rect"][0] + o["rect"][1]) / 2 <= q[1] + 1 and q[2] - 1 <= (o["rect"][2] + o["rect"][3]) / 2 <= q[3] + 1
        for q in R.zone["rects"])]
    for r in doors + R.open_ways:
        near = {c for c in cells if r[0] - 1.6 <= c[0] * g <= r[1] + 1.6 and r[2] - 1.6 <= c[1] * g <= r[3] + 1.6}
        if not near:
            return False          # a door with no room in front of it at all
        targets.append(near)
    if len(targets) < 2:
        return True
    seen, todo = set(), [next(iter(targets[0]))]
    while todo:
        c = todo.pop()
        if c in seen or c not in cells:
            continue
        seen.add(c)
        todo += [(c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)]
    return all(t & seen for t in targets)


# what goes first when furniture closes a way through a room: decor and extras before the things the room is for
KEEP = dict(plant=0, desk=1, tv_unit=1, coffee_table=1, outdoor_set=2, wardrobe=3, dining_set=4, sofa=5, fridge2=6,
            washer2=6, kitchen_run=8, bed=9, wc2=9, vanity=9, shower2=9)


def _open_edge(R, x, y):
    """is (x, y) next to another part of the same room, an open way or a door (no wall there)?"""
    m = 1.0
    if any(q[0] - m < x < q[1] + m and q[2] - m < y < q[3] + m and not (q[0] < x < q[1] and q[2] < y < q[3])
           for q in R.zone["rects"]):
        return True
    return any(w[0] - m < x < w[1] + m and w[2] - m < y < w[3] + m for w in R.open_ways) or any(
        o["type"] != "window" and o["rect"][0] - 1.6 < x < o["rect"][1] + 1.6 and o["rect"][2] - 1.6 < y < o["rect"][3] + 1.6
        for o in R.floor["openings"])


def keep_passages(R):
    """furniture never closes the way between a room's doors (an open-plan room or a drawing room people cross to
    reach the rooms beyond): while it does, the item whose removal opens the way goes, the largest first"""
    for _ in range(6):
        if connected_doors(R, R.items):
            return
        solid = sorted((it for it in R.items if it["solid"]), key=lambda it: (KEEP.get(it["fn"], 5), -area(it["box"])))
        drop = next((it for it in solid if connected_doors(R, [x for x in R.items if x is not it])), None)
        if drop is None:
            return
        R.items = [x for x in R.items if x is not drop]


def clashes(items, floor):
    """sanity check: solid items overlapping each other, or blocking a doorway"""
    bad = []
    solid = [it for it in items if it["solid"] and it["box"][1] > it["box"][0]]
    for i, a in enumerate(solid):
        for b in solid[i + 1:]:
            if overlap(a["box"], b["box"], 0.05) and a["fn"] != "rug" and b["fn"] != "rug":
                bad.append(f'{a["fn"]} x {b["fn"]} in {a["room"]}')
    for o in floor["openings"]:
        if o["type"] == "window":
            continue
        r = o["rect"]
        for it in solid:
            if overlap(it["box"], (r[0] - 0.1, r[1] + 0.1, r[2] - 0.1, r[3] + 0.1)):
                bad.append(f'{it["fn"]} blocks a doorway in {it["room"]}')
    return bad


if __name__ == "__main__":
    import json, sys
    P = json.load(open(sys.argv[1]))
    for f in P["floors"]:
        items = furnish_floor(f)
        from collections import Counter
        print(f["name"], len(items), dict(Counter(i["fn"] for i in items)))
        for b in clashes(items, f):
            print("  CLASH", b)
