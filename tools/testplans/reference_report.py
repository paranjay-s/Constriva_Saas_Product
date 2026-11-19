"""The reference plans through the whole pipeline, as the gateway runs it: what each one produces.

    uv --directory backend run python ../tools/testplans/reference_report.py [--dump DIR]

PDFs in docs/reference/plans/ (local only, never committed). Readers in the gateway's order (PlanTo3D's detector,
then the AI plan reader, converted), then the server's size fit and the verifier (checks.all_checks). These plans have
no ground truth here, so nothing is scored and nothing may be tuned to them: the table shows the reader, storeys,
rooms, how many labelled rooms are within 2 % of their label (measured between the walls), and the verifier's
findings by severity. AI replies come from the cache; a reference plan without one is read live (counted).
"""

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import score_all  # noqa: E402

ROOT = HERE.parents[1]
P3D = ROOT / "services/planto3d"
sys.path.insert(0, str(P3D))


def within(plan):
    import fit

    wall = plan["wall_pt"] / plan["scale_pt_per_ft"] if plan.get("wall_pt") and plan.get("scale_pt_per_ft") else 0.5
    n = ok = 0
    for f in plan.get("floors", []):
        walls = [w for w in f.get("walls", []) if len(w) >= 4]
        rooms = [fit.wall_box(r, walls) for r in f.get("rooms", []) if len(r.get("rects") or []) == 1 and r.get("dims")]
        if not rooms or not walls:
            continue
        c = fit.convention(rooms, walls, wall)
        for r in rooms:
            n += 1
            ok += fit.targets(r, walls, wall, c)[2] <= 0.02
    return ok, n


def main() -> None:
    import checks

    dump = Path(sys.argv[sys.argv.index("--dump") + 1]) if "--dump" in sys.argv else None
    rows, fresh = [], 0
    for pdf in sorted((ROOT / "docs/reference/plans").glob("*.pdf")):
        plan, reader = score_all.detect(pdf), "detector"
        if plan is None:
            reader = "ai"
            fresh += not score_all.cached(pdf)
            plan = score_all.ai_read(pdf)
        if not plan or not plan.get("floors"):
            rows.append(f"| {pdf.stem[:28]} | none | - | - | - | - |")
            continue
        plan = score_all.fitted(plan)
        ok, n = within(plan)
        sev = Counter(c.get("severity", "?") for c in checks.all_checks(plan))
        rooms = sum(len(f.get("rooms", [])) for f in plan["floors"])
        rows.append(f"| {pdf.stem[:28]} | {reader} | {len(plan['floors'])} | {rooms} | "
                    f"{f'{ok}/{n}' if n else '-'} | {sev.get('critical', 0)} / {sev.get('warning', 0)} / {sev.get('info', 0)} |")
        if dump:
            dump.mkdir(parents=True, exist_ok=True)
            (dump / f"{pdf.stem}.json").write_text(json.dumps(plan))
    print(f"Reference plans, full pipeline ({fresh} fresh AI calls)\n")
    print("| plan | reader | storeys | rooms | labelled rooms within 2 % | checks critical / warning / info |")
    print("|---|---|---|---|---|---|")
    print("\n".join(rows))


if __name__ == "__main__":
    main()
