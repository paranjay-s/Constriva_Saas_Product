"""Phase 5: edit engine (typed ops, locking, summary, impossible edits) and the chat step.

The solver may return different (equally valid) layouts between runs, so most tests
check invariants that must hold for any result:
  - a successful edit gives a plan that passes the validator
  - every room the edit did not move keeps its exact rectangle, furniture and the doors
    between unmoved rooms
  - an impossible edit returns the original plan unchanged, with a reason
"""

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from app.modules.ai.floorplan.pipeline.edit_engine import (
    EditInterpretation,
    apply_edit,
    describe_plan,
    edit_plan,
    program_from_plan,
    topology_from_plan,
)
from app.modules.ai.floorplan.pipeline.layout.engine import generate_layout
from app.modules.ai.floorplan.pipeline.validator import validate
from app.modules.ai.floorplan.schemas.edit_ops import EditOp
from app.modules.ai.floorplan.schemas.plan import FloorPlan, Meta, Plot
from app.modules.ai.floorplan.schemas.program import RoomProgram
from app.modules.ai.llm.client import LLMError

PROGRAMS = Path(__file__).parent / "fixtures" / "programs"
OPS = TypeAdapter(list[EditOp])


def _base(name: str) -> tuple[FloorPlan, RoomProgram]:
    data = json.loads((PROGRAMS / f"{name}.json").read_text(encoding="utf-8"))
    program = RoomProgram.model_validate(data["program"])
    plot = Plot.model_validate(data["plot"])
    res = generate_layout(program, plot, Meta(unit_display="ft"), "plan_edit_test")
    assert res.ok, res.attempts
    return res.plan, res.program


@pytest.fixture(scope="module")
def house():
    return _base("house_3bed_12x15")


@pytest.fixture(scope="module")
def small():
    return _base("house_2bed_30x40ft_east")


def _rect(r):
    return (r.x, r.y, r.w, r.h)


def _assert_invariants(before: FloorPlan, res) -> None:
    if not res.ok:
        assert res.plan is before
        assert res.message
        return
    after = res.plan
    assert validate(after, res.program).ok, validate(after, res.program).feedback()
    old = {r.id: r for r in before.rooms if r.type != "shaft"}
    unmoved = {r.id for r in after.rooms if r.id in old and r.id not in res.moved}
    for r in after.rooms:
        if r.id in unmoved:
            assert _rect(r) == _rect(old[r.id]), f"{r.id} moved but is not reported"

    # furniture of unmoved rooms whose doors did not change is untouched
    def doors_of(plan, rid):
        return {
            (d.id, d.wall, d.offset, d.width, d.swing)
            for d in plan.doors
            if rid in (d.to_room, d.from_room)
        }

    unmoved = {rid for rid in unmoved if doors_of(before, rid) == doors_of(after, rid)}
    old_fx = {
        (f.room, f.symbol, f.x, f.y, f.rotation) for f in before.fixtures if f.room in unmoved
    }
    new_fx = {(f.room, f.symbol, f.x, f.y, f.rotation) for f in after.fixtures if f.room in unmoved}
    assert old_fx == new_fx
    # doors between two unmoved rooms keep id, wall and position
    for d in before.doors:
        if d.to_room in unmoved and (d.from_room is None or d.from_room in unmoved):
            same = [n for n in after.doors if n.id == d.id]
            if same:
                n = same[0]
                assert (n.to_room, n.from_room, n.wall, n.offset, n.width) == (
                    d.to_room,
                    d.from_room,
                    d.wall,
                    d.offset,
                    d.width,
                )
    assert res.summary


# --------------------------------------------------------------- simple operations


def test_rename_changes_only_the_label(house) -> None:
    plan, program = house
    res = apply_edit(
        plan,
        program,
        OPS.validate_python([{"op": "rename_room", "id": "bed_2", "label": "Kids room"}]),
    )
    assert res.ok
    assert res.plan.room("bed_2").label == "KIDS ROOM"
    assert [_rect(r) for r in res.plan.rooms] == [_rect(r) for r in plan.rooms]
    assert next(p for p in res.program.rooms if p.id == "bed_2").label == "KIDS ROOM"
    assert res.moved == []
    assert any("KIDS ROOM" in s for s in res.summary)


def test_window_asked_on_inside_wall_goes_on_an_outside_wall(house) -> None:
    plan, program = house
    from app.modules.ai.floorplan.geometry import exterior_intervals

    sides = ("north", "south", "east", "west")
    room = inside = None
    for r in plan.rooms:
        if r.is_open or r.type == "shaft":
            continue
        ins = [s for s in sides if not exterior_intervals(plan, r, s)]
        if ins and len(ins) < 4:
            room, inside = r, ins
            break
    assert room is not None
    res = apply_edit(
        plan,
        program,
        OPS.validate_python([{"op": "add_window", "room": room.id, "wall": inside[0]}]),
    )
    if not res.ok:  # only when every outside window is already as wide as it can be
        assert "largest windows" in res.message
        return
    old = {w.id: w for w in plan.windows}
    changed = [w for w in res.plan.windows if w.id not in old or w != old[w.id]]
    assert len(changed) == 1 and changed[0].room == room.id
    assert changed[0].wall != inside[0] and exterior_intervals(plan, room, changed[0].wall)
    assert any("inside wall" in line or "widened" in line for line in res.summary)
    assert [_rect(r) for r in res.plan.rooms] == [_rect(r) for r in plan.rooms]


def test_window_without_a_wall_picks_one(house) -> None:
    plan, program = house
    res = apply_edit(plan, program, OPS.validate_python([{"op": "add_window", "room": "bed_2"}]))
    if not res.ok:
        assert "largest windows" in res.message
        return
    assert res.plan.windows != plan.windows
    assert any("window" in line for line in res.summary)


def test_window_in_a_room_without_outside_wall_is_explained(house) -> None:
    plan, program = house
    from app.modules.ai.floorplan.geometry import exterior_intervals

    inner = [
        r
        for r in plan.rooms
        if not r.is_open
        and r.type != "shaft"
        and not any(exterior_intervals(plan, r, s) for s in ("north", "south", "east", "west"))
    ]
    if not inner:
        pytest.skip("every room touches an outside wall in this layout")
    res = apply_edit(
        plan, program, OPS.validate_python([{"op": "add_window", "room": inner[0].id}])
    )
    assert res.status == "impossible" and "no outside wall" in res.message.lower()


def test_add_window_on_outside_wall(house) -> None:
    plan, program = house
    # the bedroom with the most outside wall
    from app.modules.ai.floorplan.geometry import exterior_intervals

    for room in plan.rooms:
        for side in ("north", "south", "east", "west"):
            ivs = exterior_intervals(plan, room, side)
            has_window = any(w.room == room.id and w.wall == side for w in plan.windows)
            if room.type == "dining" and ivs and not has_window:
                res = apply_edit(
                    plan,
                    program,
                    OPS.validate_python(
                        [{"op": "add_window", "room": room.id, "wall": side, "width": 90}]
                    ),
                )
                if res.ok:
                    # a new window, or (wall too short for a useful one) a wider window
                    added = len(res.plan.windows) == len(plan.windows) + 1
                    widened = any("widened" in line for line in res.summary)
                    assert added or widened
                    for w in res.plan.windows:
                        if w.room == room.id and w not in plan.windows:
                            assert w.width >= 90  # never a uselessly small window
                    _assert_invariants(plan, res)
                    return
    pytest.skip("no free outside wall on the dining room in this layout")


def test_move_door_along_its_wall(house) -> None:
    plan, program = house
    door = next(d for d in plan.doors if d.from_room is not None)
    res = apply_edit(
        plan, program, OPS.validate_python([{"op": "move_door", "id": door.id}])
    )  # no offset: centre it on the shared wall
    assert res.ok, res.message
    moved = next(d for d in res.plan.doors if d.id == door.id)
    assert moved.wall == door.wall
    assert [_rect(r) for r in res.plan.rooms] == [_rect(r) for r in plan.rooms]


def test_move_door_to_a_wall_the_rooms_do_not_share_is_refused(house) -> None:
    plan, program = house
    for door in plan.doors:
        if door.from_room is None:
            continue
        to, frm = plan.room(door.to_room), plan.room(door.from_room)
        from app.modules.ai.floorplan.geometry import shared_wall_interval

        for side in ("north", "south", "east", "west"):
            if shared_wall_interval(to, side, frm) is None:
                res = apply_edit(
                    plan,
                    program,
                    OPS.validate_python([{"op": "move_door", "id": door.id, "wall": side}]),
                )
                assert res.status == "impossible" and res.plan is plan
                assert "does not touch" in res.message
                return
    pytest.fail("every door wall was shared on all sides")


def test_unknown_room_is_refused_and_lists_rooms(house) -> None:
    plan, program = house
    res = apply_edit(
        plan, program, OPS.validate_python([{"op": "resize_room", "id": "bed_9", "width_cm": 400}])
    )
    assert res.status == "impossible" and res.plan is plan
    assert "bed_9" in res.message and "bed_2" in res.message


def test_resize_below_minimum_is_refused(house) -> None:
    plan, program = house
    res = apply_edit(
        plan,
        program,
        OPS.validate_python(
            [{"op": "resize_room", "id": "bed_1", "width_cm": 200, "height_cm": 200}]
        ),
    )
    assert res.status == "impossible" and res.plan is plan
    assert "minimum" in res.message


def test_resize_larger_than_plot_is_refused(house) -> None:
    plan, program = house
    res = apply_edit(
        plan,
        program,
        OPS.validate_python(
            [{"op": "resize_room", "id": "bed_1", "width_cm": 5000, "height_cm": 400}]
        ),
    )
    assert res.status == "impossible" and "larger than the plot" in res.message


# --------------------------------------------------------------- layout operations


LAYOUT_CASES = [
    [{"op": "resize_room", "id": "bed_2", "width_cm": 360}],
    [{"op": "add_room", "type": "store", "target_area_m2": 3}],
    [{"op": "add_room", "type": "bath", "next_to": "bed_2"}],
    [{"op": "remove_room", "id": "bed_2"}],
    [{"op": "swap_rooms", "a": "bed_1", "b": "bed_2"}],
    [{"op": "move_room", "id": "kitchen_1", "anchor": "north-east"}],
]


@pytest.mark.parametrize("ops", LAYOUT_CASES, ids=lambda o: o[0]["op"])
@pytest.mark.parametrize("which", ["house", "small"])
def test_layout_edits_keep_unmentioned_rooms_exactly(which, ops, request) -> None:
    plan, program = request.getfixturevalue(which)
    if any(
        o.get(k) not in {r.id for r in plan.rooms} for o in ops for k in ("id", "a", "b") if k in o
    ):
        pytest.skip("room not in this plan")
    res = apply_edit(plan, program, OPS.validate_python(ops))
    _assert_invariants(plan, res)


def test_remove_room_also_removes_its_attached_bath(house) -> None:
    plan, program = house
    attached = [p.id for p in program.rooms if p.attached_to == "bed_1"]
    assert attached
    res = apply_edit(plan, program, OPS.validate_python([{"op": "remove_room", "id": "bed_1"}]))
    assert res.ok, res.message
    ids = {r.id for r in res.plan.rooms}
    assert "bed_1" not in ids and not (set(attached) & ids)
    assert {p.id for p in res.program.rooms} == {r.id for r in res.plan.rooms if r.type != "shaft"}
    _assert_invariants(plan, res)


def test_swap_two_bedrooms_exchanges_places(small) -> None:
    plan, program = small
    a, b = plan.room("bed_1"), plan.room("bed_2")
    res = apply_edit(
        plan, program, OPS.validate_python([{"op": "swap_rooms", "a": "bed_1", "b": "bed_2"}])
    )
    if not res.ok:
        assert res.plan is plan and res.message
        return
    assert _rect(res.plan.room("bed_1")) == _rect(b)
    assert _rect(res.plan.room("bed_2")) == _rect(a)
    _assert_invariants(plan, res)


def test_resize_to_current_size_moves_nothing_else(small) -> None:
    plan, program = small
    r = plan.room("bed_2")
    res = apply_edit(
        plan,
        program,
        OPS.validate_python(
            [{"op": "resize_room", "id": "bed_2", "width_cm": r.w, "height_cm": r.h}]
        ),
    )
    assert res.ok, res.message
    others = [x for x in res.plan.rooms if x.id != "bed_2" and x.type != "shaft"]
    assert all(_rect(x) == _rect(plan.room(x.id)) for x in others)


def test_too_big_resize_is_done_as_far_as_it_fits(small) -> None:
    plan, program = small
    before = plan.room("bed_2")
    res = apply_edit(
        plan,
        program,
        OPS.validate_python(
            [{"op": "resize_room", "id": "bed_2", "width_cm": 800, "height_cm": 800}]
        ),
    )
    if res.ok:
        after = res.plan.room("bed_2")
        assert after.area_m2 > before.area_m2
        assert any("as large as fits" in line for line in res.summary)
        _assert_invariants(plan, res)
    else:  # nothing at all fits: the plan is untouched and the reason is given
        assert res.plan is plan and res.program is program and res.message


def test_locked_mode_refuses_instead_of_moving_others(small) -> None:
    plan, program = small
    res = apply_edit(
        plan,
        program,
        OPS.validate_python(
            [{"op": "resize_room", "id": "bed_2", "width_cm": 800, "height_cm": 800}]
        ),
        allow_reflow=False,
    )
    if res.ok:  # partial growth using neighbours only
        assert not any("re-arranged" in line for line in res.summary)
        _assert_invariants(plan, res)
    else:
        assert res.plan is plan
        assert any("Allow other rooms to move" in a for a in res.alternatives)


def test_set_plot_replans_everything(small) -> None:
    plan, program = small
    res = apply_edit(
        plan,
        program,
        OPS.validate_python(
            [
                {
                    "op": "set_plot",
                    "width_cm": plan.plot.width + 150,
                    "depth_cm": plan.plot.depth + 150,
                }
            ]
        ),
    )
    assert res.ok, res.message
    assert res.plan.plot.width == plan.plot.width + 150
    assert validate(res.plan, res.program).ok
    assert "re-planned" in res.summary[0]


def test_set_plot_must_be_alone(small) -> None:
    plan, program = small
    res = apply_edit(
        plan,
        program,
        OPS.validate_python(
            [
                {"op": "set_plot", "width_cm": 1200, "depth_cm": 1500},
                {"op": "rename_room", "id": "bed_1", "label": "X"},
            ]
        ),
    )
    assert res.status == "impossible" and "on its own" in res.message


# -------------------------------------------------------------- helpers and the LLM


def test_topology_from_plan_follows_the_doors(house) -> None:
    plan, _ = house
    topo = topology_from_plan(plan)
    entrance = next(d for d in plan.doors if d.from_room is None)
    assert topo.root == entrance.to_room
    for child, parent in topo.parent.items():
        if parent is not None:
            assert any({d.from_room, d.to_room} == {child, parent} for d in plan.doors)


def test_program_from_plan_matches_rooms(house) -> None:
    plan, _ = house
    prog = program_from_plan(plan)
    assert {p.id for p in prog.rooms} == {r.id for r in plan.rooms if r.type != "shaft"}
    res = apply_edit(
        plan, None, OPS.validate_python([{"op": "rename_room", "id": "kitchen_1", "label": "Cook"}])
    )
    assert res.ok


def test_llm_sees_sizes_but_no_coordinates(house) -> None:
    plan, _ = house
    desc = describe_plan(plan)
    for room in desc["rooms"]:
        assert "x" not in room and "y" not in room
        assert {"id", "label", "size", "position"} <= set(room)
    assert all("offset" not in d for d in desc["doors"])


class FakeLLM:
    def __init__(self, reply=None, fail=False):
        self.reply, self.fail, self.calls = reply, fail, []

    def structured(self, *, system, user, schema, task):
        self.calls.append((task, json.loads(user)))
        if self.fail:
            raise LLMError("down")
        return schema.model_validate(self.reply)


def test_edit_plan_uses_llm_ops(house) -> None:
    plan, program = house
    llm = FakeLLM({"ops": [{"op": "rename_room", "id": "living_1", "label": "Hall"}]})
    res = edit_plan(plan, program, "call the living room hall", llm)
    assert res.ok and res.plan.room("living_1").label == "HALL"
    task, payload = llm.calls[0]
    assert task == "edit_ops" and payload["request"] == "call the living room hall"


def test_edit_plan_asks_when_unclear(house) -> None:
    plan, program = house
    llm = FakeLLM({"ops": [], "question": "Which bedroom do you mean?"})
    res = edit_plan(plan, program, "make the bedroom bigger", llm)
    assert res.status == "needs_clarification" and res.plan is plan
    assert res.message == "Which bedroom do you mean?"


def test_edit_plan_reports_unsupported(house) -> None:
    plan, program = house
    llm = FakeLLM({"ops": [], "unsupported": ["swimming pool"]})
    res = edit_plan(plan, program, "add a pool", llm)
    assert res.status == "no_change" and "swimming pool" in res.message


def test_edit_plan_degrades_without_llm(house) -> None:
    plan, program = house
    assert edit_plan(plan, program, "x", None).status == "failed"
    res = edit_plan(plan, program, "x", FakeLLM(fail=True))
    assert res.status == "failed" and res.plan is plan


def test_interpretation_schema_rejects_coordinates() -> None:
    with pytest.raises(ValueError):
        EditInterpretation.model_validate(
            {"ops": [{"op": "move_room", "id": "bed_1", "x": 100, "y": 200}]}
        )
