"""Area specs (areaspec.py): a valid spec builds, anything out of the schema or its limits is refused (the area is then a
generic zone), the library keeps specs by type name.  python3 tests/test_areas.py"""
import os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import areaspec  # noqa: E402

HELIPAD = dict(type="helipad", name="Helipad", description="Landing pad", surface="concrete", edge="kerb",
               height=dict(mode="raised", value_m=0.3), walkable=True,
               markings=[dict(kind="circle", centre=[0.5, 0.5], radius=0.4, width_m=0.3),
                         dict(kind="text", at=[0.5, 0.5], text="H", size_m=4.0)],
               objects=[dict(part="lamp", at=[0.05, 0.05], rot=0)])
clean, bad = areaspec.validate(HELIPAD)
assert not bad and clean["type"] == "helipad", bad
boxes, objs, walkable = areaspec.parts(clean, [0, 40, 0, 40])
assert walkable and len(objs) == 1 and len(boxes) > 30, len(boxes)     # surface, kerb, ring segments, the letter
assert all(len(b) == 7 and b[0] < b[1] and b[2] < b[3] for b in boxes)
assert max(b[5] for b in boxes if b[6] == "concrete") > 0.9            # raised 0.3 m

BAD = [
    dict(HELIPAD, type="__import__('os')"),                       # not a plain name
    dict(HELIPAD, surface="lava"),                                # not in the list
    dict(HELIPAD, edge="moat"),
    dict(HELIPAD, height=dict(mode="raised", value_m=50)),         # beyond the limit
    dict(HELIPAD, walkable="yes"),
    dict(HELIPAD, markings=[dict(kind="line", **{"from": [0, 0]}, to=[2, 2], width_m=0.1)]),   # outside the area
    dict(HELIPAD, markings=[dict(kind="text", at=[0.5, 0.5], text="<script>", size_m=1)]),
    dict(HELIPAD, markings=[dict(kind="line", **{"from": [0, 0]}, to=[1, 1], width_m=0.1)] * 41),
    dict(HELIPAD, objects=[dict(part="rocket", at=[0.5, 0.5], rot=0)]),
    dict(HELIPAD, name="x" * 100),
    "not a spec",
]
for b in BAD:
    clean_b, problems = areaspec.validate(b)
    assert clean_b is None and problems, b
# a refused or missing spec builds as the generic zone
gb, go, gw = areaspec.parts(None, [0, 10, 0, 10])
assert gw and not go and gb[0][6] == "concrete"

with tempfile.TemporaryDirectory() as tmp:
    areaspec.LIBRARY = os.path.join(tmp, "areas", "library.json")
    areaspec.save(HELIPAD, source="ai", reviewed=False)
    assert areaspec.spec_for("Helipad")["surface"] == "concrete"
    assert areaspec.load()["helipad"]["reviewed"] is False
    try:
        areaspec.save(BAD[1])
        raise AssertionError("an invalid spec was saved")
    except ValueError:
        pass
print(f"ok   area specs: 1 valid, {len(BAD)} refused, library round trip")
