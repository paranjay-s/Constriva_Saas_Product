"""Developer tool: generate a plan from a hand-written room program (no LLM) and render it.

Input file format: {"plot": {...}, "meta": {...}, "program": {RoomProgram}}

Usage (from backend/):
    uv run python scripts/generate_from_program.py
        tests/floorplan/fixtures/programs/house_3bed_12x15.json   (one line)
    uv run python scripts/generate_from_program.py <file> --out plan.svg --png --solver-only
"""

import argparse
import json
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.modules.ai.floorplan.pipeline.layout import generate_layout  # noqa: E402
from app.modules.ai.floorplan.render.svg_renderer import render_svg  # noqa: E402
from app.modules.ai.floorplan.schemas.plan import Meta, Plot  # noqa: E402
from app.modules.ai.floorplan.schemas.program import RoomProgram  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--out", type=Path, default=Path("plan.svg"))
    ap.add_argument("--png", action="store_true")
    ap.add_argument("--json", action="store_true", help="also write the plan JSON")
    ap.add_argument("--solver-only", action="store_true", help="skip templates")
    ap.add_argument("--time", type=float, default=8.0, help="solver time limit per attempt (s)")
    args = ap.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    plot = Plot.model_validate(data["plot"])
    meta = Meta.model_validate(data.get("meta", {}))
    program = RoomProgram.model_validate(data["program"])

    t0 = time.perf_counter()
    res = generate_layout(
        program, plot, meta, use_templates=not args.solver_only, time_limit_s=args.time
    )
    print(f"took {time.perf_counter() - t0:.1f}s")
    for line in res.attempts:
        print("  attempt:", line)
    if not res.ok:
        print("NO VALID PLAN. Errors:")
        for line in res.report.feedback() if res.report else []:
            print("  ", line)
        sys.exit(1)
    print(f"valid plan via {res.method}; warnings: {[w.code for w in res.report.warnings]}")
    svg = render_svg(res.plan)
    args.out.write_text(svg, encoding="utf-8")
    print(f"wrote {args.out.resolve()}")
    if args.json:
        jp = args.out.with_suffix(".json")
        jp.write_text(json.dumps(res.plan.to_json_dict(), indent=2), encoding="utf-8")
        print(f"wrote {jp.resolve()}")
    if args.png:
        import pymupdf

        doc = pymupdf.open(stream=svg.encode("utf-8"), filetype="svg")
        png = args.out.with_suffix(".png")
        doc[0].get_pixmap(dpi=100).save(str(png))
        print(f"wrote {png.resolve()}")


if __name__ == "__main__":
    main()
