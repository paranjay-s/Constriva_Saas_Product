"""Areas: plot or built-up, the built-up band, setbacks, and the area statement."""

import pytest

from app.modules.ai.floorplan.model.areas import area_lines
from app.modules.ai.floorplan.model.build import build_building
from app.modules.ai.floorplan.model.building import Areas
from app.modules.ai.floorplan.pipeline.brief_parser import (
    AREA_BASIS_QUESTION,
    area_basis_from_words,
    parse_brief,
)
from app.modules.ai.floorplan.pipeline.generate import (
    built_up_target,
    generate_plan,
    plot_from_brief,
)
from app.modules.ai.floorplan.schemas.brief import Brief, BriefForm, PlotSpec, RoomRequest

pytestmark = pytest.mark.site_rules
FT = 30.48


def _brief(**kw) -> Brief:
    base = dict(
        plot=PlotSpec(width_cm=round(50 * FT), depth_cm=round(100 * FT), input_unit="ft"),
        bedrooms=3,
        bathrooms=3,
        road_side="south",
        rooms=[
            RoomRequest(type="master_bedroom", attached_bath=True),
            RoomRequest(type="bedroom", count=2, attached_bath=True),
            RoomRequest(type="living"),
            RoomRequest(type="kitchen"),
            RoomRequest(type="dining"),
            RoomRequest(type="majlis"),
            RoomRequest(type="maid_room"),
            RoomRequest(type="pool"),
        ],
    )
    base.update(kw)
    return Brief(**base)


@pytest.mark.parametrize(
    ("text", "basis"),
    [
        ("5000 sq ft plot, 4 bedrooms", "plot"),
        ("a villa of 5000 sq ft built-up area", "built_up"),
        ("5000 sq ft covered area with a pool", "built_up"),
        ("land of 500 m2 for a villa", "plot"),
        ("4 bedroom villa, 5000 sq ft", None),
        ("4 bedroom villa, 5000 sq ft.\nIt is the built-up area", "built_up"),
        ("5000 sq ft plot with 3500 sq ft built up", "plot"),
    ],
)
def test_area_basis_from_words(text: str, basis: str | None) -> None:
    assert area_basis_from_words(text) == basis


def test_an_area_without_its_basis_is_asked_once_before_drawing() -> None:
    res = parse_brief(BriefForm(prompt="", plot_area=5000, unit="ft", bedrooms=3), None)
    assert res.brief.plot.stated_area_m2 == pytest.approx(464.5, abs=0.1)
    assert AREA_BASIS_QUESTION in res.missing and not res.ready
    answered = parse_brief(
        BriefForm(prompt="", plot_area=5000, unit="ft", bedrooms=3, area_basis="plot"), None
    )
    assert answered.ready


def test_a_built_up_area_makes_a_larger_plot() -> None:
    res = parse_brief(BriefForm(plot_area=3500, unit="ft", bedrooms=3, area_basis="built_up"), None)
    p = res.brief.plot
    assert p.built_up_m2 == pytest.approx(325.2, abs=0.1)
    assert p.width_cm * p.depth_cm / 10_000 == pytest.approx(325.2 / 0.70, rel=0.01)


def test_default_target_is_seventy_percent_inside_the_band() -> None:
    b = _brief(plot=PlotSpec(width_cm=round(80 * FT), depth_cm=round(100 * FT)))
    plot = plot_from_brief(b)
    plot_m2 = plot.width * plot.depth / 10_000
    target, notes = built_up_target(b, plot)
    assert target == pytest.approx(0.70 * plot_m2, rel=0.001) and not notes
    assert (plot.setbacks.front, plot.setbacks.left, plot.setbacks.rear) == (300, 150, 150)


def test_the_persons_share_wins_and_setbacks_cap_it() -> None:
    b = _brief(built_up_share=0.5)
    plot = plot_from_brief(b)
    assert plot.built_up_m2 == pytest.approx(0.5 * plot.width * plot.depth / 10_000, rel=0.01)
    small = _brief(plot=PlotSpec(width_cm=round(30 * FT), depth_cm=round(50 * FT)))
    target, notes = built_up_target(small, plot_from_brief(small))
    assert notes and "setbacks" in notes[0]


def test_area_statement_wording() -> None:
    a = Areas(
        plot_m2=464.52,
        built_up_m2=325.16,
        built_up_net_m2=290.0,
        exterior_m2=139.36,
        coverage=0.7,
        rooms_gross_m2=325.16,
    )
    lines = area_lines(a, "ft")
    assert lines[0] == "Total area 5,000 sq ft (3,500 sq ft built-up + 1,500 sq ft exterior)"
    assert lines[1] == "Total area 464.5 m² (325.2 m² built-up + 139.4 m² exterior), coverage 70%"


def test_a_generated_villa_meets_its_band_and_setbacks() -> None:
    res = generate_plan(_brief(), llm=None, solver_time_s=10)
    assert res.ok, res.message
    plan = res.plan
    x0, y0, x1, y1 = plan.plot.buildable()
    for r in plan.rooms:
        if not r.is_open and r.type != "shaft":
            assert x0 <= r.x and r.x2 <= x1 and y0 <= r.y and r.y2 <= y1, r.id
    b = build_building(plan)
    assert 0.60 <= b.areas.coverage <= 0.76, b.areas
    assert abs(b.areas.rooms_gross_m2 - b.areas.built_up_m2) <= 0.01 * b.areas.built_up_m2
