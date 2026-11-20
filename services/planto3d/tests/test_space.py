"""Space (PART C1): furniture scaled to the room, fewer pieces in small rooms, a 0.9 m walk-way at the bed's
foot, a full-length mirror in dressing rooms. python3 tests/test_space.py"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import furnish  # noqa: E402

FAILS = []


def check(ok, msg):
    print(("ok   " if ok else "FAIL ") + msg)
    if not ok:
        FAILS.append(msg)


def floor(rooms, doors=()):
    """one storey: rooms (type, x0, x1, y0, y1) in feet, walls round each room, doors (x0, x1, y0, y1, axis)"""
    walls, zones = [], []
    for t, x0, x1, y0, y1 in rooms:
        w = 0.5
        walls += [[x0 - w, x1 + w, y0 - w, y0, 0], [x0 - w, x1 + w, y1, y1 + w, 0],
                  [x0 - w, x0, y0, y1, 0], [x1, x1 + w, y0, y1, 0]]
        zones.append(dict(type=t, label=t.upper(), rects=[[x0, x1, y0, y1]]))
    openings = [dict(type="door", rect=list(d[:4]), axis=d[4]) for d in doors]
    return dict(name="Ground", walls=walls, openings=openings, rooms=zones, stairs=[])


def items(fl, fn):
    return [i for i in furnish.furnish_floor(fl) if i["fn"] == fn]


def bed_box(fl):
    return items(fl, "bed")[0]["box"]


# a bed's foot keeps 3 ft (0.9 m) to the opposite wall when the room allows it
big = floor([("bedroom", 0, 12, 0, 13)], [(4, 7, -0.5, 0, "x")])
b = bed_box(big)
# the head is against a wall; the foot is the far end of the bed's long side
foot = max(b[2] - 0, 13 - b[3]) if (b[1] - b[0]) < (b[3] - b[2]) else max(b[0], 12 - b[1])
check(foot >= 3.0 - 0.05, f"12 x 13 ft bedroom: {foot:.2f} ft clear at the bed's foot (>= 3.0)")
# bed size scales with the room
k = floor([("bedroom", 0, 15, 0, 16)], [(6, 9, -0.5, 0, "x")])
q = floor([("bedroom", 0, 10, 0, 12)], [(4, 7, -0.5, 0, "x")])
n = floor([("bedroom", 0, 8.2, 0, 12)], [(3, 6, -0.5, 0, "x")])
widths = [items(f, "bed")[0]["kw"]["w"] for f in (k, q, n)]
check(widths == [6.0, 5.0, 3.5], f"bed widths for 15, 10 and 8.2 ft wide rooms: {widths} (king, queen, single)")
# a tight bedroom still gets its bed
check(len(items(n, "bed")) == 1, "8.2 x 12 ft bedroom keeps a bed")
# small rooms: fewer pieces; solid furniture covers at most 38 % of the floor
small = floor([("living", 0, 9, 0, 11)], [(3, 6, -0.5, 0, "x")])
solid = [i for i in furnish.furnish_floor(small) if i["solid"] and i["fn"] != "rug"]
cover = sum((i["box"][1] - i["box"][0]) * (i["box"][3] - i["box"][2]) for i in solid) / (9 * 11)
check(cover <= 0.38 + 1e-6, f"9 x 11 ft living room: furniture covers {cover:.0%} (<= 38 %)")
# dressing rooms get a full-length mirror
dr = floor([("dress", 0, 7, 0, 9)], [(2, 4.5, -0.5, 0, "x")])
check(len(items(dr, "wall_mirror")) == 1, "a dressing room gets a full-length mirror")
print(f"{len(FAILS)} failed")
sys.exit(1 if FAILS else 0)
