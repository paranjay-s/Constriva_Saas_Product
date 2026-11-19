"""The plan verifier (verify.py).  python3 tests/test_verify.py"""
import glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import checks, verify  # noqa: E402

# ground truth: generated plans are drawn right, so nothing critical and no warnings
plans = sorted(glob.glob(os.path.join(HERE, "..", "..", "..", "docs", "overnight", "testplans", "p*.json")))
bad = [(os.path.basename(p), i["kind"]) for p in plans for i in verify.verify(json.load(open(p))) if i["severity"] != "info"]
assert not bad, bad[:5]

W = lambda x0, x1, y0, y1: [x0, x1, y0, y1, 0]
box = [W(0, 20, 0, 0.5), W(0, 20, 15.5, 16), W(0, 0.5, 0, 16), W(19.5, 20, 0, 16), W(9.75, 10.25, 0, 16)]
plan = {"floors": [{"name": "G", "walls": box, "rooms": [
    dict(label="A", type="bedroom", rects=[[0.5, 9.75, 0.5, 15.5]]),
    dict(label="B", type="living", rects=[[8, 19.5, 0.5, 15.5]]),           # overlaps A by ~25 sq ft
    dict(label="C", type="", rects=[[30, 35, 30, 35]]),                       # no type, no walls
], "openings": [
    dict(type="window", rect=[9.75, 10.25, 6, 9], axis="y"),                  # between A and B
    dict(type="door", rect=[19.5, 20, 2, 5], axis="y"),
], "stairs": [dict(rect=[1, 4, 1, 8], axis="y", up=True, words=[])]},
    {"name": "F", "walls": [W(0, 20, 0, 0.5)], "rooms": [dict(label="T", type="bedroom", rects=[[40, 60, 40, 60]])],
     "openings": [], "stairs": []}]}
kinds = {(i["kind"], i["severity"]) for i in verify.verify(plan)}
for want in [("room_overlap", "critical"), ("untyped_room", "critical"), ("window_inside", "warning"),
             ("stair_no_landing", "warning"), ("floor_overhang", "warning"), ("open_room", "info")]:
    assert want in kinds, (want, kinds)
plan["stated_area_sqft"] = 1000
assert any(i["kind"] == "area_total" for i in verify.verify(plan))
merged = checks.all_checks(plan)
assert merged[0]["severity"] == "critical" and all("severity" in c for c in merged)
print(f"ok   verifier: {len(plans)} true plans with no warning, {len(kinds)} kinds found on a broken plan")
