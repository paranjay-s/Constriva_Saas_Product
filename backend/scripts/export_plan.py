"""Developer tool: export a saved plan to CAD (DXF), PDF, PNG and SVG (the Phase 6 flow).

Examples (from backend/), after scripts/generate_from_brief.py wrote plan.json:
    uv run python scripts/export_plan.py plan.json                 # all four formats
    uv run python scripts/export_plan.py plan.json --format dxf    # CAD file only
    uv run python scripts/export_plan.py plan.json --format png --dpi 300

All files come from the same plan JSON. The DXF opens in AutoCAD, BricsCAD, LibreCAD,
DraftSight or any free online DXF viewer: layers WALLS DOORS WINDOWS FURNITURE TEXT
DIMENSIONS HATCH PLOT, units centimetres.
"""

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.modules.ai.floorplan.render.exports import FORMATS, export_plan  # noqa: E402
from app.modules.ai.floorplan.schemas.plan import FloorPlan  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("plan", type=Path, help="plan.json written by generate_from_brief.py")
    ap.add_argument("--format", choices=FORMATS, action="append", help="repeatable; default all")
    ap.add_argument("--dpi", type=int, default=150, help="PNG resolution")
    ap.add_argument("--out-dir", type=Path, help="default: next to the plan file")
    args = ap.parse_args()

    data = json.loads(args.plan.read_text(encoding="utf-8"))
    plan = FloorPlan.model_validate(data.get("plan", data))
    out_dir = args.out_dir or args.plan.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    for fmt in args.format or FORMATS:
        exp = export_plan(plan, fmt, dpi=args.dpi)
        target = out_dir / f"{args.plan.stem}.{fmt}"
        target.write_bytes(exp.data)
        print(f"wrote {target.resolve()} ({len(exp.data) // 1024} KB, {exp.media_type})")


if __name__ == "__main__":
    main()
