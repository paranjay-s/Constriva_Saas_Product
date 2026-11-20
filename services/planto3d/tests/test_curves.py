"""Curved walls, round rooms and their furniture (feat/pro_2, C3.1). python3 tests/test_curves.py
(The drawing -> detector round trip is backend/tests/floorplan/test_fp_curves.py.)"""
import math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import curves, furnish  # noqa: E402

FAILS = []


def check(ok, msg):
    print(("ok   " if ok else "FAIL ") + msg)
    if not ok:
        FAILS.append(msg)


# a disc as row slices: every corner inside the circle, area close to pi r^2
rs = curves.disc_rects(10, 10, 6)
inside = all(math.hypot(x - 10, y - 10) <= 6 + 0.005 for q in rs for x in q[:2] for y in q[2:])
area = sum((q[1] - q[0]) * (q[3] - q[2]) for q in rs)
check(inside, "disc slices stay inside the circle")
check(0.9 * math.pi * 36 <= area <= math.pi * 36, f"disc slices cover {area / (math.pi * 36):.0%} of the disc")

# a curved wall band: quads all between the two radii
qs = curves.sector_quads(0, 0, 9.6, 10.4, 30, 150)
ok = all(9.6 - 1e-6 <= math.hypot(*p) <= 10.4 + 1e-6 for q in qs for p in q)
check(ok and len(qs) == 20, f"a 120-degree band in {len(qs)} pieces between its faces")

# the span of a curve from its pieces' end points: whole circle, half circle, and one across 0 degrees
P = lambda a: (math.cos(math.radians(a)), math.sin(math.radians(a)))
full = [P(a) for k in range(4) for a in (k * 90, k * 90 + 90)]
half = [P(a) for k in range(2) for a in (k * 90, k * 90 + 90)]
wrap = [P(300), P(360), P(0), P(60)]
check(curves.angle_span(0, 0, full) == (0.0, 360.0), "four quarter pieces: a whole circle")
check(curves.angle_span(0, 0, half) == (0.0, 180.0), f"two quarter pieces: half a circle {curves.angle_span(0, 0, half)}")
a0, a1 = curves.angle_span(0, 0, wrap)
check(abs(a1 - a0 - 120) < 0.1, f"an arc across 0 degrees spans 120 ({a0}..{a1})")

# concentric pairs a wall thick apart are curved walls; a single arc (a door swing) is not
s, T = 10.0, 2.0
circles = [(100, 100, 60, [(160, 100), (100, 160)]), (100, 100, 68, [(168, 100), (100, 168)]),
           (300, 300, 30, [(330, 300), (300, 330)])]
walls = curves.curved_walls(circles, T * 4, s)
check(len(walls) == 1 and walls[0][2:4] == (60, 68), f"one curved wall from a concentric pair ({len(walls)})")

# a room that fills a whole circle of curved wall is round; one beside a half circle is not
arcs = [dict(c=[10, 10], r=6.3, t=0.6, a0=0.0, a1=360.0)]
check(curves.round_room(curves.disc_rects(10, 10, 6), arcs) == [10, 10, 6.0], "a room filling a circle is round")
check(curves.round_room([[4, 16, 4, 16]], [dict(arcs[0], a1=180.0)]) is None, "a room with one curved side is not round")
check(curves.in_arc_band(16.3, 10, arcs[0]) and not curves.in_arc_band(10, 10, arcs[0]), "points on and off a curved wall")

# furniture in a round room stands round the centre, inside the circle
room = dict(type="living", label="ROTUNDA", circle=[20, 20, 9], rects=curves.disc_rects(20, 20, 9))
items = furnish.furnish_floor(dict(rooms=[room], walls=[], openings=[], stairs=[]))
fns = sorted(i["fn"] for i in items)
inside = all(math.hypot(x - 20, y - 20) <= 9 + 0.01 for i in items if i["solid"] for x in i["box"][:2] for y in i["box"][2:])
check({"round_rug", "coffee_table", "sofa"} <= set(fns), f"round living room: {fns}")
check(inside, "every solid piece stands inside the circle")
# a dash-dot (chain) pattern is a property, setback or centre line, never a wall face; plain dashes are kept
import vector  # noqa: E402
check(vector.chain_line("7.09 1.42 1.42 1.42") and vector.chain_line("17.01 2.83 2.27 2.83"), "chain lines are skipped")
check(not vector.chain_line("4.25 2.83") and not vector.chain_line(None), "plain dashes and solid lines are kept")
print(f"{len(FAILS)} failed")
sys.exit(1 if FAILS else 0)
