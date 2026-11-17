"""Run the floor plan eval set and print the pass rate.

    uv run python eval/floorplan/run_eval.py               # all cases (needs GEMINI_API_KEY)
    uv run python eval/floorplan/run_eval.py --no-llm      # only cases that need no AI
    uv run python eval/floorplan/run_eval.py --only t05_prompt_beats_form --jobs 1
    uv run python eval/floorplan/run_eval.py --out eval_result.json

Each case goes through the same path as the app: form + description -> brief -> plan.
A case passes when every expectation in cases.json holds:
    status          ok | infeasible | incomplete
    bedrooms        exact number of bedrooms in the plan
    baths_min       at least this many bathrooms
    attached_min    at least this many attached bathrooms
    has             room types that must be in the plan
    adjacent        [[a, b], ...] a room of type a shares a wall (>= 90 cm) with type b
    road_side       the plot's road side
    conflict        a form/description clash on this field was recorded
    warning_contains  text found in the warnings/notes shown to the person
    project_name    text found in the project name
    pool_layout     where the pool ended up: side | u_shape | centre | two_block
"""

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from app.modules.ai.floorplan.pipeline.brief_parser import parse_brief  # noqa: E402
from app.modules.ai.floorplan.pipeline.generate import generate_plan  # noqa: E402
from app.modules.ai.floorplan.schemas.brief import BriefForm  # noqa: E402
from app.modules.ai.floorplan.schemas.plan import FloorPlan, Room  # noqa: E402
from app.modules.ai.llm.client import get_llm  # noqa: E402

CASES = Path(__file__).with_name("cases.json")
BEDROOMS = ("bedroom", "master_bedroom")
EXPECT_KEYS = {
    "status",
    "bedrooms",
    "baths_min",
    "attached_min",
    "has",
    "adjacent",
    "road_side",
    "conflict",
    "warning_contains",
    "project_name",
    "pool_layout",
}


def load_cases() -> list[dict]:
    return json.loads(CASES.read_text(encoding="utf-8"))["cases"]


def _shared(a: Room, b: Room) -> int:
    if a.x2 == b.x or b.x2 == a.x:
        return max(0, min(a.y2, b.y2) - max(a.y, b.y))
    if a.y2 == b.y or b.y2 == a.y:
        return max(0, min(a.x2, b.x2) - max(a.x, b.x))
    return 0


def check(
    expect: dict,
    status: str,
    plan: FloorPlan | None,
    brief,
    texts: list[str],
    pool_layout: str | None = None,
) -> list[str]:
    """Failed expectations, as short readable lines (empty = pass)."""
    fails: list[str] = []
    if expect.get("status", "ok") != status:
        return [f"status {status!r}, expected {expect.get('status', 'ok')!r}"]
    if brief is not None:
        if "conflict" in expect and not any(c.field == expect["conflict"] for c in brief.conflicts):
            fails.append(f"no conflict recorded for {expect['conflict']}")
        if "project_name" in expect and expect["project_name"].lower() not in (
            brief.project_name.lower()
        ):
            fails.append(f"project name {brief.project_name!r}")
    if "warning_contains" in expect:
        blob = " ".join(texts).lower()
        if expect["warning_contains"].lower() not in blob:
            fails.append(f"no warning mentioning {expect['warning_contains']!r}")
    if plan is None:
        return fails
    if "pool_layout" in expect and (pool_layout or "side") != expect["pool_layout"]:
        fails.append(f"pool {pool_layout or 'side'}, expected {expect['pool_layout']}")
    rooms = [r for r in plan.rooms if r.type != "shaft"]
    types = {r.type for r in rooms}
    beds = sum(r.type in BEDROOMS for r in rooms)
    baths = sum(r.type == "bath" for r in rooms)
    attached = sum(r.type == "bath" and re.fullmatch(r"bath_\d+", r.id) is not None for r in rooms)
    if "bedrooms" in expect and beds != expect["bedrooms"]:
        fails.append(f"{beds} bedrooms, expected {expect['bedrooms']}")
    if baths < expect.get("baths_min", 0):
        fails.append(f"{baths} bathrooms, expected at least {expect['baths_min']}")
    if attached < expect.get("attached_min", 0):
        fails.append(f"{attached} attached baths, expected at least {expect['attached_min']}")
    for t in expect.get("has", []):
        if t not in types:
            fails.append(f"no {t}")
    for a, b in expect.get("adjacent", []):
        if not any(_shared(x, y) >= 90 for x in rooms if x.type == a for y in rooms if y.type == b):
            fails.append(f"{a} not next to {b}")
    if "road_side" in expect and (plan.plot.road_side or "south") != expect["road_side"]:
        fails.append(f"road on {plan.plot.road_side}, expected {expect['road_side']}")
    return fails


def run_case(case: dict, llm) -> dict:
    t0 = time.perf_counter()
    try:
        form = BriefForm.model_validate(case["form"])
        parsed = parse_brief(form, llm if case.get("llm") else None)
        texts = [*parsed.warnings, *parsed.brief.assumptions, *parsed.brief.unknowns]
        texts.append(parsed.brief.notes)
        if not parsed.ready:
            status, plan, layout = "incomplete", None, None
        else:
            res = generate_plan(parsed.brief, llm=llm if case.get("llm") else None)
            status, plan = res.status, res.plan
            layout = res.program.pool_layout if res.program else None
            texts += res.warnings + [res.message]
        fails = check(case["expect"], status, plan, parsed.brief, texts, layout)
    except Exception as e:  # a crash is a failed case, not a stopped run
        status, fails = "error", [f"{type(e).__name__}: {e}"]
    return {
        "id": case["id"],
        "passed": not fails,
        "status": status,
        "fails": fails,
        "seconds": round(time.perf_counter() - t0, 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true", help="only cases that need no AI")
    ap.add_argument("--only", nargs="*", help="case ids to run")
    ap.add_argument(
        "--jobs", type=int, default=1, help="cases run in parallel (the AI key may rate-limit >1)"
    )
    ap.add_argument("--out", type=Path, help="write the full results as JSON")
    args = ap.parse_args()

    cases = load_cases()
    if args.only:
        cases = [c for c in cases if c["id"] in set(args.only)]
    if args.no_llm:
        cases = [c for c in cases if not c.get("llm")]
    llm = None if args.no_llm else get_llm()
    print(f"running {len(cases)} cases ({'no AI' if llm is None else 'with AI'})...")

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        results = list(pool.map(lambda c: run_case(c, llm), cases))
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        line = f"{mark}  {r['id']:<28} {r['status']:<11} {r['seconds']:>5}s"
        if r["fails"]:
            line += "  " + "; ".join(r["fails"])
        print(line)
    passed = sum(r["passed"] for r in results)
    rate = 100 * passed / max(len(results), 1)
    print(f"\npass rate: {passed}/{len(results)} = {rate:.0f}%  ({time.perf_counter() - t0:.0f}s)")
    if args.out:
        args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
