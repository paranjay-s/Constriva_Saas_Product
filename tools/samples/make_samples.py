"""PART 1 proof: generate the sample plans and write every export.

    uv --directory backend run python ../tools/samples/make_samples.py OUT_DIR

Plans: villas of about 1,500, 3,000, 5,000 and 8,000 sq ft (plot area), and the nandu
request (same plot and rooms as the user's plan, with "pool and garden at the front, the
pool touching the kitchen, living and bar, each with a door onto it" as rules). For each:
PDF (A3, vector, model attached), DXF, DWG (when the converter is installed), IFC and a
PNG at 200 dpi, plus OUT_DIR/samples.json with areas, checks and timings, and a contact
sheet (contact_sheet.png) beside the reference examples when they are present.
"""

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("TESTING", "1")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import pymupdf  # noqa: E402

from app.modules.ai.floorplan.model.areas import area_lines  # noqa: E402
from app.modules.ai.floorplan.model.build import build_building  # noqa: E402
from app.modules.ai.floorplan.model.checks import run_checks  # noqa: E402
from app.modules.ai.floorplan.pipeline.generate import generate_plan  # noqa: E402
from app.modules.ai.floorplan.render.dwg import DwgUnavailable  # noqa: E402
from app.modules.ai.floorplan.render.exports import export_plan  # noqa: E402
from app.modules.ai.floorplan.schemas.brief import Brief, PlotSpec, RoomRequest  # noqa: E402
from app.modules.ai.floorplan.schemas.rules import Place, Touches  # noqa: E402

FT = 30.48


def briefs() -> list[tuple[str, Brief]]:
    def villa(name, w, d, beds, extras, road="south", rules=(), owner="", unit="ft"):
        rooms = [RoomRequest(type="master_bedroom", attached_bath=True, dress_room=beds >= 3)]
        if beds > 1:
            rooms.append(RoomRequest(type="bedroom", count=beds - 1, attached_bath=True))
        rooms += [RoomRequest(type="living"), RoomRequest(type="kitchen")]
        rooms += [RoomRequest(type=t) if isinstance(t, str) else t for t in extras]
        return (
            name,
            Brief(
                plot=PlotSpec(width_cm=round(w * FT), depth_cm=round(d * FT), input_unit=unit),
                bedrooms=beds,
                bathrooms=beds,
                road_side=road,
                rooms=rooms,
                project_name=name.replace("-", " ").upper(),
                owner_name=owner,
                rules=list(rules),
            ),
        )

    nandu_rooms = [
        RoomRequest(type="bar", label="BAR"),
        RoomRequest(type="other", label="GAMING ROOM"),
        RoomRequest(type="puja", label="PUJA"),
        RoomRequest(type="stair"),
        RoomRequest(type="pool"),
        RoomRequest(type="garden"),
    ]
    nandu_rules = [
        Place(kind="place", room="pool", side="front", text="pool at the front"),
        Place(kind="place", room="garden", side="front", text="garden at the front"),
        Touches(
            kind="touches",
            room="pool",
            others=["kitchen", "living", "BAR"],
            door=True,
            text="the pool touches the kitchen, living and bar, each with a door onto it",
        ),
    ]
    out = [
        villa("villa-1500", 30, 50, 1, ["toilet"]),  # 2 bedrooms need smaller setbacks here
        villa("villa-3000", 50, 60, 3, ["majlis", "maid_room"], road="east"),
        villa("villa-5000", 50, 100, 4, ["majlis", "maid_room", "dining", "pool"]),
        villa(
            "villa-8000",
            80,
            100,
            5,
            ["majlis", "maid_room", "driver_room", "dining", "pool", "parking", "prayer"],
            road="north",
        ),
    ]
    name, brief = villa("nandu", 57.75, 86.6, 2, nandu_rooms, rules=nandu_rules, owner="Mr. D Naik")
    rooms = [
        r.model_copy(update={"dress_room": True}) if r.type == "master_bedroom" else r
        for r in brief.rooms
    ]
    # nandu: two master bedrooms, each with bath and dress (as in the user's plan)
    rooms = [r for r in rooms if r.type != "bedroom"] + [
        RoomRequest(type="master_bedroom", attached_bath=True, dress_room=True)
    ]
    out.append((name, brief.model_copy(update={"rooms": rooms, "bedrooms": 2})))
    return out


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    report = []
    for name, brief in briefs():
        t0 = time.time()
        res = generate_plan(brief, llm=None)
        took = round(time.time() - t0, 1)
        if not res.ok:
            report.append({"plan": name, "error": res.message})
            print(name, "failed:", res.message, flush=True)
            continue
        b = build_building(res.plan)
        files = {}
        for fmt in ("pdf", "dxf", "dwg", "ifc", "png", "svg"):
            try:
                data = export_plan(res.plan, fmt, building=b, dpi=200).data
            except DwgUnavailable as e:
                files[fmt] = f"not made: {e}"
                continue
            path = out / f"{name}.{fmt}"
            path.write_bytes(data)
            files[fmt] = path.name
        issues = run_checks(b)
        row = {
            "plan": name,
            "seconds": took,
            "areas": area_lines(b.areas, brief.plot.input_unit),
            "coverage": b.areas.coverage,
            "rooms": len(b.storeys[0].rooms),
            "critical": [i.message for i in issues if i.severity == "critical"],
            "warnings": [i.message for i in issues if i.severity == "warning"],
            "files": files,
            "notes": res.warnings,
        }
        report.append(row)
        print(json.dumps(row)[:400], flush=True)
    (out / "samples.json").write_text(json.dumps(report, indent=1))
    contact_sheet(out, [r["plan"] for r in report if "error" not in r])


def contact_sheet(out: Path, names: list[str]) -> None:
    """Our samples beside the reference sheets (docs/reference/floorplans), one page."""
    refs = sorted((ROOT / "docs" / "reference" / "floorplans").glob("*.pdf"))[:4]
    tiles = [(f"{n}.pdf", out / f"{n}.pdf") for n in names] + [(r.name[:30], r) for r in refs]
    cols = 3
    w, h = 420, 297
    rows = (len(tiles) + cols - 1) // cols
    doc = pymupdf.open()
    page = doc.new_page(width=cols * w * 2.835 / 2, height=rows * (h + 12) * 2.835 / 2)
    for i, (label, path) in enumerate(tiles):
        r, c = divmod(i, cols)
        x0 = c * w * 2.835 / 2
        y0 = r * (h + 12) * 2.835 / 2
        rect = pymupdf.Rect(x0 + 6, y0 + 18, x0 + w * 2.835 / 2 - 6, y0 + (h + 6) * 2.835 / 2)
        with pymupdf.open(path) as src:
            page.show_pdf_page(rect, src, 0)
        tag = "REFERENCE: " if path.parent.name == "floorplans" else "GENERATED: "
        page.insert_text((x0 + 8, y0 + 13), tag + label, fontsize=9)
    pdf = doc.tobytes()
    (out / "contact_sheet.pdf").write_bytes(pdf)
    with pymupdf.open(stream=pdf, filetype="pdf") as d:
        d[0].get_pixmap(dpi=60).save(str(out / "contact_sheet.png"))


if __name__ == "__main__":
    main()
