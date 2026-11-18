"""Detector accuracy against two hand-measured real plans. Those drawings are private and not part of the repository:
set PLANTO3D_FIXTURES to a folder holding plan.py, plan6.py (the measurements), opt6.pdf and sf.pdf, or this test is skipped.
Run: python3 tests/test_detect.py  -> per floor scores, fails if below the thresholds. (tests/test_sample.py always runs.)"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.environ.get("PLANTO3D_FIXTURES", "")
if not all(os.path.exists(os.path.join(FIX, f)) for f in ("plan.py", "plan6.py", "opt6.pdf", "sf.pdf")):
    print("skip test_detect.py: private fixtures not found (PLANTO3D_FIXTURES)")
    sys.exit(0)
sys.path[:0] = [os.path.dirname(HERE), FIX]
import detect  # noqa
import plan as P1  # noqa
import plan6 as P6  # noqa

OPT6, SF = os.path.join(FIX, "opt6.pdf"), os.path.join(FIX, "sf.pdf")
G = 0.25          # raster cell, feet
TOL = 2           # cells of slack (0.5 ft) for wall placement


def kind(key):
    k = key.split("_")[-1].rstrip("0123456789")
    return {"bed": "bedroom", "toi": "toilet", "mtoi": "toilet", "dress": "toilet", "kit": "kitchen",
            "liv": "living", "drg": "living", "din": "dining", "puja": "puja", "wash": "wash",
            "pass": "passage", "lobby": "passage", "ver": "balcony"}.get(k)


def truth():
    sh = lambda bs, dx: [(b[0] + dx, b[1] + dx, *b[2:]) for b in bs]
    gf = dict(walls=P6.GF_WALLS + [b for b, h in P6.GF_LOW], doors=P6.GF_DOORS,
              windows=[w[:4] for w in P6.GF_WINDOWS], rooms=[(kind(k), r[2][0]) for k, r in P6.GF_ROOMS.items()])
    fw = P6.FF_WALLS + [b for b, h in P6.FF_LOW]
    fd, fwin, fr = list(P6.FF_DOORS), [w[:4] for w in P6.FF_WINDOWS], []
    for tag, dx in (("A", 0), ("B", P6.SHIFT)):
        fw += sh(P6.FLAT_WALLS, dx) + sh([b for b, h in P6.FLAT_LOW], dx)
        fd += sh(P6.FLAT_DOORS, dx)
        fwin += sh([w[:4] for w in P6.FLAT_WINDOWS], dx)
        fr += [(kind(k), rects[0]) for k, _, _, rects in P6.flat_rooms(tag)]
    ff = dict(walls=fw, doors=fd, windows=fwin, rooms=fr)
    sf = dict(walls=P1.WALLS + [b for b, h in P1.LOW_WALLS], doors=[d[:4] for d in P1.DOORS],
              windows=[w[:4] for w in P1.WINDOWS], rooms=[(kind(k), r[2][0]) for k, r in P1.ROOMS.items()])
    return [(OPT6, 0, "opt6 ground", gf), (OPT6, 1, "opt6 first", ff), (SF, 0, "sf first", sf)]


def cells(rects):
    out = set()
    for r in rects:
        for i in range(round(r[0] / G), round(r[1] / G)):
            for j in range(round(r[2] / G), round(r[3] / G)):
                out.add((i, j))
    return out


def near(a, b, t=TOL):
    """fraction of cells of a within t cells of some cell of b"""
    if not a:
        return 0.0
    grow = {(i + di, j + dj) for i, j in b for di in range(-t, t + 1) for dj in range(-t, t + 1)}
    return sum(c in grow for c in a) / len(a)


def match(det, tru, d=1.6):
    """greedy centre matching of opening rects -> (recall, precision)"""
    c = lambda r: ((r[0] + r[1]) / 2, (r[2] + r[3]) / 2)
    used, hit = set(), 0
    for t in tru:
        tc = c(t)
        best = min(((abs(c(r)[0] - tc[0]) + abs(c(r)[1] - tc[1]), k) for k, r in enumerate(det) if k not in used),
                   default=(99, None))
        if best[0] <= d:
            used.add(best[1]); hit += 1
    return hit / max(1, len(tru)), hit / max(1, len(det))


def score(f, t):
    det_w = [w[:4] for w in f["walls"]]
    det_o = [o["rect"] for o in f["openings"]]
    tw = cells(t["walls"])
    # detected walls + openings ~ truth walls (truth walls run through their openings); find the best shift
    best = None
    for dx in range(-6, 7):
        for dy in range(-6, 7):
            dw = {(i + dx, j + dy) for i, j in cells(det_w + det_o)}
            sc = near(dw, tw) + near(tw, dw)
            if not best or sc > best[0]:
                best = (sc, dx, dy, near(dw, tw), near(tw, dw))
    _, dx, dy, wp, wr = best
    sx, sy = dx * G, dy * G
    mv = lambda r: (r[0] + sx, r[1] + sx, r[2] + sy, r[3] + sy)
    doors = [mv(o["rect"]) for o in f["openings"] if o["type"] in ("door", "opening")]
    wins = [mv(o["rect"]) for o in f["openings"] if o["type"] == "window"]
    dr, dp = match(doors, t["doors"])
    wr_, wp_ = match(wins, t["windows"])
    ok = 0
    for typ, r in t["rooms"]:
        x, y = (r[0] + r[1]) / 2 - sx, (r[2] + r[3]) / 2 - sy
        got = next((z["type"] for z in f["rooms"] for q in z["rects"] if q[0] <= x <= q[1] and q[2] <= y <= q[3]), None)
        ok += got == typ or {got, typ} == {"living", "dining"}
    return dict(shift=(sx, sy), wall_precision=wp, wall_recall=wr, door_recall=dr, door_precision=dp,
                window_recall=wr_, window_precision=wp_, rooms=ok / len(t["rooms"]))


# regression guards (current scores minus a margin), not targets
MIN = dict(wall_precision=0.85, wall_recall=0.9, door_recall=0.8, door_precision=0.55, window_recall=0.9,
           window_precision=0.9, rooms=0.95)

if __name__ == "__main__":
    cache, fails = {}, []
    for pdf, k, name, t in truth():
        if not os.path.exists(pdf):
            print(f"skip {name}: {pdf} missing")
            continue
        plan = cache.setdefault(pdf, detect.detect(pdf))
        sc = score(plan["floors"][k], t)
        print(f"{name:12s} " + "  ".join(f"{a}={b:.2f}" if isinstance(b, float) else f"{a}={b}" for a, b in sc.items()))
        fails += [f"{name} {a}={sc[a]:.2f} < {m}" for a, m in MIN.items() if sc[a] < m]
    s6 = cache.get(OPT6, {}).get("scale_pt_per_ft")
    if s6:
        print(f"opt6 scale {s6} (true 12.204)")
        if abs(s6 - 12.204) > 0.06:
            fails.append("opt6 scale off")
    print("FAIL:\n  " + "\n  ".join(fails) if fails else "PASS")
    sys.exit(1 if fails else 0)
