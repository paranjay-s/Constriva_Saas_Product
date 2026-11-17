"""Layout tests: templates, CP-SAT solver, locking, openings, fixtures (no LLM)."""

import json
from itertools import combinations
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from shapely.geometry import box

from app.modules.ai.floorplan.pipeline.layout import generate_layout
from app.modules.ai.floorplan.pipeline.layout.grid import Grid
from app.modules.ai.floorplan.pipeline.layout.solver import (
    fill_gaps,
    fill_holes_with_shafts,
    solve_layout,
)
from app.modules.ai.floorplan.pipeline.layout.templates import compact_rows
from app.modules.ai.floorplan.pipeline.layout.topology import build_topology
from app.modules.ai.floorplan.pipeline.validator import validate
from app.modules.ai.floorplan.schemas.plan import FloorPlan, Meta, Plot, Room
from app.modules.ai.floorplan.schemas.program import RoomProgram

PROGRAMS = Path(__file__).parent / "fixtures" / "programs"


def _load(name: str) -> tuple[RoomProgram, Plot, Meta]:
    d = json.loads((PROGRAMS / f"{name}.json").read_text(encoding="utf-8"))
    return (
        RoomProgram.model_validate(d["program"]),
        Plot.model_validate(d["plot"]),
        Meta.model_validate(d.get("meta", {})),
    )


def _assert_geometry(rooms: list[Room], plot: Plot) -> None:
    for r in rooms:
        assert r.x >= 0 and r.y >= 0 and r.x2 <= plot.width and r.y2 <= plot.depth, r
    for a, b in combinations(rooms, 2):
        inter = box(a.x, a.y, a.x2, a.y2).intersection(box(b.x, b.y, b.x2, b.y2)).area
        assert inter <= 1, f"{a.id} overlaps {b.id}"


# ---------------------------------------------------------------------- grid


def test_grid_edges_exact_and_round_trip() -> None:
    g = Grid.for_plot(1113, 1676)  # 36'6" x 55'
    assert g.x_cm(0) == 0 and g.x_cm(g.nx) == 1113 and g.y_cm(g.ny) == 1676
    for u in range(g.nx + 1):
        assert g.x_units(g.x_cm(u)) == u
    assert [g.x_cm(u) for u in range(g.nx + 1)] == sorted(g.x_cm(u) for u in range(g.nx + 1))


# ------------------------------------------------------------------ topology


def test_topology_parents() -> None:
    program, _, _ = _load("house_3bed_12x15")
    topo = build_topology(program)
    assert topo.root == "foyer_1"
    assert topo.parent["bath_1"] == "bed_1"
    assert topo.parent["dress_1"] == "bed_1"
    assert topo.parent["kitchen_1"] == "dining_1"
    assert topo.parent["living_1"] == "foyer_1"
    assert topo.parent["garden_1"] is None  # open edge area, reached from outside


# ----------------------------------------------------------------- templates


@pytest.mark.parametrize("road", ["south", "east", "north", "west"])
def test_template_handles_compact_house_on_every_road_side(road: str) -> None:
    program, plot, meta = _load("house_2bed_template_12x11")
    if road in ("east", "west"):
        plot = Plot(width=plot.depth, depth=plot.width, road_side=road)
    else:
        plot = plot.model_copy(update={"road_side": road})
    res = generate_layout(program, plot, meta)
    assert res.ok, res.attempts
    assert res.method == "compact_rows"
    entrance = [d for d in res.plan.doors if d.from_room is None]
    assert len(entrance) == 1 and entrance[0].wall == road
    assert entrance[0].to_room == "foyer_1"


def test_template_returns_none_for_unsupported_program() -> None:
    program, plot, _ = _load("villa_4bed_courtyard_18x14")
    assert compact_rows(program, plot) is None  # courtyard: solver territory


def test_template_plan_has_doors_windows_and_furniture() -> None:
    program, plot, meta = _load("house_2bed_template_12x11")
    plan = generate_layout(program, plot, meta).plan
    assert plan is not None
    rooms_with_window = {w.room for w in plan.windows}
    for rid in ("bed_1", "bed_2", "kitchen_1", "living_1"):
        assert rid in rooms_with_window
    symbols = {(f.room, f.symbol) for f in plan.fixtures}
    assert ("bed_1", "bed_double") in symbols
    assert ("kitchen_1", "kitchen_counter") in symbols
    assert ("bath_1", "toilet") in symbols
    assert ("dining_1", "dining_6") in symbols or ("dining_1", "dining_4") in symbols
    # attached bath opens straight into its bedroom
    assert any({d.from_room, d.to_room} == {"bed_1", "bath_1"} for d in plan.doors)


# -------------------------------------------------------------------- solver


@pytest.mark.parametrize(
    "name", ["house_3bed_12x15", "house_2bed_30x40ft_east", "villa_4bed_courtyard_18x14"]
)
def test_generate_valid_plans_for_hand_written_programs(name: str) -> None:
    program, plot, meta = _load(name)
    res = generate_layout(program, plot, meta)
    assert res.ok, res.attempts
    assert validate(res.plan, program).ok
    ids = {r.id for r in res.plan.rooms}
    assert {r.id for r in program.rooms} <= ids
    _assert_geometry(res.plan.rooms, plot)
    assert res.plan.meta.project == meta.project
    assert any(d.from_room is None for d in res.plan.doors)


def test_locked_rooms_keep_exact_geometry() -> None:
    program, plot, meta = _load("house_2bed_30x40ft_east")
    first = generate_layout(program, plot, meta)
    assert first.ok
    keep = {rid: first.plan.room(rid) for rid in ("bed_1", "bath_1", "kitchen_1")}
    second = generate_layout(program, plot, meta, fixed=keep, seeds=(3,))
    assert second.ok, second.attempts
    for rid, before in keep.items():
        after = second.plan.room(rid)
        assert (after.x, after.y, after.w, after.h) == (before.x, before.y, before.w, before.h)
        assert after.locked


def test_program_too_big_for_plot_is_rejected_not_faked() -> None:
    program, _, meta = _load("house_3bed_12x15")
    res = generate_layout(program, Plot(width=600, depth=600), meta, time_limit_s=2, seeds=(0,))
    assert not res.ok and res.plan is None
    assert res.attempts


def test_fill_gaps_and_shafts_cover_the_plot() -> None:
    plot = Plot(width=600, depth=400)
    rooms = [
        Room(id="a", type="living", label="A", x=0, y=0, w=300, h=400),
        Room(id="b", type="bedroom", label="B", x=300, y=0, w=300, h=300),
        Room(id="g", type="garden", label="G", x=300, y=330, w=200, h=70),
    ]
    grown = fill_gaps(rooms, plot, {"a": 12, "b": 9, "g": 1})
    filled = fill_holes_with_shafts(grown, plot)
    _assert_geometry(filled, plot)
    area = sum(r.w * r.h for r in filled)
    assert area == plot.width * plot.depth
    assert any(r.type == "shaft" for r in filled) or grown != rooms


# ---------------------------------------------------------------- properties

ROOM_TYPES = st.sampled_from(["bedroom", "master_bedroom"])


@st.composite
def compact_programs(draw):
    n_bed = draw(st.integers(1, 3))
    rooms = []
    for i in range(n_bed):
        bt = "master_bedroom" if i == 0 else "bedroom"
        rooms.append({"id": f"bed_{i + 1}", "type": bt, "target_area_m2": draw(st.floats(10, 18))})
        if draw(st.booleans()):
            rooms.append(
                {
                    "id": f"bath_{i + 1}",
                    "type": "bath",
                    "target_area_m2": draw(st.floats(3.2, 5)),
                    "attached_to": f"bed_{i + 1}",
                }
            )
    if draw(st.booleans()):
        rooms.append({"id": "bath_c", "type": "bath", "target_area_m2": draw(st.floats(3.2, 5))})
    rooms += [
        {"id": "living_1", "type": "living", "target_area_m2": draw(st.floats(14, 26))},
        {"id": "kitchen_1", "type": "kitchen", "target_area_m2": draw(st.floats(7, 11))},
    ]
    if draw(st.booleans()):
        rooms.append({"id": "dining_1", "type": "dining", "target_area_m2": draw(st.floats(8, 14))})
    if draw(st.booleans()):
        rooms.append({"id": "foyer_1", "type": "foyer", "target_area_m2": draw(st.floats(4, 7))})
    if draw(st.booleans()):
        rooms.append(
            {"id": "garden_1", "type": "garden", "target_area_m2": draw(st.floats(10, 30))}
        )
    for r in rooms:
        r.setdefault("label", r["type"].upper())
        r.setdefault("zone", "private")
    program = RoomProgram.model_validate({"rooms": rooms})
    total = sum(r.target_area_m2 for r in program.rooms) * draw(st.floats(1.15, 1.45))
    ratio = draw(st.floats(0.6, 1.6))
    width = int((total * 10_000 * ratio) ** 0.5)
    depth = int(total * 10_000 / width)
    road = draw(st.sampled_from(["south", "north", "east", "west"]))
    return program, Plot(width=width, depth=depth, road_side=road)


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(compact_programs())
def test_property_template_never_overlaps_or_leaves_plot(case) -> None:
    program, plot = case
    tpl = compact_rows(program, plot)
    if tpl is None:
        return
    _assert_geometry(tpl.rooms, plot)
    covered = sum(r.w * r.h for r in tpl.rooms)
    assert covered == plot.width * plot.depth  # guillotine tiling: no gaps


@settings(max_examples=6, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(compact_programs())
def test_property_solver_never_overlaps_or_leaves_plot(case) -> None:
    program, plot = case
    rooms = solve_layout(program, plot, build_topology(program), time_limit_s=2, workers=4)
    if rooms is None:
        return
    _assert_geometry(rooms, plot)


@settings(max_examples=6, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(compact_programs())
def test_property_only_valid_plans_are_returned(case) -> None:
    program, plot = case
    res = generate_layout(program, plot, time_limit_s=2, seeds=(0,), workers=4)
    if res.ok:
        assert validate(res.plan, program).ok
        _assert_geometry(res.plan.rooms, plot)
        assert isinstance(res.plan, FloorPlan)
    else:
        assert res.plan is None
