"""A2: the colour presentation plan, a second view of the same building model."""

import re

import pymupdf
import pytest

from app.modules.ai.floorplan.drawing.presentation import FLOOR, SITE, WATER
from app.modules.ai.floorplan.model.build import build_building
from app.modules.ai.floorplan.model.embed import signed_model
from app.modules.ai.floorplan.render.exports import export_plan
from tests.floorplan.snapshot_util import normalise, sample_plan


@pytest.fixture(scope="module")
def nandu():
    plan = sample_plan("nandu")
    return plan, build_building(plan)


def _texts(svg: str) -> list[str]:
    return re.findall(r"<text[^>]*>([^<]*)</text>", svg)


def test_same_words_numbers_and_title_block_as_the_engineering_drawing(nandu) -> None:
    plan, b = nandu
    eng = export_plan(plan, "svg", building=b).data.decode()
    pres = export_plan(plan, "svg", building=b, view="presentation").data.decode()
    eng_t, pres_t = _texts(eng), _texts(pres)
    legend_only = {t for t in set(pres_t) ^ set(eng_t)}
    # every room name, size, area, chain, title-block line and the disclaimer is kept; only
    # legend entries differ (colour swatches instead of hatches)
    assert set(eng_t) - set(pres_t) <= {
        "HINGED DOOR", "SLIDING DOOR", "WINDOW", "LAWN / GARDEN", "SETBACK LINE"
    }, legend_only
    assert "Jost" in pres and "FOR DESIGN PURPOSES ONLY," in pres_t


def test_floors_site_and_water_are_filled_with_muted_colours(nandu) -> None:
    plan, b = nandu
    pres = export_plan(plan, "svg", building=b, view="presentation").data.decode()
    for colour in (FLOOR["living"], FLOOR["master_bedroom"], FLOOR["bath"], SITE["garden"], WATER):
        assert f'fill="{colour}"' in pres
    # muted: every fill used is light and low in saturation (no bright colour)
    for hex_ in set(re.findall(r'fill="(#[0-9a-f]{6})"', pres)):
        r, g, bl = (int(hex_[i : i + 2], 16) for i in (1, 3, 5))
        if max(r, g, bl) > 0xC0:  # light fills only; walls and ink are dark greys
            assert max(r, g, bl) - min(r, g, bl) <= 0x30, hex_


def test_presentation_pdf_carries_the_signed_model_and_names_itself(nandu) -> None:
    plan, b = nandu
    exp = export_plan(plan, "pdf", building=b, view="presentation")
    assert exp.filename.endswith("-presentation.pdf")
    model = signed_model(exp.data)
    assert model is not None and len(model.storeys[0].rooms) == len(b.storeys[0].rooms)
    with pymupdf.open(stream=exp.data, filetype="pdf") as doc:
        assert doc.page_count == 1
    png = export_plan(plan, "png", building=b, dpi=60, view="presentation").data
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.parametrize("fmt", ["dxf", "ifc"])
def test_cad_formats_stay_engineering_only(nandu, fmt: str) -> None:
    plan, b = nandu
    eng = export_plan(plan, fmt, building=b).data
    pres = export_plan(plan, fmt, building=b, view="presentation").data
    if fmt == "dxf":
        assert normalise(eng, "dxf") == normalise(pres, "dxf")
    else:  # IFC carries a timestamp and GUIDs; same size and same entities
        assert eng.count(b"IFCSPACE") == pres.count(b"IFCSPACE")
