"""Developer tool: chat-edit a saved plan (the Phase 5 flow).

Examples (from backend/), after scripts/generate_from_brief.py wrote plan.json:
    uv run python scripts/edit_plan.py plan.json --say "make bedroom 2 one foot wider"
    uv run python scripts/edit_plan.py plan.json --say "add a store room next to the kitchen"
    uv run python scripts/edit_plan.py plan.json --say "add a swimming pool in the garden"
    uv run python scripts/edit_plan.py plan.json --say "make bedroom 2 bigger" --locked
    uv run python scripts/edit_plan.py plan.json \
        --ops '[{"op": "rename_room", "id": "bed_2", "label": "KIDS ROOM"}]'

--say uses the configured LLM to turn the message into edit operations; --ops applies
operations directly (no LLM), the way the drag-and-drop UI will. On success the plan
file is updated in place (or written to --out) with a new .svg/.png next to it.
"""

import argparse
import json
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from pydantic import TypeAdapter  # noqa: E402

from app.modules.ai.floorplan.pipeline.edit_engine import apply_edit, edit_plan  # noqa: E402
from app.modules.ai.floorplan.render.svg_renderer import render_svg  # noqa: E402
from app.modules.ai.floorplan.schemas.edit_ops import EditOp  # noqa: E402
from app.modules.ai.floorplan.schemas.plan import FloorPlan  # noqa: E402
from app.modules.ai.floorplan.schemas.program import RoomProgram  # noqa: E402
from app.modules.ai.llm.client import get_llm  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("plan", type=Path, help="plan.json written by generate_from_brief.py")
    ap.add_argument("--say", default="", help="the edit request in plain words")
    ap.add_argument("--ops", default="", help="edit operations as JSON (no LLM)")
    ap.add_argument(
        "--locked",
        action="store_true",
        help="only the named room and its neighbours may move (default: others move if needed)",
    )
    ap.add_argument("--out", type=Path, help="write here instead of updating the plan file")
    ap.add_argument("--no-png", action="store_true")
    args = ap.parse_args()
    if not args.say and not args.ops:
        ap.error("give --say or --ops")

    data = json.loads(args.plan.read_text(encoding="utf-8"))
    plan = FloorPlan.model_validate(data["plan"])
    program = RoomProgram.model_validate(data["program"]) if data.get("program") else None

    t0 = time.perf_counter()
    if args.ops:
        ops = TypeAdapter(list[EditOp]).validate_json(args.ops)
        res = apply_edit(plan, program, ops, allow_reflow=not args.locked)
    else:
        res = edit_plan(plan, program, args.say, get_llm(), allow_reflow=not args.locked)
    print(f"--- {res.status} in {time.perf_counter() - t0:.1f}s ---")
    if res.ops:
        print("operations:", json.dumps([o.model_dump(exclude_none=True) for o in res.ops]))
    for w in res.warnings:
        print("WARNING:", w)
    if res.message:
        print(res.message)
    for a in res.alternatives:
        print("  option:", a)
    for line in res.summary:
        print("  *", line)
    if not res.ok:
        sys.exit(1)

    out = args.out or args.plan
    out.write_text(
        json.dumps(
            {"plan": res.plan.to_json_dict(), "program": res.program.model_dump()}, indent=2
        ),
        encoding="utf-8",
    )
    svg = render_svg(res.plan)
    svg_path = out.with_suffix(".svg")
    svg_path.write_text(svg, encoding="utf-8")
    print(f"wrote {out.resolve()} and {svg_path.name}")
    if not args.no_png:
        import pymupdf

        png = out.with_suffix(".png")
        pymupdf.open(stream=svg.encode(), filetype="svg")[0].get_pixmap(dpi=100).save(str(png))
        print(f"wrote {png.name}")


if __name__ == "__main__":
    main()
