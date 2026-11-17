"""Phase 6: every export comes from the same plan JSON; DXF is real CAD vector data."""

import io
from collections import Counter

import ezdxf
import pymupdf
import pytest
from ezdxf import recover

from app.modules.ai.floorplan.render.dxf_renderer import LAYERS, render_dxf
from app.modules.ai.floorplan.render.exports import FORMATS, export_plan
from app.modules.ai.floorplan.schemas.plan import FloorPlan
from tests.floorplan.test_no_sample_content import DENY_RE


def _read_dxf(data: bytes):
    doc, auditor = recover.read(io.BytesIO(data))
    return doc, auditor


def test_dxf_is_valid_and_in_centimetres(sample_plan: FloorPlan) -> None:
    doc, auditor = _read_dxf(render_dxf(sample_plan))
    assert not auditor.has_errors, [e.message for e in auditor.errors]
    assert doc.header["$INSUNITS"] == ezdxf.units.CM
    for name in LAYERS:
        assert name in doc.layers, name


def test_dxf_entities_match_the_plan(sample_plan: FloorPlan) -> None:
    doc, _ = _read_dxf(render_dxf(sample_plan))
    msp = doc.modelspace()
    count = Counter((e.dxftype(), e.dxf.layer) for e in msp)
    swinging = [d for d in sample_plan.doors if d.swing != "none"]
    assert count[("ARC", "DOORS")] == len(swinging)
    assert count[("INSERT", "FURNITURE")] == len(sample_plan.fixtures)
    assert count[("LWPOLYLINE", "WINDOWS")] == len(sample_plan.windows)
    assert count[("HATCH", "WALLS")] >= 1 and count[("LWPOLYLINE", "WALLS")] >= 1
    assert count[("DIMENSION", "DIMENSIONS")] >= 4
    labels = {e.dxf.text for e in msp.query("TEXT")}
    for r in sample_plan.rooms:
        assert r.label.upper() in labels
    # furniture symbols are reusable named blocks
    for f in sample_plan.fixtures:
        assert f.symbol.upper() in doc.blocks


def test_dxf_geometry_is_in_real_units(sample_plan: FloorPlan) -> None:
    doc, _ = _read_dxf(render_dxf(sample_plan))
    plot = next(iter(doc.modelspace().query('LWPOLYLINE[layer=="PLOT"]')))
    xs = [p[0] for p in plot.get_points()]
    ys = [p[1] for p in plot.get_points()]
    assert max(xs) - min(xs) == pytest.approx(sample_plan.plot.width)
    assert max(ys) - min(ys) == pytest.approx(sample_plan.plot.depth)
    dims = list(doc.modelspace().query("DIMENSION"))
    overall = max(d.get_measurement() for d in dims)
    assert overall == pytest.approx(max(sample_plan.plot.width, sample_plan.plot.depth))


def test_dxf_has_no_sample_content(sample_plan: FloorPlan) -> None:
    text = render_dxf(sample_plan).decode("utf-8")
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
        export_plan(sample_plan, "dwg")  # type: ignore[arg-type]
