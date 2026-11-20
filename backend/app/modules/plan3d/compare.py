"""Compare a read plan with the truth, both as PlanTo3D floors (feet, y up).

    scores = compare_floor(truth_floor, read_floor)

The read floor is moved so its walls' lower-left corner meets the truth's (readers put
their origin at their own walls). Measures, each as recall (truth found) and precision
(found things that are true):

    walls     area of the truth walls (less their openings) covered by read walls, and
              the reverse, with a tolerance of WALL_TOL_FT around each read wall
    doors     truth doors matched to read doors or plain openings whose centre is within
              MATCH_FT on the same axis
    windows   the same for windows
    rooms     a truth room is found when a read room's centre lies inside it; `room_types`
              is the share of truth rooms found with the right type
Site areas (pool, garden, paving...) and ducts are left out: the readers build rooms only.
"""

from shapely.geometry import box
from shapely.ops import unary_union

WALL_TOL_FT = 0.35
MATCH_FT = 1.6
SITE_TYPES = {
    "pool",
    "garden",
    "yard",
    "parking",
    "balcony",
    "dock",
    "water",
    "court",
    "custom",
    "duct",
}
SAME_TYPE = {
    "toilet": {"toilet", "wash"},
    "living": {"living", "majlis"},
    "passage": {"passage", "foyer"},
}


def _walls(floor: dict) -> list[list[float]]:
    return [w[:4] for w in floor.get("walls", []) if not (len(w) > 4 and w[4])]


def _shift(floor: dict, dx: float, dy: float) -> dict:
    def mv(r):
        return [r[0] + dx, r[1] + dx, r[2] + dy, r[3] + dy]

    return {
        "walls": [mv(w) for w in _walls(floor)],
        "openings": [dict(o, rect=mv(o["rect"])) for o in floor.get("openings", [])],
        "rooms": [dict(r, rects=[mv(q) for q in r["rects"]]) for r in floor.get("rooms", [])],
    }


def _centre(r) -> tuple[float, float]:
    return ((r[0] + r[1]) / 2, (r[2] + r[3]) / 2)


def _pr(found: int, total: int, true_read: int, read: int) -> dict:
    return {
        "recall": round(found / total, 4) if total else 1.0,
        "precision": round(true_read / read, 4) if read else (1.0 if not total else 0.0),
        "truth": total,
        "read": read,
    }


def _match_openings(truth, read, kinds_truth, kinds_read) -> dict:
    t = [o for o in truth if o["type"] in kinds_truth]
    r = [o for o in read if o["type"] in kinds_read]
    used: set[int] = set()
    found = 0
    for o in t:
        c = _centre(o["rect"])
        best = None
        for i, q in enumerate(r):
            if i in used or q.get("axis") != o.get("axis"):
                continue
            d = abs(_centre(q["rect"])[0] - c[0]) + abs(_centre(q["rect"])[1] - c[1])
            if d <= MATCH_FT and (best is None or d < best[0]):
                best = (d, i)
        if best:
            used.add(best[1])
            found += 1
    return _pr(found, len(t), len(used), len(r))


def compare_floor(truth: dict, read: dict) -> dict:
    tw, rw = _walls(truth), _walls(read)
    if not rw:
        empty = _pr(0, 1, 0, 0)
        return {"walls": empty, "doors": empty, "windows": empty, "rooms": empty, "room_types": 0.0}
    dx = min(w[0] for w in tw) - min(w[0] for w in rw)
    dy = min(w[2] for w in tw) - min(w[2] for w in rw)
    read = _shift(read, dx, dy)
    # PlanTo3D's walls run on through their openings; a reader that stops a wall at a door
    # is right, so the truth's opening rectangles are not wall to be found
    holes = unary_union(
        [
            box(o["rect"][0], o["rect"][2], o["rect"][1], o["rect"][3])
            for o in truth.get("openings", [])
        ]
    )
    full = unary_union([box(w[0], w[2], w[1], w[3]) for w in tw])
    tu = full.difference(holes)
    ru = unary_union([box(w[0], w[2], w[1], w[3]) for w in read["walls"]])
    walls = {
        "recall": round(tu.intersection(ru.buffer(WALL_TOL_FT)).area / tu.area, 4),
        "precision": round(ru.intersection(full.buffer(WALL_TOL_FT)).area / ru.area, 4),
        "truth": len(tw),
        "read": len(read["walls"]),
    }
    doors = _match_openings(
        truth.get("openings", []), read["openings"], {"door"}, {"door", "opening"}
    )
    windows = _match_openings(truth.get("openings", []), read["openings"], {"window"}, {"window"})
    t_rooms = [r for r in truth.get("rooms", []) if r["type"] not in SITE_TYPES]
    r_rooms = [r for r in read["rooms"] if r["type"] not in SITE_TYPES]
    found = typed = 0
    hit: set[int] = set()
    for tr in t_rooms:
        shape = unary_union([box(q[0], q[2], q[1], q[3]) for q in tr["rects"]]).buffer(0.5)
        best = None
        for i, rr in enumerate(r_rooms):
            if i in hit:
                continue
            q = max(rr["rects"], key=lambda q: (q[1] - q[0]) * (q[3] - q[2]))
            cx, cy = _centre(q)
            if shape.contains(box(cx - 0.01, cy - 0.01, cx + 0.01, cy + 0.01)):
                best = i
                break
        if best is not None:
            hit.add(best)
            found += 1
            want = tr["type"]
            got = r_rooms[best]["type"]
            if got == want or got in SAME_TYPE.get(want, set()):
                typed += 1
    rooms = _pr(found, len(t_rooms), len(hit), len(r_rooms))
    return {
        "walls": walls,
        "doors": doors,
        "windows": windows,
        "rooms": rooms,
        "room_types": round(typed / len(t_rooms), 4) if t_rooms else 1.0,
    }
