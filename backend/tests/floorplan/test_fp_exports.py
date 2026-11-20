"""Phase 6: every export comes from the same plan JSON; DXF is real CAD vector data."""

import io
from collections import Counter

import ezdxf
import pymupdf
import pytest
from ezdxf import recover

from app.modules.ai.floorplan.model.build import build_building
from app.modules.ai.floorplan.render.cad_dxf import LAYERS, building_dxf
from app.modules.ai.floorplan.render.exports import (
    FORMATS,
    PlanReference,
    export_plan,
    plan_reference,
    read_plan_reference,
)
from app.modules.ai.floorplan.schemas.plan import FloorPlan
from tests.floorplan.test_no_sample_content import DENY_RE


def _read_dxf(data: bytes):
    doc, auditor = recover.read(io.BytesIO(data))
    return doc, auditor


def _dxf(plan: FloorPlan) -> bytes:
    return building_dxf(build_building(plan))


def test_dxf_is_valid_and_in_millimetres(sample_plan: FloorPlan) -> None:
    doc, auditor = _read_dxf(_dxf(sample_plan))
    assert not auditor.has_errors, [e.message for e in auditor.errors]
    assert doc.header["$INSUNITS"] == ezdxf.units.MM
    for name in LAYERS:
        assert name in doc.layers, name


def test_dxf_entities_match_the_plan(sample_plan: FloorPlan) -> None:
    b = build_building(sample_plan)
    doc, _ = _read_dxf(building_dxf(b))
    msp = doc.modelspace()
    count = Counter((e.dxftype(), e.dxf.layer) for e in msp)
    st = b.storeys[0]
    doors = [o for o in st.openings if o.kind == "door"]
    assert count[("INSERT", "A-DOOR")] == len(doors)
    assert count[("INSERT", "A-GLAZ")] == len(st.openings) - len(doors)
    fixtures = count[("INSERT", "A-FLOR-FIXT")] + count[("INSERT", "A-FURN")]
    assert fixtures == len(st.fixtures)
    assert count[("HATCH", "A-WALL-PATT")] >= 1 and count[("LWPOLYLINE", "A-WALL-EXTR")] >= 1
    assert count[("DIMENSION", "A-ANNO-DIMS")] >= 4
    labels = {e.dxf.text for e in msp.query("TEXT")}
    for r in sample_plan.rooms:
        if r.type != "shaft" and not r.is_open:
            assert r.label.upper() in labels


def test_dxf_geometry_is_in_real_units(sample_plan: FloorPlan) -> None:
    doc, _ = _read_dxf(_dxf(sample_plan))
    plot = next(iter(doc.modelspace().query('LWPOLYLINE[layer=="C-PROP"]')))
    xs = [p[0] for p in plot.get_points()]
    ys = [p[1] for p in plot.get_points()]
    assert max(xs) - min(xs) == pytest.approx(sample_plan.plot.width * 10, abs=25)
    assert max(ys) - min(ys) == pytest.approx(sample_plan.plot.depth * 10, abs=25)
    measures = {round(d.get_measurement()) for d in doc.modelspace().query("DIMENSION")}
    # the plot chain measures the plot (the building chain may be wider by the outer half of
    # exterior walls standing on a plot edge, in layouts without setbacks)
    assert any(abs(m - sample_plan.plot.width * 10) <= 25 for m in measures)
    assert any(abs(m - sample_plan.plot.depth * 10) <= 25 for m in measures)


def test_dxf_has_no_sample_content(sample_plan: FloorPlan) -> None:
    text = _dxf(sample_plan).decode("utf-8")
    assert not DENY_RE.search(text), DENY_RE.findall(text)


def test_pdf_is_vector(sample_plan: FloorPlan) -> None:
    exp = export_plan(sample_plan, "pdf")
    assert exp.data.startswith(b"%PDF") and exp.media_type == "application/pdf"
    page = pymupdf.open(stream=exp.data, filetype="pdf")[0]
    assert len(page.get_drawings()) > 50  # walls, doors, symbols are vector paths
    assert page.get_images() == []  # no embedded bitmap
    assert "LIVING" in page.get_text() or any(
        r.label.upper() in page.get_text() for r in sample_plan.rooms
    )


PLAN_ID = "3f0c2b8e-5d41-4a77-9c1e-0a6b7d2e4f10"


def test_pdf_names_the_plan_it_was_exported_from(sample_plan: FloorPlan) -> None:
    plan = sample_plan.model_copy(update={"id": PLAN_ID})
    exp = export_plan(plan, "pdf", version=4)
    assert read_plan_reference(exp.data) == PlanReference(PLAN_ID, 4)
    assert read_plan_reference(export_plan(plan, "pdf").data) == PlanReference(PLAN_ID, None)
    # the drawing itself is unchanged by the reference
    page = pymupdf.open(stream=exp.data, filetype="pdf")[0]
    assert len(page.get_drawings()) > 50 and page.get_images() == []


def test_a_plan_whose_id_is_not_a_uuid_gets_no_reference(sample_plan: FloorPlan) -> None:
    plan = sample_plan.model_copy(update={"id": "plan 1; drop"})
    exp = export_plan(plan, "pdf", version=2)
    assert exp.data.startswith(b"%PDF")
    assert read_plan_reference(exp.data) is None
    assert plan_reference("not-a-uuid", 1) == ""


def _pdf_with_keywords(keywords: str) -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    doc.set_metadata({"keywords": keywords})
    return doc.tobytes()


@pytest.mark.parametrize(
    ("keywords", "expected"),
    [
        (f"constriva-plan:{PLAN_ID};v=12", PlanReference(PLAN_ID, 12)),
        (f"villa, constriva-plan:{PLAN_ID.upper()}, 2026", PlanReference(PLAN_ID, None)),
        (f"constriva-plan:{PLAN_ID};v=0007", PlanReference(PLAN_ID, 7)),
        ("", None),
        ("constriva-plan:1234", None),
        (f"constriva-plan:{PLAN_ID}0", None),  # a longer id is not this id
        (f"xconstriva-plan:{PLAN_ID}", None),
        (f"constriva-plan:{PLAN_ID};v=" + "9" * 7, PlanReference(PLAN_ID, None)),
        ("k" * 3000 + f" constriva-plan:{PLAN_ID}", None),
    ],
)
def test_reading_a_plan_reference(keywords: str, expected: PlanReference | None) -> None:
    assert read_plan_reference(_pdf_with_keywords(keywords)) == expected


def test_reading_a_reference_from_bytes_that_are_not_a_pdf() -> None:
    assert read_plan_reference(b"") is None
    assert read_plan_reference(b"not a pdf at all") is None
    assert read_plan_reference(b"%PDF-1.7\n%broken") is None


def test_png_and_svg(sample_plan: FloorPlan) -> None:
    png = export_plan(sample_plan, "png", dpi=72)
    assert png.data.startswith(b"\x89PNG")
    svg = export_plan(sample_plan, "svg")
    assert svg.data.lstrip().startswith(b"<svg") or b"<svg" in svg.data[:200]


def test_all_formats_share_one_file_name(sample_plan: FloorPlan) -> None:
    named = sample_plan.model_copy(
        update={"meta": sample_plan.meta.model_copy(update={"project": "My House / Plot 7"})}
    )
    names = {export_plan(named, fmt).filename.rsplit(".", 1)[0] for fmt in FORMATS}
    assert names == {"my-house-plot-7"}


def test_unknown_format_is_rejected(sample_plan: FloorPlan) -> None:
    with pytest.raises(ValueError):
        export_plan(sample_plan, "xyz")  # type: ignore[arg-type]
