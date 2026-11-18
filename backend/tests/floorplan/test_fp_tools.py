"""Edit tools beyond re-layout: facing / rotate / mirror, doors, windows, room use, units,
undo / version history, and the read-only reports (areas, schedule, openings,
orientation)."""

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from app.modules.ai.floorplan.geometry import door_span, window_span
from app.modules.ai.floorplan.pipeline.edit_engine import (
    EditInterpretation,
    apply_edit,
    edit_plan,
)
from app.modules.ai.floorplan.pipeline.layout.engine import generate_layout
from app.modules.ai.floorplan.pipeline.plan_report import report, zone_of
from app.modules.ai.floorplan.pipeline.plan_tools import facing, transform_plan
from app.modules.ai.floorplan.pipeline.validator import validate
from app.modules.ai.floorplan.schemas.edit_ops import EditOp
from app.modules.ai.floorplan.schemas.plan import FloorPlan, Meta, Plot
from app.modules.ai.floorplan.schemas.program import RoomProgram

PROGRAMS = Path(__file__).parent / "fixtures" / "programs"
OPS = TypeAdapter(list[EditOp])


def _base(name: str) -> tuple[FloorPlan, RoomProgram]:
    data = json.loads((PROGRAMS / f"{name}.json").read_text(encoding="utf-8"))
    program = RoomProgram.model_validate(data["program"])
    plot = Plot.model_validate(data["plot"])
    res = generate_layout(program, plot, Meta(unit_display="ft"), "plan_tools_test")
    assert res.ok, res.attempts
    return res.plan, res.program


@pytest.fixture(scope="module")
def house():
    return _base("house_3bed_12x15")


@pytest.fixture(scope="module")
def east():
    return _base("house_2bed_30x40ft_east")


def ops(*items: dict):
    return OPS.validate_python(list(items))


def _shape(plan: FloorPlan):
    """Everything that must survive a turn: room sizes, door/window widths, furniture."""
    return (
        sorted((r.id, r.type, r.area_m2) for r in plan.rooms),
        sorted((d.id, d.to_room, d.from_room, d.width) for d in plan.doors),
        sorted((w.id, w.room, w.width) for w in plan.windows),
        sorted((f.id, f.room, f.symbol) for f in plan.fixtures),
    )


# ------------------------------------------------------------------ transforms


@pytest.mark.parametrize("kind", [90, 180, 270, "left_right", "top_bottom"])
def test_transform_keeps_plan_valid_and_complete(house, kind):
    plan, program = house
    new = transform_plan(plan, kind)
    assert validate(new).ok, validate(new).feedback()
    assert _shape(new) == _shape(plan)
    if kind in (90, 270):
        assert (new.plot.width, new.plot.depth) == (plan.plot.depth, plan.plot.width)


def test_four_quarter_turns_and_two_mirrors_are_identity(house):
    plan, _ = house
    p = plan
    for _ in range(4):
        p = transform_plan(p, 90)
    assert p == plan
    assert transform_plan(transform_plan(plan, "left_right"), "left_right") == plan
    assert transform_plan(transform_plan(plan, "top_bottom"), "top_bottom") == plan


def test_openings_land_on_the_transformed_wall_positions(house):
    plan, _ = house
    new = transform_plan(plan, 90)
    d = plan.plot.depth

    def turn(p):
        return (d - p[1], p[0])

    for old_door in plan.doors:
        new_door = next(x for x in new.doors if x.id == old_door.id)
        a, b = door_span(plan, old_door).start, door_span(plan, old_door).end
        na, nb = door_span(new, new_door).start, door_span(new, new_door).end
        assert {turn(a), turn(b)} == {tuple(na), tuple(nb)}
    for old_win in plan.windows:
        new_win = next(x for x in new.windows if x.id == old_win.id)
        a, b = window_span(plan, old_win).start, window_span(plan, old_win).end
        na, nb = window_span(new, new_win).start, window_span(new, new_win).end
        assert {turn(a), turn(b)} == {tuple(na), tuple(nb)}


def test_set_facing_turns_the_house(east):
    plan, program = east
    assert facing(plan) == "east"
    res = apply_edit(plan, program, ops({"op": "set_facing", "side": "north"}))
    assert res.ok, res.message
    assert facing(res.plan) == "north"
    assert res.plan.plot.road_side == "north"
    assert validate(res.plan, res.program).ok
    assert len(res.summary) == 1 and "north-facing" in res.summary[0]


def test_set_facing_same_side_explains(east):
    plan, program = east
    res = apply_edit(plan, program, ops({"op": "set_facing", "side": "east"}))
    assert res.status == "impossible"
    assert "already faces east" in res.message


def test_whole_plan_ops_must_be_alone(house):
    plan, program = house
    room = next(r for r in plan.rooms if r.type == "kitchen")
    res = apply_edit(
        plan,
        program,
        ops(
            {"op": "rotate_plan", "degrees": 90}, {"op": "rename_room", "id": room.id, "label": "K"}
        ),
    )
    assert res.status == "impossible"
    assert "on its own" in res.message


# --------------------------------------------------------------- doors, windows


def test_remove_only_door_of_a_room_is_refused(house):
    plan, program = house
    bed = next(r for r in plan.rooms if r.type == "bedroom")
    doors = [d for d in plan.doors if bed.id in (d.to_room, d.from_room)]
    if len(doors) != 1:
        pytest.skip("this layout gives the bedroom more than one door")
    res = apply_edit(plan, program, ops({"op": "remove_door", "id": doors[0].id}))
    assert res.status == "impossible"
    assert "no way in" in res.message
    assert res.plan is plan


def test_set_door_width_and_minimum(house):
    plan, program = house
    door = next(d for d in plan.doors if d.from_room is None)
    res = apply_edit(plan, program, ops({"op": "set_door_width", "id": door.id, "width": 60}))
    assert res.status == "impossible"
    res = apply_edit(plan, program, ops({"op": "set_door_width", "id": door.id, "width": 80}))
    assert res.ok, res.message
    assert next(d for d in res.plan.doors if d.id == door.id).width == 80


def test_add_door_between_neighbours(house):
    plan, program = house
    linked = {frozenset((d.to_room, d.from_room)) for d in plan.doors}
    from app.modules.ai.floorplan.geometry import shared_wall_interval

    pair = None
    for a in plan.rooms:
        for b in plan.rooms:
            if a.id >= b.id or a.is_open or b.is_open or a.type == "shaft" or b.type == "shaft":
                continue
            if frozenset((a.id, b.id)) in linked:
                continue
            for wall in ("north", "south", "east", "west"):
                iv = shared_wall_interval(a, wall, b)
                if iv and iv[1] - iv[0] > 150:
                    pair = (a, b)
    if pair is None:
        pytest.skip("no unlinked neighbours with a long shared wall")
    res = apply_edit(plan, program, ops({"op": "add_door", "room": pair[0].id, "to": pair[1].id}))
    assert res.ok, res.message
    assert len(res.plan.doors) == len(plan.doors) + 1


def test_remove_and_resize_window(house):
    plan, program = house
    win = max(plan.windows, key=lambda w: w.width)
    res = apply_edit(plan, program, ops({"op": "set_window_width", "id": win.id, "width": 60}))
    assert res.ok, res.message
    assert next(w for w in res.plan.windows if w.id == win.id).width == 60
    res = apply_edit(plan, program, ops({"op": "remove_window", "id": win.id}))
    assert res.ok, res.message
    assert all(w.id != win.id for w in res.plan.windows)


# ------------------------------------------------------------ room use, units


def test_change_room_type(house):
    plan, program = house
    bed = max((r for r in plan.rooms if r.type == "bedroom"), key=lambda r: r.area_m2)
    res = apply_edit(plan, program, ops({"op": "change_room_type", "id": bed.id, "type": "study"}))
    assert res.ok, res.message
    room = res.plan.room(bed.id)
    assert room.type == "study" and (room.x, room.y, room.w, room.h) == (bed.x, bed.y, bed.w, bed.h)
    assert next(p for p in res.program.rooms if p.id == bed.id).type == "study"


def test_open_and_closed_spaces_cannot_swap_use(house):
    plan, program = house
    bed = next(r for r in plan.rooms if r.type == "bedroom")
    res = apply_edit(plan, program, ops({"op": "change_room_type", "id": bed.id, "type": "garden"}))
    assert res.status == "impossible"


def test_set_units(house):
    plan, program = house
    res = apply_edit(plan, program, ops({"op": "set_units", "unit": "m"}))
    assert res.ok and res.plan.meta.unit_display == "m"


# ------------------------------------------------------------------- reports


@pytest.mark.parametrize("topic", ["areas", "schedule", "openings", "orientation", "help"])
def test_reports(house, topic):
    plan, _ = house
    text = report(plan, topic)
    assert text.startswith("**")
    if topic == "schedule":
        for r in plan.rooms:
            if r.type != "shaft":
                assert r.label in text


def test_orientation_names_every_room_zone(house):
    plan, _ = house
    text = report(plan, "orientation")
    for r in plan.rooms:
        if r.type != "shaft" and not r.is_open:
            assert f"{r.label}: {zone_of(r, plan)}" in text


class _FakeLLM:
    def __init__(self, interp: EditInterpretation) -> None:
        self.interp = interp

    def structured(self, **_kw):
        return self.interp


def test_info_request_answers_without_changing(house):
    plan, program = house
    res = edit_plan(
        plan, program, "what is the built up area", _FakeLLM(EditInterpretation(info="areas"))
    )
    assert res.status == "info"
    assert "Built-up" in res.message
    assert res.plan is plan


def test_undo_is_handed_to_the_service(house):
    plan, program = house
    interp = EditInterpretation(ops=ops({"op": "undo"}))
    res = edit_plan(plan, program, "undo", _FakeLLM(interp))
    assert res.undo is not None and res.plan is plan
