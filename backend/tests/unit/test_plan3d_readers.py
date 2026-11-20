"""The OpenCV plan reader and the read-versus-truth comparison."""

import pytest

from app.modules.ai.floorplan.model.build import build_building
from app.modules.ai.floorplan.model.planto3d import to_planto3d
from app.modules.ai.floorplan.render.exports import export_plan
from app.modules.plan3d.compare import compare_floor
from app.modules.plan3d.raster_reader import read_pdf_page, scale_from_text
from tests.floorplan.test_fp_building import _pool_plan


@pytest.fixture(scope="module")
def plan_and_truth():
    plan = _pool_plan()
    b = build_building(plan)
    return plan, b, to_planto3d(b)["floors"][0]


def test_a_floor_compared_with_itself_scores_full_marks(plan_and_truth) -> None:
    _, _, truth = plan_and_truth
    scores = compare_floor(truth, truth)
    for key in ("walls", "doors", "windows", "rooms"):
        assert scores[key]["recall"] == 1.0 and scores[key]["precision"] == 1.0, key
    assert scores["room_types"] == 1.0


def test_an_empty_read_scores_nothing(plan_and_truth) -> None:
    _, _, truth = plan_and_truth
    scores = compare_floor(truth, {"walls": [], "openings": [], "rooms": []})
    assert scores["walls"]["recall"] == 0.0 and scores["rooms"]["recall"] == 0.0


def test_scale_from_the_sheet_text() -> None:
    assert scale_from_text("GROUND FLOOR PLAN  SCALE 1:125 @ A3") == 125
    assert scale_from_text("no scale here") is None


def test_the_opencv_reader_finds_the_walls_and_rooms_of_our_drawing(plan_and_truth) -> None:
    plan, b, truth = plan_and_truth
    pdf = export_plan(plan, "pdf", building=b).data
    res = read_pdf_page(pdf)
    scores = compare_floor(truth, res.floor)
    # measured on 20 generated plans in docs/pro/2d/ROUNDTRIP.md; here a floor, not a target
    assert scores["walls"]["recall"] >= 0.7 and scores["walls"]["precision"] >= 0.6
    assert scores["rooms"]["recall"] >= 0.5
