"""Calculator, geometry, room matching, catalog matching, composer number check."""

import pytest

from app.modules.ai.material_agent.calculator import (
    Applied,
    build_report,
    coverage_shares,
    quantity_line,
    wastage_for,
)
from app.modules.ai.material_agent.compose import numbers_ok, template_explanation
from app.modules.ai.material_agent.geometry import AppArea, NeedsInput, application_area, rect_room
from app.modules.ai.material_agent.normalise import find_material, match_catalog, normalise
from app.modules.ai.material_agent.schemas import (
    ApplicationRequest,
    ManualSpace,
    Material,
    Overrides,
    TargetSpace,
)
from app.modules.ai.material_agent.space import (
    clean_name,
    manual_target,
    match_room,
    room_kind,
    rooms_from_plan,
)
from app.modules.ai.material_agent.units import fmt, round_half_up, to_ft
from tests.material_agent.conftest import TV_WALL, plan_json


def _mats():
    return normalise(TV_WALL.materials)


def _kitchen(**kw) -> TargetSpace:
    return TargetSpace(source="manual", label="Kitchen", room=rect_room("Kitchen", 10, 8, 10, **kw))


# ------------------------------------------------------------ worked examples


def test_worked_example_1_tv_wall():
    """TV wall 12 x 10 ft, 70 % fluted veneer, 30 % marble, 10 % wastage."""
    target = manual_target(ManualSpace(kind="wall", length=12, height=10, label="TV wall"))
    report = build_report(_mats(), target, [], Overrides(), 1).report
    veneer = next(ln for ln in report.lines if "veneer" in ln.material.lower())
    marble = next(ln for ln in report.lines if "marble" in ln.material.lower())
    assert veneer.surface_sqft == 120
    assert veneer.net_qty == 84.0 and veneer.wastage_pct == 10 and veneer.total_qty == 92.4
    assert veneer.buy_qty == 3 and veneer.buy_unit == "sheets (8 × 4 ft)"
    assert marble.net_qty == 36.0 and marble.total_qty == 39.6
    # the floor material cannot be measured on a single wall: shown, not quantified
    floor = next(m for m in _mats() if m.surface == "floor")
    assert floor.id in report.identified_only


def test_worked_example_2_kitchen_platform_l_shape():
    """Kitchen 10 x 8 ft, L-shape, depth 2 ft -> 32 sq ft, 35.2 with 10 % wastage."""
    marble = next(m for m in _mats() if "marble" in m.name.lower())
    area = application_area(
        _kitchen(), ApplicationRequest(application="platform", layout="l_shape")
    )
    assert isinstance(area, AppArea)
    assert area.area_sqft == pytest.approx(32.0)
    assert [b.formula for b in area.breakdown] == ["10 × 2", "(8 − 2) × 2"]
    line = quantity_line(marble, area, 1.0)
    assert line.net_qty == 32.0 and line.total_qty == 35.2
    assert "corner counted once" in area.breakdown[1].label
    assert any("Platform depth 2 ft" in a for a in area.assumptions)


# ------------------------------------------------------------------ geometry


@pytest.mark.parametrize(
    ("layout", "expected"),
    [
        ("one_wall", 20.0),
        ("l_shape", 32.0),
        ("u_shape", 8 * 2 + (10 - 2) * 2 * 2),
        ("parallel", 40.0),
        ("island", 18.0),
    ],
)
def test_platform_layouts(layout, expected):
    area = application_area(_kitchen(), ApplicationRequest(application="platform", layout=layout))
    assert isinstance(area, AppArea)
    assert area.area_sqft == pytest.approx(expected)


def test_platform_without_layout_asks_one_question():
    res = application_area(_kitchen(), ApplicationRequest(application="platform"))
    assert isinstance(res, NeedsInput) and res.missing == "layout"
    assert res.options == ["One wall", "L-shape", "U-shape", "Parallel", "Island"]


def test_platform_run_never_crosses_a_door():
    # 10 x 8 kitchen, a 3 ft door on the first 10 ft wall
    plan = plan_json([("Kitchen", 0, 0, 10, 8)], doors=[((0, 0), (10, 0), 5, 3)])
    room = rooms_from_plan(plan)[0]
    assert [o.side for o in room.openings] == [0]
    target = TargetSpace(source="project", label="k", room=room)
    one = application_area(target, ApplicationRequest(application="platform", layout="one_wall"))
    assert isinstance(one, AppArea)
    # the clear 10 ft wall opposite the door wins over the 10 - 3 = 7 ft wall
    assert one.area_sqft == pytest.approx(20.0)
    lshape = application_area(target, ApplicationRequest(application="platform", layout="l_shape"))
    assert lshape.area_sqft == pytest.approx(10 * 2 + 6 * 2)
    assert "door" not in " ".join(b.label for b in lshape.breakdown)


def test_walls_floor_ceiling_and_openings():
    target = TargetSpace(
        source="manual", label="r", room=rect_room("Bedroom", 12, 10, 10, doors=1, windows=1)
    )
    walls = application_area(target, ApplicationRequest(application="all_walls"))
    assert walls.area_sqft == pytest.approx(44 * 10 - 21 - 16)
    assert application_area(target, ApplicationRequest(application="floor")).area_sqft == 120
    assert application_area(target, ApplicationRequest(application="ceiling")).area_sqft == 120
    q = application_area(target, ApplicationRequest(application="one_wall"))
    assert isinstance(q, NeedsInput) and q.missing == "side" and len(q.options) == 4
    one = application_area(target, ApplicationRequest(application="one_wall", side=1))
    assert one.area_sqft == 100


def test_backsplash_follows_the_wall_runs():
    area = application_area(
        _kitchen(), ApplicationRequest(application="backsplash", layout="l_shape")
    )
    assert area.area_sqft == pytest.approx((10 + 8) * 2)


def test_wall_target_needs_room_for_floor():
    target = manual_target(ManualSpace(kind="wall", length=12, height=10))
    res = application_area(target, ApplicationRequest(application="floor"))
    assert isinstance(res, NeedsInput) and res.missing == "space"


# ---------------------------------------------------------------- calculator


def test_rounding_and_units():
    assert round_half_up(92.40000000000001) == 92.4
    assert round_half_up(0.05) == 0.1
    assert fmt(12.0) == "12" and fmt(92.4) == "92.4"
    assert to_ft(3, "m") == pytest.approx(9.8425, abs=1e-4)
    assert to_ft(3048, "mm") == pytest.approx(10)
    assert to_ft(24, "in") == 2


def test_wastage_sources():
    m = Material(
        id="m1",
        catalog_id="engineered_wood",
        name="oak",
        display_name="Oak",
        category="wood_floor",
        surface="floor",
    )
    assert wastage_for(m)[0] == 8
    herring = m.model_copy(update={"pattern": "herringbone"})
    assert wastage_for(herring)[0] == 15
    assert wastage_for(m, 12)[0] == 12
    other = Material(
        id="m2", name="mystery", display_name="Mystery", category="other", surface="wall"
    )
    assert wastage_for(other)[0] == 10


def test_buy_units_boxes_and_paint():
    tile = Material(
        id="t",
        catalog_id="vitrified_tile",
        name="tile",
        display_name="Tile",
        category="tile",
        surface="floor",
    )
    line = quantity_line(tile, AppArea(label="Floor", area_sqft=100), 1.0)
    assert line.total_qty == 110 and line.buy_qty == 8  # 110 / 15.5 = 7.1 -> 8 boxes
    paint = Material(
        id="p",
        catalog_id="emulsion_paint",
        name="paint",
        display_name="Paint",
        category="paint",
        surface="wall",
    )
    pl = quantity_line(paint, AppArea(label="Walls", area_sqft=400), 1.0)
    assert (
        pl.total_qty == 420 and pl.buy_qty == 9 and pl.buy_unit == "litres (2 coats)"
    )  # 420 x 2 / 100 = 8.4


def test_coverage_shares():
    a = Material(
        id="a", name="a", display_name="A", category="x", surface="wall", coverage_ratio=0.8
    )
    b = Material(
        id="b", name="b", display_name="B", category="x", surface="wall", coverage_ratio=0.6
    )
    shares, notes = coverage_shares([a, b], {})
    assert sum(shares.values()) == pytest.approx(1.0) and notes
    c = Material(id="c", name="c", display_name="C", category="x", surface="wall")
    shares, _ = coverage_shares([a, c], {})
    assert shares["c"] == pytest.approx(0.2)
    shares, _ = coverage_shares([c], {})
    assert shares["c"] == 1.0
    shares, _ = coverage_shares([a, c], {"a": 0.5})
    assert shares == {"a": 0.5, "c": 0.5}


def test_report_overrides_and_applied():
    mats = _mats()
    target = manual_target(ManualSpace(kind="room", length=12, width=10, height=10, label="Living"))
    marble = next(m for m in mats if "marble" in m.name.lower())
    kitchen = _kitchen()
    applied = [
        Applied(
            material_id=marble.id,
            request=ApplicationRequest(application="platform", layout="l_shape"),
            target=kitchen,
        )
    ]
    res = build_report(mats, target, applied, Overrides(wastage_pct={marble.id: 5}), 2).report
    platform = next(ln for ln in res.lines if "platform" in ln.application)
    assert platform.total_qty == round_half_up(32 * 1.05)
    floor = next(ln for ln in res.lines if ln.application == "Living floor")
    assert floor.surface_sqft == 120
    taller = build_report(mats, target, [], Overrides(ceiling_height_ft=12), 3).report
    walls = next(ln for ln in taller.lines if "veneer" in ln.material.lower())
    assert walls.surface_sqft == 44 * 12


def test_no_target_identifies_only():
    res = build_report(_mats(), None, [], Overrides(), 1).report
    assert not res.lines and len(res.identified_only) == 3
    assert "Add the room or wall size" in template_explanation(res, _mats())


# ------------------------------------------------------------ catalog + names


def test_catalog_matching():
    mats = _mats()
    assert mats[0].catalog_id == "fluted_veneer_panel"
    assert mats[1].catalog_id == "italian_marble"
    assert mats[2].catalog_id == "engineered_wood"
    assert match_catalog("something nobody sells") is None
    assert match_catalog("quartz countertop", "countertop")["id"] == "quartz"
    assert match_catalog("herringbone oak floor", "floor")["id"] == "herringbone_wood"
    assert find_material(mats, "marble")[0].id == mats[1].id
    assert find_material(mats, "the veneer")[0].id == mats[0].id
    assert find_material(mats, "granite") == []


def test_unknown_material_is_kept_as_other():
    from app.modules.ai.material_agent.schemas import DetectedMaterial

    out = normalise(
        [DetectedMaterial(name="hand-painted resin artwork xyz", category="art", surface="wall")]
    )
    assert out[0].catalog_id is None and out[0].display_name.startswith("Hand-painted")


def test_room_names_and_matching():
    assert clean_name("KITCHEN 10'0 X 8'0") == "Kitchen"
    assert room_kind("Modular kitchen") == "kitchen"
    assert room_kind("washroom") == "bathroom"
    assert room_kind("Master Bedroom") == "master_bedroom"
    plan = plan_json(
        [
            ("Kitchen", 0, 0, 10, 8),
            ("Master Bedroom", 10, 0, 14, 12),
            ("Bedroom 2", 0, 8, 12, 10),
            ("Bedroom 3", 12, 12, 11, 10),
            ("Toilet", 24, 0, 5, 8),
        ]
    )
    rooms = rooms_from_plan(plan)
    assert rooms[0].area_sqft == pytest.approx(80, abs=0.01) and rooms[
        0
    ].height_ft == pytest.approx(10)
    assert match_room(rooms, "kitchen").room.name == "Kitchen"
    assert match_room(rooms, "modular kitchen").room.name == "Kitchen"
    assert match_room(rooms, "washroom").room.name == "Toilet"
    assert match_room(rooms, "bedroom 2").room.name == "Bedroom 2"
    amb = match_room(rooms, "bedroom")
    assert amb.status == "ambiguous" and len(amb.options) == 3
    assert match_room(rooms, "pooja").status == "not_found"


# ------------------------------------------------------------------ composer


def test_composer_number_check():
    source = '{"total_sq_ft": "92.4", "buy": "3 sheets", "wastage_percent": "10", "share": 0.7}'
    assert numbers_ok(
        "Fluted veneer needs 92.4 sq ft, about 3 sheets, with 10% wastage (70% of the wall).",
        source,
    )
    assert not numbers_ok("You need 95 sq ft.", source)
