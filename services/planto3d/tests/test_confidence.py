"""Source and confidence of every room and opening (checks.annotate).  python3 tests/test_confidence.py"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import checks  # noqa: E402

R = lambda label, typ, rect, **kw: dict(label=label, type=typ, rects=[rect], **kw)
plan = {"floors": [{"name": "Ground", "walls": [], "rooms": [
    R("BEDROOM", "bedroom", [0, 12, 0, 12]),
    R("BEDR", "bedroom", [12, 24, 0, 12]),
    R("KICHEN", "kitchen", [36, 48, 0, 12]),
    R("ZORBLAX", "multipurpose", [24, 36, 0, 12]),
    R("HELIPAD", "custom", [0, 40, 20, 60], src="ai", confidence=0.9),
    R("", "garden", [40, 60, 20, 60]),
], "openings": [
    dict(type="door", rect=[11.8, 12.2, 4, 7], axis="y", hinge=[12, 4]),     # between two bedrooms, with a leaf
    dict(type="door", rect=[100, 103, 100, 100.3], axis="x"),                # no room on either side
    dict(type="window", rect=[2, 6, -0.2, 0.2], axis="x"),
]}]}
checks.annotate(plan, "detector")
f = plan["floors"][0]
conf = {r["label"]: r["conf"] for r in f["rooms"]}
assert conf["BEDROOM"] == 0.95 and conf["BEDR"] == 0.8 and conf["KICHEN"] == 0.6, conf  # exact, abbreviation, fuzzy
assert conf["ZORBLAX"] <= 0.3, conf                                        # unknown: capped by its check
assert conf["HELIPAD"] == 0.9 and f["rooms"][4]["src"] == "ai", conf       # the AI's own confidence
assert [o["conf"] for o in f["openings"]] == [0.9, 0.3, 0.8], f["openings"]
assert all(x["src"] == "detector" for x in f["rooms"][:3] + f["openings"])
assert f["wall_src"] == "detector" and f["wall_conf"] == 0.8
# a person's save: what they add is theirs, the rest keeps its source and confidence
f["rooms"].append(R("STUDY", "study", [60, 70, 0, 10]))
checks.annotate(plan, "user")
assert f["rooms"][-1]["src"] == "user" and f["rooms"][-1]["conf"] == 1.0
assert f["rooms"][0]["src"] == "detector" and f["rooms"][0]["conf"] == 0.95
# an AI read is trusted less than the detector for the same drawing
ai = json.loads(json.dumps(plan))
for fl in ai["floors"]:
    fl.pop("wall_src")
    for x in fl["rooms"] + fl["openings"]:
        if x.get("src") == "detector":
            x.pop("src")
checks.annotate(ai, "ai")
assert ai["floors"][0]["rooms"][0]["conf"] < 0.95 and ai["floors"][0]["wall_conf"] < 0.8
print(f"ok   confidence: rooms {plan['confidence']['rooms']}, openings {plan['confidence']['openings']} on average")
