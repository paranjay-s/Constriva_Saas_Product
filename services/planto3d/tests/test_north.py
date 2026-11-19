"""The north arrow (detect.north_arrow) on synthetic strokes: no PDF."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import detect  # noqa: E402


def arrow(cx, cy, deg, h=8.0):
    """a north arrow centred at (cx, cy) on the page (y down), pointing `deg` clockwise from up, with N at its tip"""
    a = math.radians(deg)
    ux, uy = math.sin(a), -math.cos(a)               # page direction of north
    tip = (cx + ux * 3 * h, cy + uy * 3 * h)
    tail = (cx - ux * 3 * h, cy - uy * 3 * h)
    px, py = -uy, ux
    segs = [(tail[0], tail[1], tip[0], tip[1], 0, 0.5),
            (tip[0], tip[1], tip[0] - ux * h + px * h * 0.6, tip[1] - uy * h + py * h * 0.6, 0, 0.5),
            (tip[0], tip[1], tip[0] - ux * h - px * h * 0.6, tip[1] - uy * h - py * h * 0.6, 0, 0.5)]
    for k in range(12):                                # a circle around the arrow
        t0, t1 = 2 * math.pi * k / 12, 2 * math.pi * (k + 1) / 12
        segs.append((cx + 2.5 * h * math.cos(t0), cy + 2.5 * h * math.sin(t0),
                     cx + 2.5 * h * math.cos(t1), cy + 2.5 * h * math.sin(t1), 0, 0.5))
    lx, ly = tip[0] + ux * 1.2 * h, tip[1] + uy * 1.2 * h
    return [(lx - h / 3, ly - h / 2, lx + h / 3, ly + h / 2, "N")], segs


ok = True
for deg in (0, 2, 30, 90, 200, 315):
    words, segs = arrow(500, 300, deg)
    got = detect.north_arrow(words + [(10, 10, 60, 20, "BEDROOM")], segs + [(0, 600, 800, 600, 1, 2)])
    want = 0.0 if min(deg, 360 - deg) <= 3 else deg
    good = got is not None and min(abs(got - want), 360 - abs(got - want)) <= 2
    ok &= good
    print(("ok  " if good else "FAIL") + f" north arrow at {deg} degrees: read {got}")
# a dart-shaped arrow (two long edges, no shaft) inside a circle, with a stray dimension tick beside it
def dart(cx, cy, deg, h=10.0):
    a = math.radians(deg)
    ux, uy = math.sin(a), -math.cos(a)
    px, py = -uy, ux
    tip, back = (cx + ux * 1.4 * h, cy + uy * 1.4 * h), (cx - ux * 1.4 * h, cy - uy * 1.4 * h)
    left, right = (back[0] + px * 0.75 * h, back[1] + py * 0.75 * h), (back[0] - px * 0.75 * h, back[1] - py * 0.75 * h)
    segs = [(tip[0], tip[1], left[0], left[1]), (tip[0], tip[1], right[0], right[1]),
            (left[0], left[1], cx - ux * 0.8 * h, cy - uy * 0.8 * h), (right[0], right[1], cx - ux * 0.8 * h, cy - uy * 0.8 * h)]
    for k in range(16):
        t0, t1 = 2 * math.pi * k / 16, 2 * math.pi * (k + 1) / 16
        segs.append((cx + 1.6 * h * math.cos(t0), cy + 1.6 * h * math.sin(t0), cx + 1.6 * h * math.cos(t1), cy + 1.6 * h * math.sin(t1)))
    lx, ly = tip[0] + ux * 1.6 * h, tip[1] + uy * 1.6 * h
    tick = [(lx - 4.3 * h, ly + 1.0 * h, lx - 3.7 * h, ly + 1.6 * h)]
    return [(lx - h / 3, ly - h / 2, lx + h / 3, ly + h / 2, "N")], [g + (0, 0.5) for g in segs + tick]


for deg in (0, 45, 160):
    words, segs = dart(400, 400, deg)
    got = detect.north_arrow(words, segs)
    want = 0.0 if min(deg, 360 - deg) <= 3 else deg
    good = got is not None and min(abs(got - want), 360 - abs(got - want)) <= 2
    ok &= good
    print(("ok  " if good else "FAIL") + f" dart arrow with a stray tick at {deg} degrees: read {got}")

# no arrow: an N in a room label is not a north arrow, nor a lone N with nothing drawn around it
print(("ok  " if detect.north_arrow([(100, 100, 106, 108, "N")], []) is None else "FAIL") + " a lone N without strokes")
ok &= detect.north_arrow([(100, 100, 106, 108, "N")], []) is None
if not ok:
    sys.exit(1)
