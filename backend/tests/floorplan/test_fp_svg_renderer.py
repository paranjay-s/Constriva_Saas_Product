import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pymupdf

from app.modules.ai.floorplan.render.svg_renderer import render_svg
from app.modules.ai.floorplan.render.symbols import SYMBOLS
from app.modules.ai.floorplan.schemas.plan import FloorPlan

SNAPSHOT = Path(__file__).parent / "snapshots" / "sample_plan.svg"
NS = {"s": "http://www.w3.org/2000/svg"}


def _texts(svg: str) -> list[str]:
    root = ET.fromstring(svg)
    return ["".join(t.itertext()) for t in root.iter("{http://www.w3.org/2000/svg}text")]


def test_svg_is_valid_xml_with_layers(sample_plan: FloorPlan) -> None:
    root = ET.fromstring(render_svg(sample_plan))
    ids = {el.get("id") for el in root.iter() if el.get("id")}
    for layer in (
        "walls",
        "doors",
        "windows",
        "fixtures",
        "labels",
        "dimensions",
        "title-block",
        "hatch",
    ):
        assert layer in ids


def test_every_room_labelled_with_size(sample_plan: FloorPlan) -> None:
    texts = _texts(render_svg(sample_plan))
    for r in sample_plan.rooms:
        assert r.label.upper() in texts
        assert f"{r.w}X{r.h}" in texts


def test_feet_labels(sample_plan: FloorPlan) -> None:
    sample_plan.meta.unit_display = "ft"
    texts = _texts(render_svg(sample_plan))
    assert "14'9\"X14'9\"" in texts  # 450 x 450 cm master bedroom
    assert "166 M2" not in " ".join(texts)
    assert any("SQ.FT" in t for t in texts)


def test_walls_have_cut_openings(sample_plan: FloorPlan) -> None:
    svg = render_svg(sample_plan)
    walls = re.search(r'<g id="walls"><path [^>]*d="([^"]+)"', svg)
    assert walls and walls.group(1).count("M") > 1  # openings split the wall mass
    assert svg.count("stroke-dasharray") == sum(1 for d in sample_plan.doors if d.swing != "none")


def test_title_block_uses_only_user_input(sample_plan: FloorPlan) -> None:
    texts = _texts(render_svg(sample_plan))
    assert "SAMPLE HOUSE A" in texts
    assert "166.0 M2" in texts
    sample_plan.meta.project = ""
    sample_plan.meta.owner = "Owner & <Co>"
    svg = render_svg(sample_plan)
    texts = _texts(svg)
    assert "SAMPLE HOUSE A" not in texts
    assert "Owner & <Co>" in texts  # escaped in the XML, intact after parsing
    assert "&amp;" in svg


def test_blank_meta_renders_blank_title_values() -> None:
    plan = FloorPlan.model_validate(
        {
            "id": "p",
            "plot": {"width": 600, "depth": 500},
            "rooms": [
                {"id": "r", "type": "living", "label": "LIVING", "x": 0, "y": 0, "w": 600, "h": 500}
            ],
        }
    )
    texts = _texts(render_svg(plan))
    title_values = [
        t
        for t in texts
        if t not in {"PROJECT", "OWNER", "TOTAL AREA", "GROUND FLOOR", "30.0 M2", "N"}
    ]
    assert set(title_values) <= {"LIVING", "600X500", "600", "500"}


def test_all_symbols_render() -> None:
    rooms = [{"id": "r", "type": "living", "label": "HALL", "x": 0, "y": 0, "w": 2000, "h": 400}]
    fixtures = [
        {
            "id": f"f{i}",
            "room": "r",
            "symbol": name,
            "x": 100 + i * 115,
            "y": 150,
            "rotation": (i % 4) * 90,
        }
        for i, name in enumerate(sorted(SYMBOLS))
    ]
    plan = FloorPlan.model_validate(
        {"id": "p", "plot": {"width": 2000, "depth": 400}, "rooms": rooms, "fixtures": fixtures}
    )
    svg = render_svg(plan)
    for name in SYMBOLS:
        assert f'id="sym-{name}"' in svg
        assert f'href="#sym-{name}"' in svg


def test_pdf_conversion_uses_sans_font(sample_plan: FloorPlan) -> None:
    doc = pymupdf.open(stream=render_svg(sample_plan).encode(), filetype="svg")
    pdf = pymupdf.open("pdf", doc.convert_to_pdf())
    fonts = {f[3] for f in pdf[0].get_fonts()}
    assert any("Helvetica" in f for f in fonts), fonts
    assert "MASTER BED ROOM" in pdf[0].get_text()


def test_render_is_deterministic(sample_plan: FloorPlan) -> None:
    assert render_svg(sample_plan) == render_svg(sample_plan)


def test_different_plans_render_differently(sample_plan: FloorPlan, sample_dict: dict) -> None:
    sample_dict["rooms"][0]["label"] = "GUEST ROOM"
    other = FloorPlan.model_validate(sample_dict)
    assert render_svg(sample_plan) != render_svg(other)


def test_snapshot(sample_plan: FloorPlan) -> None:
    """Fails when the look changes. Re-baseline on purpose with UPDATE_SNAPSHOTS=1."""
    svg = render_svg(sample_plan)
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(svg, encoding="utf-8", newline="\n")
    assert SNAPSHOT.exists(), "snapshot missing: run with UPDATE_SNAPSHOTS=1"
    assert svg == SNAPSHOT.read_text(encoding="utf-8")
