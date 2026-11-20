"""Which doors and windows the vector detector misses in a round-trip run, and what it read there.

    uv --directory backend run python ../tools/roundtrip/missed.py RUN_DIR [door|window]
"""
import json
import sys
from collections import Counter
from pathlib import Path

from app.modules.ai.floorplan.model.embed import read_embedded_model
from app.modules.ai.floorplan.model.planto3d import to_planto3d
from app.modules.plan3d.compare import MATCH_FT, _centre, _shift, _walls

run = Path(sys.argv[1])
kind = sys.argv[2] if len(sys.argv) > 2 else "door"
why = Counter()
for pdf in sorted(run.glob("rt??.pdf")):
    emb = read_embedded_model(pdf.read_bytes())
    truth = to_planto3d(emb.building)["floors"][0]
    det_all = json.loads(pdf.with_name(pdf.stem + ".plain.det.json").read_text())["floors"]
    det = max(det_all, key=lambda f: len(f["walls"]))
    tw, rw = _walls(truth), _walls(det)
    read = _shift(det, min(w[0] for w in tw) - min(w[0] for w in rw), min(w[2] for w in tw) - min(w[2] for w in rw))
    rooms = truth["rooms"]

    def room_at(x, y):
        return next((r["label"] for r in rooms for q in r["rects"] if q[0] <= x <= q[1] and q[2] <= y <= q[3]), "-")

    for o in [o for o in truth["openings"] if o["type"] == kind]:
        c = _centre(o["rect"])
        near = [(abs(_centre(q["rect"])[0] - c[0]) + abs(_centre(q["rect"])[1] - c[1]), q) for q in read["openings"]]
        hit = [q for d, q in near if d <= MATCH_FT and q.get("axis") == o.get("axis") and
               (q["type"] in ({"door", "opening"} if kind == "door" else {"window"}))]
        if hit:
            continue
        close = sorted(near, key=lambda t: t[0])[:1]
        width = max(o["rect"][1] - o["rect"][0], o["rect"][3] - o["rect"][2])
        a = (c[0] - (0.6 if o["axis"] == "y" else 0), c[1] - (0.6 if o["axis"] == "x" else 0))
        b = (c[0] + (0.6 if o["axis"] == "y" else 0), c[1] + (0.6 if o["axis"] == "x" else 0))
        sides = f"{room_at(*a)} | {room_at(*b)}"
        got = f"{close[0][1]['type']} at {close[0][0]:.1f} ft" if close else "nothing"
        reason = "read as " + close[0][1]["type"] if close and close[0][0] <= 2 else "not read"
        why[reason] += 1
        print(f"{pdf.stem} {kind} {width:.1f} ft between {sides}: nearest {got}")
print(dict(why))
