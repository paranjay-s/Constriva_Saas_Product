"""Developer tool: render a FloorPlan JSON file to SVG (and optionally PNG) for a visual check.

Usage (from backend/):
    uv run python scripts/render_sample_plan.py                      # -> plan.svg
    uv run python scripts/render_sample_plan.py --unit ft --png      # feet labels + plan.png
    uv run python scripts/render_sample_plan.py --plan path/to/plan.json --out out.svg

The default input is the hand-written test fixture. It is never loaded by the app at
runtime and never sent to an LLM.
"""

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.modules.ai.floorplan.render.svg_renderer import render_svg  # noqa: E402
from app.modules.ai.floorplan.schemas.plan import FloorPlan  # noqa: E402

DEFAULT_PLAN = BACKEND / "tests" / "floorplan" / "fixtures" / "sample_plan.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    ap.add_argument("--out", type=Path, default=Path("plan.svg"))
    ap.add_argument("--unit", choices=["cm", "m", "ft"], default=None)
    ap.add_argument("--png", action="store_true", help="also write a PNG preview next to the SVG")
    args = ap.parse_args()

    plan = FloorPlan.model_validate(json.loads(args.plan.read_text(encoding="utf-8")))
    if args.unit:
        plan.meta.unit_display = args.unit
    svg = render_svg(plan)
    args.out.write_text(svg, encoding="utf-8")
    print(f"wrote {args.out.resolve()}")

    if args.png:
        import pymupdf

        doc = pymupdf.open(stream=svg.encode("utf-8"), filetype="svg")
        png_path = args.out.with_suffix(".png")
        doc[0].get_pixmap(dpi=110).save(str(png_path))
        print(f"wrote {png_path.resolve()}")


if __name__ == "__main__":
    main()
