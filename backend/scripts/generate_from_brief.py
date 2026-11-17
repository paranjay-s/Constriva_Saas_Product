"""Developer tool: form fields + free-text prompt -> Brief -> plan (the full Phase 4 flow).

Examples (from backend/):
    uv run python scripts/generate_from_brief.py --width 40 --depth 50 --unit ft \
        --prompt "3 BHK, master bedroom with attached bath, kitchen next to dining, east facing"
    uv run python scripts/generate_from_brief.py --no-llm \
        --prompt "2 bedroom house on a 30x45 ft plot"

Uses the configured LLM (GEMINI_API_KEY) unless --no-llm is given. Prints the parsed
brief (what the confirmation card will show), then generates, validates and renders.
Also writes <out>.json (plan + room program) for chat edits with scripts/edit_plan.py.
"""

import argparse
import json
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.modules.ai.floorplan.pipeline.brief_parser import parse_brief  # noqa: E402
from app.modules.ai.floorplan.pipeline.generate import generate_plan  # noqa: E402
from app.modules.ai.floorplan.render.svg_renderer import render_svg  # noqa: E402
from app.modules.ai.floorplan.schemas.brief import BriefForm  # noqa: E402
from app.modules.ai.llm.client import get_llm  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=float)
    ap.add_argument("--depth", type=float)
    ap.add_argument("--area", type=float, help="plot area in unit^2 (only if no width/depth)")
    ap.add_argument("--unit", choices=["ft", "m"], default="ft")
    ap.add_argument("--bedrooms", type=int)
    ap.add_argument("--bathrooms", type=int)
    ap.add_argument("--extras", default="", help="comma list, e.g. dining,parking,courtyard")
    ap.add_argument("--road", choices=["north", "south", "east", "west"])
    ap.add_argument("--project", default="")
    ap.add_argument("--owner", default="")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--out", type=Path, default=Path("plan.svg"))
    ap.add_argument("--png", action="store_true")
    args = ap.parse_args()

    form = BriefForm(
        plot_width=args.width,
        plot_depth=args.depth,
        plot_area=args.area,
        unit=args.unit,
        bedrooms=args.bedrooms,
        bathrooms=args.bathrooms,
        extras=[e.strip() for e in args.extras.split(",") if e.strip()],
        road_side=args.road,
        project_name=args.project,
        owner_name=args.owner,
        prompt=args.prompt,
    )
    llm = None if args.no_llm else get_llm()

    t0 = time.perf_counter()
    parsed = parse_brief(form, llm)
    print(f"--- brief ({time.perf_counter() - t0:.1f}s) ---")
    print(json.dumps(parsed.brief.model_dump(exclude_defaults=True), indent=2))
    for w in parsed.warnings:
        print("WARNING:", w)
    if not parsed.ready:
        print("MISSING:", ", ".join(parsed.missing))
        sys.exit(2)

    t1 = time.perf_counter()
    res = generate_plan(parsed.brief, llm=llm, progress=lambda s, d: print(f"  [{s}] {d}"))
    print(f"--- result: {res.status} in {time.perf_counter() - t1:.1f}s ({res.method}) ---")
    for w in res.warnings:
        print("note:", w)
    if not res.ok:
        print(res.message)
        if res.feasibility and res.feasibility.options:
            print("options:", *res.feasibility.options, sep="\n  - ")
        sys.exit(1)
    print(
        "rooms:",
        ", ".join(f"{r.label} {r.w}x{r.h}" for r in res.plan.rooms if not r.part_of),
    )
    joined = [r for r in res.plan.rooms if r.part_of]
    if joined:
        print(
            "leftover space shown as part of:", ", ".join(f"{r.label} {r.w}x{r.h}" for r in joined)
        )
    svg = render_svg(res.plan)
    args.out.write_text(svg, encoding="utf-8")
    print(f"wrote {args.out.resolve()}")
    saved = args.out.with_suffix(".json")  # plan + room program, for scripts/edit_plan.py
    saved.write_text(
        json.dumps(
            {"plan": res.plan.to_json_dict(), "program": res.program.model_dump()}, indent=2
        ),
        encoding="utf-8",
    )
    print(f"wrote {saved.resolve()}")
    if args.png:
        import pymupdf

        png = args.out.with_suffix(".png")
        pymupdf.open(stream=svg.encode(), filetype="svg")[0].get_pixmap(dpi=100).save(str(png))
        print(f"wrote {png.resolve()}")


if __name__ == "__main__":
    main()
