"""The detector on the made-up sample drawing (examples/sample_plan.pdf): every wall, door, window and room must be
found, and the scale read from the room sizes.  python3 tests/test_sample.py"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE), os.path.join(os.path.dirname(HERE), "examples")]
import detect  # noqa: E402
import make_sample as M  # noqa: E402

plan = detect.detect(os.path.join(HERE, "..", "examples", "sample_plan.pdf"))
assert plan["scale_source"] == "labels" and abs(plan["scale_pt_per_ft"] - M.S) < 0.02 * M.S, plan["scale_pt_per_ft"]
assert len(plan["floors"]) == 1, [f["name"] for f in plan["floors"]]
f = plan["floors"][0]
assert f["name"] == "Ground Floor" and all(abs(a - b) < 0.1 for a, b in zip(f["size"], M.EXPECT["size"])), (f["name"], f["size"])
kinds = [o["type"] for o in f["openings"]]
assert (kinds.count("door"), kinds.count("window")) == (M.EXPECT["doors"], M.EXPECT["windows"]), kinds
assert sorted(r["type"] for r in f["rooms"]) == M.EXPECT["rooms"], [r["type"] for r in f["rooms"]]
# every drawn opening is where the drawing puts it (to a tenth of a foot)
drawn = [(k, *((c0, c1, y0, y1) if x1 - x0 > y1 - y0 else (x0, x1, c0, c1)))
         for (x0, x1, y0, y1), cuts in M.WALLS for k, c0, c1, _ in cuts]
for k, *r in drawn:
    assert any(o["type"] == k and all(abs(a - b) < 0.1 for a, b in zip(o["rect"], r)) for o in f["openings"]), (k, r)
print("ok   sample plan: %d walls, %d doors, %d windows, %d rooms, scale %.1f pt/ft" % (
    len(f["walls"]), kinds.count("door"), kinds.count("window"), len(f["rooms"]), plan["scale_pt_per_ft"]))
