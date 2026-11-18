"""Score a detected plan against a reference plan (a plan corrected by hand on the review page).

Usage: python3 tools/score_plan.py detected.json reference.json [--json]

Both are PlanTo3D plan JSON (feet; per floor, origin at the lower-left of the walls), compared floor by floor in
order. A plan corrected from a detected one shares its frame; plans from different readers are compared as they
are, so a wrong scale or a shifted outline counts against the reader, as it would in the house.

- walls: centre lines, sampled every 0.1 ft. A sample of one plan is matched when a wall of the other plan runs the
  same way (walls are axis-aligned here, so within 5 degrees means parallel) within 0.15 m of it, across and along.
  recall = matched reference length / reference length; precision = matched detected length / detected length.
- doors and windows: a reference opening is found when a detected one of the same type has its centre within 0.5 m.
- rooms: each reference room's largest rectangle centre is looked up in the detected rooms; type accuracy is the
  share of reference rooms whose type matches there; area error is the mean |detected - reference| / reference over
  the rooms found.
"""
import json, math, sys

M = 0.3048                      # metres per foot
TOL = 0.15 / M                  # walls: 0.15 m, in feet
OPEN_TOL = 0.5 / M              # openings: 0.5 m
STEP = 0.1


def centre_lines(f):
    """walls as (horizontal, across, a0, a1) centre lines in feet"""
    out = []
    for w in f.get("walls", []):
        x0, x1, y0, y1 = w[:4]
        if x1 - x0 >= y1 - y0:
            out.append((True, (y0 + y1) / 2, x0, x1))
        else:
            out.append((False, (x0 + x1) / 2, y0, y1))
    return out


def matched_length(a, b):
    """length of the centre lines a lying within TOL of a parallel centre line of b"""
    total = hit = 0.0
    for h, c, a0, a1 in a:
        n = max(1, int((a1 - a0) / STEP))
        for i in range(n):
            t = a0 + (i + 0.5) * (a1 - a0) / n
            total += (a1 - a0) / n
            if any(h2 == h and abs(c2 - c) <= TOL and b0 - TOL <= t <= b1 + TOL for h2, c2, b0, b1 in b):
                hit += (a1 - a0) / n
    return hit, total


def openings(f, kind):
    return [((o["rect"][0] + o["rect"][1]) / 2, (o["rect"][2] + o["rect"][3]) / 2)
            for o in f.get("openings", []) if o.get("type") == kind]


def area(r):
    return sum((q[1] - q[0]) * (q[3] - q[2]) for q in r.get("rects", []))


def room_at(f, x, y):
    for r in f.get("rooms", []):
        if any(q[0] <= x <= q[1] and q[2] <= y <= q[3] for q in r.get("rects", [])):
            return r
    return None


def score(det, ref):
    rows = []
    for k, rf in enumerate(ref["floors"]):
        df = det["floors"][k] if k < len(det["floors"]) else {"walls": [], "openings": [], "rooms": []}
        a, b = centre_lines(rf), centre_lines(df)
        hit_r, len_r = matched_length(a, b)
        hit_d, len_d = matched_length(b, a)
        row = dict(floor=rf.get("name") or f"Floor {k}",
                   wall_recall=round(hit_r / len_r, 3) if len_r else None,
                   wall_precision=round(hit_d / len_d, 3) if len_d else None,
                   wall_m_reference=round(len_r * M, 1), wall_m_detected=round(len_d * M, 1),
                   wall_m_missed=round((len_r - hit_r) * M, 1))
        for kind in ("door", "window"):
            rp, dp = openings(rf, kind), openings(df, kind)
            found = sum(any(math.hypot(x - u, y - v) <= OPEN_TOL for u, v in dp) for x, y in rp)
            row[kind + "s"] = f"{found}/{len(rp)} found, {len(dp)} detected"
        types = errors = found = 0
        rooms = [r for r in rf.get("rooms", []) if r.get("rects")]
        for r in rooms:
            q = max(r["rects"], key=area_of)
            d = room_at(df, (q[0] + q[1]) / 2, (q[2] + q[3]) / 2)
            if d is None:
                continue
            found += 1
            types += d.get("type") == r.get("type")
            errors += abs(area(d) - area(r)) / max(area(r), 1e-6)
        row.update(room_type_accuracy=round(types / len(rooms), 3) if rooms else None,
                   room_area_error=round(errors / found, 3) if found else None, rooms=f"{found}/{len(rooms)} found")
        rows.append(row)
    return rows


def area_of(q):
    return (q[1] - q[0]) * (q[3] - q[2])


if __name__ == "__main__":
    det, ref = (json.load(open(p)) for p in sys.argv[1:3])
    rows = score(det, ref)
    if "--json" in sys.argv:
        print(json.dumps(rows, indent=1))
    else:
        for r in rows:
            print(" | ".join(f"{k} {v}" for k, v in r.items()))
