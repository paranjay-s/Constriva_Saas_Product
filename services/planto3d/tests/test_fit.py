"""Rooms sized to their labels (fit.py).  python3 tests/test_fit.py"""
import copy, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import detect, fit  # noqa: E402

T = 0.5


def plan_row(sizes, k=1.0, labels=None, unit_labels=None):
    """rooms side by side along x, each drawn at its size times k, walls T thick between and around"""
    walls, rooms, x = [], [], 0.0
    h = max(b for _, b in sizes) * k
    walls.append([0, T, 0, h + 2 * T, 0])
    for n, (a, b) in enumerate(sizes):
        x0 = x + T
        rooms.append(dict(label=f"R{n}", type="bedroom", rects=[[x0, x0 + a * k, T, T + b * k]],
                          dims=list((labels or sizes)[n])))
        x = x0 + a * k
        walls.append([x, x + T, 0, h + 2 * T, 0])
    walls += [[0, x + T, 0, T, 0], [0, x + T, h + T, h + 2 * T, 0]]
    return {"floors": [{"name": "G", "walls": walls, "rooms": rooms, "openings": [], "stairs": []}]}


def offs(plan):
    return [fit._off(r, T) for r in plan["floors"][0]["rooms"]]


# drawn 3 % small everywhere (a scale error): after the fit every room is within 1 % of its label
p = plan_row([(12, 10), (10, 10), (14, 10), (8, 10)], k=0.97)
before = offs(p)
rep, _ = fit.fit_plan(p)
after = offs(p)
assert max(before) > 0.025 and max(after) <= 0.02 and sum(after) < sum(before) / 3, (before, after)
# walls keep their thickness, and neighbours still share their wall
f = p["floors"][0]
assert all(abs((w[1] - w[0]) - T) < 0.02 for w in f["walls"] if w[1] - w[0] < w[3] - w[2]), f["walls"]
rs = [r["rects"][0] for r in f["rooms"]]
assert all(abs((b[0] - a[1]) - T) < 0.02 for a, b in zip(rs, rs[1:])), rs

# one room drawn far off its label (30 %, still 18 % by centre lines) is reported and left alone; the others are still fitted
p = plan_row([(12, 10), (10, 10), (14, 10), (8, 10)], labels=[(12, 10), (10, 10), (14, 10), (8 * 1.3, 10)])
rep, _ = fit.fit_plan(p)
assert [r["label"] for r in rep["reported"]] == ["R3"], rep

# metre labels (parsed by the detector into feet) fit the same way
a, b, unit = detect.parse_size("4.20 x 3.60 m")
p = plan_row([(a, b), (a, b), (a, b)], k=1.04, labels=[(a, b)] * 3)
fit.fit_plan(p)
assert max(offs(p)) <= 0.02 and unit == "m", offs(p)

# nothing labelled: nothing moves
p = plan_row([(12, 10)])
p["floors"][0]["rooms"][0].pop("dims")
q = copy.deepcopy(p)
fit.fit_plan(p)
assert p["floors"] == q["floors"]
# walls already right, but the reader's room rectangle spans two rooms (and stops at a wall centre): measured from
# where the name is written, between the walls, every room already matches; nothing moves
p = plan_row([(12, 10), (10, 10), (14, 10)])
f = p["floors"][0]
r0, r1 = f["rooms"][0], f["rooms"][1]
r0["label_at"] = [(r0["rects"][0][0] + r0["rects"][0][1]) / 2, 5.0]
r0["rects"] = [[r0["rects"][0][0], r1["rects"][0][1], T / 2, T + 10]]       # spans R0 and R1, bottom at a wall centre
walls_before = copy.deepcopy(f["walls"])
fit.fit_plan(p)
assert f["walls"] == walls_before, (walls_before, f["walls"])

print("ok   size fit: scale error removed (every room within 2 %), walls and neighbours kept, a room 30 % off reported, metres work, a wrong room rectangle moves no wall")
