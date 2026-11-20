"""Leftover gaps next to the garden/pool are drawn as part of it, not as OPEN shafts."""

from types import SimpleNamespace

from app.modules.ai.floorplan.legacy_plan_json import to_legacy_plan_json
from app.modules.ai.floorplan.pipeline.layout.solver import fill_holes_with_shafts
from app.modules.ai.floorplan.pipeline.validator import ValidationReport, _check_shafts
from app.modules.ai.floorplan.render import render_svg
from app.modules.ai.floorplan.schemas.plan import FloorPlan, Plot, Room


def _rooms() -> list[Room]:
    # 1000 x 600 plot: garden on the west, living on the east; a gap between them at
    # the north that touches the garden, and an isolated gap enclosed by enclosed rooms.
    return [
        Room(id="garden_1", type="garden", label="GARDEN", x=0, y=0, w=300, h=600),
        Room(id="living_1", type="living", label="LIVING", x=500, y=0, w=500, h=300),
        Room(id="kitchen_1", type="kitchen", label="KITCHEN", x=300, y=300, w=700, h=300),
    ]


def test_gap_touching_garden_joins_it() -> None:
    rooms = fill_holes_with_shafts(_rooms(), Plot(width=1000, depth=600))
    shafts = [r for r in rooms if r.type == "shaft"]
    assert len(shafts) == 1
    s = shafts[0]
    assert (s.x, s.y, s.w, s.h) == (300, 0, 200, 300)
    assert s.part_of == "garden_1"
    assert s.label == "GARDEN"


def test_gap_away_from_outdoor_stays_open() -> None:
    rooms = [
        Room(id="living_1", type="living", label="LIVING", x=0, y=0, w=400, h=600),
        Room(id="kitchen_1", type="kitchen", label="KITCHEN", x=600, y=0, w=400, h=600),
        Room(id="bed_1", type="bedroom", label="BED ROOM", x=400, y=300, w=200, h=300),
    ]
    out = fill_holes_with_shafts(rooms, Plot(width=1000, depth=600))
    shafts = [r for r in out if r.type == "shaft"]
    assert len(shafts) == 1 and shafts[0].part_of is None and shafts[0].label == "OPEN"


def test_joined_gap_is_not_a_leftover_shaft() -> None:
    rooms = fill_holes_with_shafts(_rooms(), Plot(width=1000, depth=600))
    rep = ValidationReport()
    _check_shafts(SimpleNamespace(rooms=rooms), rep)  # type: ignore[arg-type]
    assert not any(i.code == "LARGE_SHAFTS" for i in rep.warnings)


def test_joined_gap_drawn_without_own_label(sample_plan: FloorPlan) -> None:
    outdoor = next(r for r in sample_plan.rooms if r.is_open and r.type != "shaft")
    gap = Room(
        id="shaft_99",
        type="shaft",
        label="UNIQUEGAPLABEL",
        x=0,
        y=0,
        w=50,
        h=50,
        part_of=outdoor.id,
    )
    plan = sample_plan.model_copy(update={"rooms": [*sample_plan.rooms, gap]})
    svg = render_svg(plan)
    assert "UNIQUEGAPLABEL" not in svg
    assert to_legacy_plan_json(plan)  # joined gaps export as outdoor space
