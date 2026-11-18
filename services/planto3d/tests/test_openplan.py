"""Open plan: one walled space with a kitchen, a dining and a living zone side by side (no walls between them).
Every zone is furnished, nothing overlaps, furniture of neighbouring zones keeps a passage of at least 0.9 m (2.95 ft),
and every zone can be reached on foot from the front door.  python3 tests/test_openplan.py"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import furnish  # noqa: E402

T = 0.75
W, D = 42.0, 22.0
ZONES = [("kitchen", "KITCHEN", (0, 13)), ("dining", "DINING", (13, 26)), ("living", "LIVING", (26, W))]
walls = [[-T, W + T, -T, 0, 0], [-T, W + T, D, D + T, 0], [-T, 0, 0, D, 0], [W, W + T, 0, D, 0]]
door = dict(type="door", rect=[30.0, 33.0, -T, 0], axis="x")
walls = [[-T, 30.0, -T, 0, 0], [33.0, W + T, -T, 0, 0]] + walls[1:]
rooms = [dict(type=t, label=l, area=(b - a) * D, rects=[[a, b, 0, D]]) for t, l, (a, b) in ZONES]
floor = dict(walls=walls, openings=[door], rooms=rooms, stairs=[])

items = furnish.furnish_floor(floor)
fails = []
for t, l, _ in ZONES:
    if not any(i["room"] == l and i["solid"] for i in items):
        fails.append(f"the {l} zone has no furniture")
fails += furnish.clashes(items, floor)
# each zone holds its own function only: no second sofa group in the dining zone (the living zone has one)
if any(i["room"] == "DINING" and i["fn"] == "sofa" for i in items):
    fails.append("the dining zone has a sofa group as well as the living zone")
PASSAGE = 0.9 / 0.3048
for i, a in enumerate(items):
    for b in items[i + 1:]:
        if a["room"] == b["room"] or not (a["solid"] and b["solid"]):
            continue
        gap = max(b["box"][0] - a["box"][1], a["box"][0] - b["box"][1], b["box"][2] - a["box"][3], a["box"][2] - b["box"][3])
        if gap < PASSAGE:
            fails.append(f"{a['fn']} ({a['room']}) and {b['fn']} ({b['room']}) are {gap * 0.3048:.2f} m apart")
# walk from the door over a 0.5 ft grid, around solid furniture (the walker is about 1.5 ft wide)
g = 0.5
nx, ny = int(W / g), int(D / g)
R = 0.75
def free(i, j):
    x, y = (i + 0.5) * g, (j + 0.5) * g
    return not any(it["solid"] and it["box"][0] - R < x < it["box"][1] + R and it["box"][2] - R < y < it["box"][3] + R for it in items)
seen, todo = set(), [(int(31.5 / g), 1)]
while todo:
    c = todo.pop()
    if c in seen or not (0 <= c[0] < nx and 0 <= c[1] < ny) or not free(*c):
        continue
    seen.add(c)
    todo += [(c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)]
for t, l, (a, b) in ZONES:
    if not any(a <= (i + 0.5) * g <= b for i, j in seen):
        fails.append(f"the {l} zone cannot be reached from the door")
assert abs(sum(r["area"] for r in rooms) - W * D) < 1e-6        # the zones fill the space exactly
for f in fails:
    print("FAIL", f)
print(f"{'FAIL' if fails else 'ok  '} open plan: {len(items)} items in {len(ZONES)} zones, {len(fails)} problems")
sys.exit(1 if fails else 0)
