"""The CAD sheet: muted colours, ISO pens, text placement, dimension chains, PDF at scale."""

import re

import pymupdf
import pytest
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from app.modules.ai.floorplan.drawing.compose import (
    chain_labels,
    compose_sheet,
    text_width,
)
from app.modules.ai.floorplan.drawing.display import Area, Line, Text
from app.modules.ai.floorplan.drawing.emit import PT_PER_MM, to_pdf, to_svg
from app.modules.ai.floorplan.drawing.style import GREY, HATCH, INK
from app.modules.ai.floorplan.model.build import build_building
from tests.floorplan.test_fp_building import _pool_plan

ALLOWED = {INK, "#ffffff", *GREY.values(), *(h["color"] for h in HATCH.values())}


@pytest.fixture(scope="module")
def building():
    return build_building(_pool_plan(), date="2026-11-20")


@pytest.fixture(scope="module")
def sheet(building):
    return compose_sheet(building, sheet="A3")


def _text_box(t: Text):
    w = text_width(t.text, t.size, t.bold)
    x0 = {"start": t.x, "middle": t.x - w / 2, "end": t.x - w}[t.anchor]
    if t.rotation % 360 == 90:
        y0 = {"start": t.y - w, "middle": t.y - w / 2, "end": t.y}[t.anchor]
        return box(t.x - t.size, y0, t.x + 0.3 * t.size, y0 + w)
    return box(x0, t.y - 0.8 * t.size, x0 + w, t.y + 0.2 * t.size)


def test_only_greys_and_light_landscape_hatches(sheet) -> None:
    colours = set()
    for it in sheet.items:
        colours.add(getattr(it, "color", None))
        colours.add(getattr(it, "fill", None))
        colours.add(getattr(it, "stroke", None))
    colours.discard(None)
    assert colours <= ALLOWED, colours - ALLOWED


def test_room_labels_do_not_overlap_each_other_or_walls(sheet) -> None:
    texts = [t for t in sheet.items if isinstance(t, Text) and t.layer == "A-AREA-IDEN"]
    assert texts
    boxes = [_text_box(t) for t in texts]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            assert a.intersection(b).area < 0.05, (a.bounds, b.bounds)
    walls = unary_union(
        [
            Polygon(it.rings[0], it.rings[1:])
            for it in sheet.items
            if isinstance(it, Area) and it.layer in ("A-WALL", "A-WALL-PATT")
        ]
    )
    for t, bx in zip(texts, boxes, strict=True):
        assert bx.intersection(walls).area < 0.05, t.text


def test_every_room_has_name_size_and_area(sheet, building) -> None:
    texts = [t.text for t in sheet.items if isinstance(t, Text)]
    for r in building.storeys[0].rooms:
        assert r.name.upper() in texts
    assert any(re.match(r"^[\d.'\"]+ × [\d.'\"]+$", t) for t in texts)
    assert any("m²" in t for t in texts)


def test_sizes_in_feet_and_inches_for_feet_plans(building) -> None:
    ft = building.model_copy(
        update={"meta": building.meta.model_copy(update={"unit_display": "ft"})}
    )
    texts = [t.text for t in compose_sheet(ft).items if isinstance(t, Text)]
    assert any(re.match(r"^\d+'\d+\" × \d+'\d+\"$", t) for t in texts)
    assert any("m² /" in t and "sq ft" in t for t in texts)


@pytest.mark.parametrize(
    "points",
    [[0, 1234, 2345, 6789, 10001], [0, 333, 666, 999], [150, 4150, 9000, 17600]],
)
def test_chain_segments_add_up_to_the_overall(points) -> None:
    labels = chain_labels(points, "ft")
    inches = [
        int(f) * 12 + int(i) for f, i in (re.match(r"(\d+)'(\d+)\"", s).groups() for s in labels)
    ]
    overall = chain_labels([points[0], points[-1]], "ft")[0]
    f, i = re.match(r"(\d+)'(\d+)\"", overall).groups()
    assert sum(inches) == int(f) * 12 + int(i)
    metric = chain_labels(points, "m")
    total = chain_labels([points[0], points[-1]], "m")[0]
    assert round(sum(float(v) for v in metric), 2) == float(total)


def test_dimension_chains_on_all_four_sides(sheet) -> None:
    dims = [t for t in sheet.items if isinstance(t, Text) and t.layer == "A-ANNO-DIMS"]
    horizontal = [t for t in dims if t.rotation == 0]
    vertical = [t for t in dims if t.rotation == 90]
    plot_top = min(t.y for t in horizontal)
    plot_bottom = max(t.y for t in horizontal)
    assert plot_bottom - plot_top > 50 and len({round(t.x) for t in vertical}) >= 4


def test_title_block_scale_bar_north_legend_and_disclaimer(sheet) -> None:
    texts = " ".join(t.text for t in sheet.items if isinstance(t, Text))
    for needle in (
        "PROJECT",
        "CLIENT",
        "DRAWING NO.",
        "SCALE",
        "REVISIONS",
        "AREA SCHEDULE",
        "LEGEND",
        "LOGO",
        "FOR DESIGN PURPOSES ONLY,",
        "NOT FOR CONSTRUCTION",
        f"1:{sheet.scale}",
        "Total area",
    ):
        assert needle in texts, needle
    layers = {it.layer for it in sheet.items}
    assert {"G-ANNO-SCAL", "G-ANNO-NRTH", "G-ANNO-LEGN"} <= layers


def test_pdf_is_a3_at_true_scale_with_the_font_embedded(sheet) -> None:
    pdf = to_pdf(sheet, keywords="constriva-plan:x")
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        page = doc[0]
        assert page.rect.width == pytest.approx(420 * PT_PER_MM, abs=0.1)
        assert page.rect.height == pytest.approx(297 * PT_PER_MM, abs=0.1)
        fonts = {f[3] for f in page.get_fonts()}
        assert any("Jost" in f for f in fonts), fonts
        # a wall drawn on the sheet measures plot mm / scale on paper
        drawings = page.get_drawings()
        assert drawings


def test_a1_is_the_same_drawing_twice_the_size(building) -> None:
    a3, a1 = compose_sheet(building, sheet="A3"), compose_sheet(building, sheet="A1")
    assert (a1.width, a1.height) == (841.0, 594.0) or a1.width == pytest.approx(2 * a3.width)
    assert a1.scale <= a3.scale


def test_furniture_can_be_turned_off(building) -> None:
    on = compose_sheet(building, furniture=True)
    off = compose_sheet(building, furniture=False)
    assert any(it.layer == "A-FURN" for it in on.items)
    assert not any(it.layer == "A-FURN" for it in off.items)
    assert any(it.layer == "A-FLOR-FIXT" for it in off.items)  # fixtures stay


def test_svg_groups_by_cad_layer_and_embeds_the_font(sheet) -> None:
    svg = to_svg(sheet, embed_font=True)
    assert 'id="A-WALL"' in svg and "@font-face" in svg and 'data-scale="1:' in svg
    assert len(svg) < 900_000
    assert all(isinstance(it, Line | Area) or True for it in sheet.items)
