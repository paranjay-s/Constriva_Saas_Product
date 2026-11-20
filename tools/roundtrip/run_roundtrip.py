"""Round trip: generated plans -> PDF -> our 3D and BOQ readers, measured.

    uv --directory backend run python ../tools/roundtrip/run_roundtrip.py OUT_DIR [--ai N]

For each of 20 generated plans (fixed briefs, no AI in generation):
  1. export the PDF with its signed building model and read it back the way the 3D
     gateway and the BOQ do: the result must equal the model exactly
  2. remove the attachment and read the drawing with
       - PlanTo3D's vector detector (services/planto3d/detect.py, /usr/bin/python3)
       - the OpenCV reader (backend/app/modules/plan3d/raster_reader.py)
       - the AI reader (the plan parser, PLAN_PARSER_LLM_*) on the first N plans
     and score walls, doors, windows and rooms (backend/app/modules/plan3d/compare.py)
Writes OUT_DIR/results.json and OUT_DIR/results.md. Briefs are general (sizes, rooms,
road sides vary); nothing is tuned to one drawing.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("TESTING", "1")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import pymupdf  # noqa: E402

from app.modules.ai.floorplan.model.build import build_building  # noqa: E402
from app.modules.ai.floorplan.model.planjson import to_planjson  # noqa: E402
from app.modules.ai.floorplan.model.planto3d import to_planto3d  # noqa: E402
from app.modules.ai.floorplan.pipeline.generate import generate_plan  # noqa: E402
from app.modules.ai.floorplan.render.exports import export_plan  # noqa: E402
from app.modules.ai.floorplan.schemas.brief import Brief, PlotSpec, RoomRequest  # noqa: E402
from app.modules.ai.floorplan.settings import get_settings  # noqa: E402
from app.modules.plan3d.compare import compare_floor  # noqa: E402
from app.modules.plan3d.raster_reader import read_pdf_page  # noqa: E402

FT = 30.48
DETECT = ROOT / "services" / "planto3d" / "detect.py"


def _briefs() -> list[tuple[str, Brief]]:
    """20 briefs from 1,500 to 12,000 sq ft, 1-6 bedrooms, every road side, ft and m."""
    specs = [
        # name, width ft, depth ft, beds, extras, road
        ("rt01", 30, 50, 2, [], "south"),
        ("rt02", 35, 60, 2, ["study"], "east"),
        ("rt03", 40, 60, 3, [], "north"),
        ("rt04", 40, 70, 3, ["parking"], "west"),
        ("rt05", 45, 70, 3, ["majlis"], "south"),
        ("rt06", 50, 80, 3, ["pool"], "south"),
        ("rt07", 50, 90, 4, ["maid_room"], "east"),
        ("rt08", 55, 90, 4, ["majlis", "pool"], "north"),
        ("rt09", 60, 90, 4, ["dining", "store"], "west"),
        ("rt10", 60, 100, 4, ["majlis", "maid_room", "pool"], "south"),
        ("rt11", 65, 100, 5, ["dining"], "east"),
        ("rt12", 70, 100, 5, ["majlis", "pool", "parking"], "south"),
        ("rt13", 70, 110, 5, ["majlis", "maid_room", "driver_room"], "north"),
        ("rt14", 75, 110, 5, ["gym", "pool"], "west"),
        ("rt15", 80, 110, 5, ["majlis", "dining", "prayer"], "south"),
        ("rt16", 80, 120, 6, ["pool", "majlis"], "east"),
        ("rt17", 90, 120, 6, ["majlis", "maid_room", "pool", "parking"], "south"),
        ("rt18", 40, 50, 1, ["study"], "north"),
        ("rt19", 58, 87, 2, ["bar", "puja", "pool", "stair"], "south"),
        ("rt20", 100, 120, 6, ["majlis", "gym", "pool", "maid_room", "dining"], "west"),
    ]
    out = []
    for i, (name, w, d, beds, extras, road) in enumerate(specs):
        unit = "m" if i % 4 == 3 else "ft"
        rooms = [RoomRequest(type="master_bedroom", attached_bath=True, dress_room=beds >= 3)]
        if beds > 1:
            rooms.append(RoomRequest(type="bedroom", count=beds - 1, attached_bath=True))
        rooms += [RoomRequest(type="living"), RoomRequest(type="kitchen")]
        rooms += [RoomRequest(type=t) for t in extras]
        brief = Brief(
            plot=PlotSpec(width_cm=round(w * FT), depth_cm=round(d * FT), input_unit=unit),
            bedrooms=beds,
            bathrooms=beds,
            road_side=road,
            rooms=rooms,
            project_name=f"Round trip {name}",
        )
        out.append((name, brief))
    return out


def _strip(pdf: bytes) -> bytes:
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        for n in doc.embfile_names():
            doc.embfile_del(n)
        return doc.tobytes()


def _detector(pdf: Path) -> dict | None:
    out = pdf.with_suffix(".det.json")
    r = subprocess.run(
        ["/usr/bin/python3", str(DETECT), str(pdf), str(out)],
        cwd=DETECT.parent,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    if r.returncode != 0 or not out.exists():
        return None
    floors = json.loads(out.read_text())["floors"]
    return max(floors, key=lambda f: len(f["walls"])) if floors else None


def _ai(pdf_bytes: bytes) -> dict | None:
    from app.modules.parsing.llm_parser import parse_plan_pdf
    from app.modules.plan3d.convert import planjson_to_planto3d

    plan = parse_plan_pdf(pdf_bytes, min_rooms=1)
    conv = planjson_to_planto3d(plan, reader="ai")
    return conv.plan["floors"][0] if conv.plan else None


def main() -> None:
    out_dir = Path(sys.argv[1])
    ai_n = int(sys.argv[sys.argv.index("--ai") + 1]) if "--ai" in sys.argv else 0
    out_dir.mkdir(parents=True, exist_ok=True)
    s = get_settings()
    if not s.model_signing_key.get_secret_value():
        from pydantic import SecretStr

        s.model_signing_key = SecretStr("round-trip-evaluation-key")
    results = []
    for i, (name, brief) in enumerate(_briefs()):
        t0 = time.time()
        res = generate_plan(brief, llm=None)
        if not res.ok:
            results.append({"plan": name, "error": res.message[:200]})
            print(name, "generation failed:", res.message[:120], flush=True)
            continue
        b = build_building(res.plan)
        truth = to_planto3d(b)["floors"][0]
        pdf = export_plan(res.plan, "pdf", building=b).data
        (out_dir / f"{name}.pdf").write_bytes(pdf)
        # 1. exact readers
        from app.modules.ai.floorplan.service import signed_plan_for_pdf
        from app.modules.sheets.boq_service import default_pdf_parser

        stored = signed_plan_for_pdf(pdf)
        exact_3d = stored is not None and stored["planto3d"]["floors"] == to_planto3d(b)["floors"]
        exact_boq = default_pdf_parser(pdf) == to_planjson(b)
        row = {
            "plan": name,
            "sq_ft": round(b.site.area_m2 * 10.7639),
            "coverage": b.areas.coverage,
            "seconds_generate": round(time.time() - t0, 1),
            "exact_3d": exact_3d,
            "exact_boq": exact_boq,
        }
        # 2. the drawing alone
        plain = _strip(pdf)
        plain_path = out_dir / f"{name}.plain.pdf"
        plain_path.write_bytes(plain)
        det = _detector(plain_path)
        row["detector"] = compare_floor(truth, det) if det else None
        row["opencv"] = compare_floor(truth, read_pdf_page(plain).floor)
        if i < ai_n:
            try:
                ai = _ai(plain)
                row["ai"] = compare_floor(truth, ai) if ai else None
            except Exception as e:  # a failed live call is reported, not fatal
                row["ai"] = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
        results.append(row)
        print(json.dumps(row), flush=True)
    (out_dir / "results.json").write_text(json.dumps(results, indent=1))
    (out_dir / "results.md").write_text(summarise(results))
    print(summarise(results))


def summarise(results: list[dict]) -> str:
    ok = [r for r in results if "error" not in r]
    lines = [
        f"Plans generated: {len(ok)} of {len(results)}.",
        f"Exact with the embedded model: 3D {sum(r['exact_3d'] for r in ok)}/{len(ok)}, "
        f"BOQ {sum(r['exact_boq'] for r in ok)}/{len(ok)}.",
        "",
        "| Reader | Plans | Walls R / P | Doors R / P | Windows R / P | Rooms R / P | Room types |",
        "|---|---|---|---|---|---|---|",
    ]
    for reader in ("detector", "opencv", "ai"):
        rows = [r[reader] for r in ok if isinstance(r.get(reader), dict) and "walls" in r[reader]]
        if not rows:
            continue

        def avg(key: str, part: str, rows=rows) -> str:
            return f"{100 * sum(r[key][part] for r in rows) / len(rows):.1f}%"

        lines.append(
            f"| {reader} | {len(rows)} | {avg('walls', 'recall')} / {avg('walls', 'precision')} "
            f"| {avg('doors', 'recall')} / {avg('doors', 'precision')} "
            f"| {avg('windows', 'recall')} / {avg('windows', 'precision')} "
            f"| {avg('rooms', 'recall')} / {avg('rooms', 'precision')} "
            f"| {100 * sum(r['room_types'] for r in rows) / len(rows):.1f}% |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
