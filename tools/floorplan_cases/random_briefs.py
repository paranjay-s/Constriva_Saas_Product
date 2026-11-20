"""A1 task 8: random briefs must all produce a plan; count how often each ladder rung is used.

    uv --directory backend run python ../tools/floorplan_cases/random_briefs.py N OUT.json
        [--seed 7] [--time 8]

Briefs: 1-12 rooms, plot 1,000-15,000 sq ft (half with a stated width and depth, half area
only), half with a stated built-up area (40-95 % of the plot), random road side, and 0-4 random
wishes (sides and touching rooms, contradictions allowed). No AI: the room program uses the
typical sizes (llm=None), so the run is free and repeatable.
"""

import json
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path

os.environ.setdefault("TESTING", "1")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

FT = 30.48
EXTRAS = ["dining", "majlis", "maid_room", "study", "store", "toilet", "puja", "pool",
          "garden", "parking", "courtyard", "foyer", "family_hall", "gym", "prayer", "utility"]


def random_brief(rng: random.Random):
    from app.modules.ai.floorplan.schemas.brief import Brief, PlotSpec, RoomRequest
    from app.modules.ai.floorplan.schemas.rules import Place, Touches

    area_ft2 = rng.uniform(1000, 15000)
    n = rng.randint(1, 12)
    beds = rng.randint(0, min(5, n))
    rooms = []
    if beds:
        rooms.append(RoomRequest(type="master_bedroom", attached_bath=True,
                                 dress_room=rng.random() < 0.5))
        if beds > 1:
            rooms.append(RoomRequest(type="bedroom", count=beds - 1,
                                     attached_bath=rng.random() < 0.7))
    left = n - beds
    pool = rng.sample(EXTRAS, k=min(len(EXTRAS), max(0, left)))
    for t in ["living", "kitchen", *pool][: max(left, 0)]:
        rooms.append(RoomRequest(type=t))
    if not rooms:
        rooms = [RoomRequest(type="living")]
    stated_shape = rng.random() < 0.5
    ratio = rng.choice([(1, 1), (3, 4), (2, 3), (1, 2), (3, 2)])
    w_ft = (area_ft2 * ratio[0] / ratio[1]) ** 0.5
    d_ft = area_ft2 / w_ft
    plot = PlotSpec(width_cm=round(w_ft * FT), depth_cm=round(d_ft * FT), input_unit="ft",
                    shape_assumed=not stated_shape,
                    area_basis=None if stated_shape else "plot",
                    stated_area_m2=None if stated_shape else round(area_ft2 * 0.0929, 2))
    if rng.random() < 0.5:
        plot = plot.model_copy(update={"built_up_m2": round(
            area_ft2 * 0.0929 * rng.uniform(0.4, 0.95), 1)})
    types = [r.type for r in rooms]
    rules = []
    for _ in range(rng.randint(0, 4)):
        a = rng.choice(types)
        if rng.random() < 0.5:
            rules.append(Place(kind="place", room=a, text=f"{a} at the side",
                               side=rng.choice(["front", "rear", "left", "right", "centre"])))
        else:
            b = rng.choice(types)
            if b != a:
                rules.append(Touches(kind="touches", room=a, others=[b], text=f"{a} by {b}",
                                     door=rng.random() < 0.3))
    return Brief(plot=plot, bedrooms=beds, bathrooms=beds, rooms=rooms,
                 road_side=rng.choice(["south", "north", "east", "west"]), rules=rules)


def main() -> None:
    from app.modules.ai.floorplan.pipeline.generate import generate_plan

    args = sys.argv[1:]
    n, out = int(args[0]), Path(args[1])
    seed = int(args[args.index("--seed") + 1]) if "--seed" in args else 7
    limit = float(args[args.index("--time") + 1]) if "--time" in args else None
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        brief = random_brief(rng)
        t0 = time.time()
        try:
            res = generate_plan(brief, llm=None, solver_time_s=limit)
            row = {"status": res.status, "step": res.relax_step or "first pass",
                   "adjustments": res.adjustments, "log": res.relax_log,
                   "valid": bool(res.report and res.report.ok)}
        except Exception as e:  # a crash is a failure to deliver
            row = {"status": "error", "step": "error", "adjustments": [], "log": [repr(e)],
                   "valid": False}
        row.update(i=i, seconds=round(time.time() - t0, 1), rooms=len(brief.rooms),
                   plot_ft2=round(brief.plot.width_cm * brief.plot.depth_cm / FT**2),
                   built_up=bool(brief.plot.built_up_m2), rules=len(brief.rules),
                   shape_assumed=brief.plot.shape_assumed)
        rows.append(row)
        print(json.dumps({k: row[k] for k in ("i", "status", "step", "seconds", "rooms",
                                              "plot_ft2", "rules")}), flush=True)
        out.write_text(json.dumps(rows, indent=1))
    steps = Counter(r["step"] for r in rows)
    print("delivered", sum(r["status"] == "ok" for r in rows), "of", len(rows), dict(steps))


if __name__ == "__main__":
    main()
