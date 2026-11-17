"""Pool layouts: beside the house, U-shape, centre, two blocks (pipeline/pool_layouts.py).

Plans are generated without the LLM (typical sizes), so these run offline.
"""

import networkx as nx
import pytest

from app.modules.ai.floorplan.geometry import shared_wall_interval
from app.modules.ai.floorplan.pipeline.brief_parser import parse_brief
from app.modules.ai.floorplan.pipeline.edit_engine import apply_edit
from app.modules.ai.floorplan.pipeline.generate import GenerationResult, generate_plan
from app.modules.ai.floorplan.pipeline.layout.topology import build_topology
from app.modules.ai.floorplan.pipeline.pool_layouts import (
    LOUNGE_ID,
    POOL_TOILET_ID,
    Choice,
    apply_layout,
    layout_chain,
    rect_frame,
)
from app.modules.ai.floorplan.pipeline.requirements import expand_rooms
from app.modules.ai.floorplan.pipeline.room_program import build_program
from app.modules.ai.floorplan.pipeline.validator import OUTSIDE, door_graph, validate
from app.modules.ai.floorplan.schemas.brief import Brief, BriefForm, RoomRequest
from app.modules.ai.floorplan.schemas.edit_ops import SetPoolLayout
from tests.floorplan.test_fp_llm_pipeline import FakeLLM, _text

FT = 30.48
SIDES = ("north", "south", "east", "west")


def _brief(w=50, d=50, beds=4, layout=None, road="south", extras=("pool", "dining")) -> Brief:
    pr = parse_brief(
        BriefForm(
            plot_width=w,
            plot_depth=d,
            unit="ft",
            bedrooms=beds,
            extras=list(extras),
            road_side=road,
            pool_layout=layout,
        )
    )
    assert pr.ready
    return pr.brief


_cache: dict[tuple, GenerationResult] = {}


def _gen(**kw) -> GenerationResult:
    key = tuple(sorted(kw.items()))
    if key not in _cache:
        _cache[key] = generate_plan(_brief(**kw))
    return _cache[key]


def _pool(plan):
    return next(r for r in plan.rooms if r.type == "pool")


def _edges(plan, room) -> set[str]:
    p = plan.plot
    return {
        s
        for s, hit in (
            ("west", room.x == 0),
            ("east", room.x2 == p.width),
            ("north", room.y == 0),
            ("south", room.y2 == p.depth),
        )
        if hit
    }


def _room_on(plan, pool, side) -> bool:
    """Rooms line at least 70 % of this side of the pool."""
    lined = sum(
        iv[1] - iv[0]
        for r in plan.rooms
        if not r.is_open and (iv := shared_wall_interval(pool, side, r))
    )
    return lined >= 0.7 * (pool.w if side in ("north", "south") else pool.h)


# ------------------------------------------------------------------ fitting rules


def test_chain_keeps_request_when_it_fits() -> None:
    chain, notes = layout_chain("centre", int(50 * FT), int(50 * FT), "south", 4)
    assert [c.layout for c in chain] == ["centre", "u_shape", "side"]
    assert notes == []


def test_chain_skips_what_cannot_fit_and_says_why() -> None:
    chain, notes = layout_chain("centre", int(30 * FT), int(40 * FT), "south", 3)
    assert [c.layout for c in chain] == ["side"]
    assert "middle" in notes[0] and "each way" in notes[0]
    assert notes[-1].endswith("Using a pool beside the house instead.")


def test_two_block_axis_follows_plot_shape() -> None:
    deep, _ = layout_chain("two_block", int(40 * FT), int(70 * FT), "south", 4)
    wide, _ = layout_chain("two_block", int(80 * FT), int(40 * FT), "south", 4)
    east, _ = layout_chain("two_block", int(40 * FT), int(80 * FT), "east", 4)
    assert deep[0] == Choice("two_block", "front_back")
    assert wide[0] == Choice("two_block", "side_by_side")
    assert east[0] == Choice("two_block", "side_by_side")  # 80 ft runs along an east road


def test_two_block_needs_two_bedrooms() -> None:
    chain, notes = layout_chain("two_block", int(60 * FT), int(60 * FT), "south", 1)
    assert chain[0].layout == "u_shape"
    assert "2 bedrooms" in notes[0]


# ---------------------------------------------------------------- room program


def test_two_block_assigns_blocks() -> None:
    brief = _brief(beds=4).model_copy(
        update={
            "rooms": [
                RoomRequest(type="master_bedroom", attached_bath=True),
                RoomRequest(type="bedroom", count=3),
                RoomRequest(type="living"),
                RoomRequest(type="kitchen"),
                RoomRequest(type="pool"),
            ]
        }
    )
    reqs, _ = expand_rooms(brief)
    out, notes = apply_layout(reqs, Choice("two_block", "front_back"))
    block = {r.id: r.block for r in out}
    assert block["bed_1"] == "main" and block["bath_1"] == "main"  # master + its bath
    assert {block["bed_2"], block["bed_3"], block["bed_4"]} == {"guest"}
    assert block[LOUNGE_ID] == "guest" and block[POOL_TOILET_ID] == "pool"
    assert block["living_1"] == "main" and block["kitchen_1"] == "main"
    assert any(r.type == "bath" and r.block == "guest" for r in out)  # no pool crossing
    assert not any(r.type == "lobby" for r in out)  # 1 bedroom in front: no corridor
    assert any("guest block has 3 bedrooms" in n for n in notes)


def test_person_can_choose_the_block() -> None:
    brief = _brief(beds=3).model_copy(
        update={
            "rooms": [
                RoomRequest(type="master_bedroom", block="guest"),
                RoomRequest(type="bedroom", count=2),
                RoomRequest(type="pool"),
            ]
        }
    )
    reqs, _ = expand_rooms(brief)
    out, _ = apply_layout(reqs, Choice("two_block", "front_back"))
    block = {r.id: r.block for r in out}
    assert block["bed_1"] == "guest"
    assert "main" in {block["bed_2"], block["bed_3"]}  # someone still lives in front


def test_lounge_is_not_duplicated() -> None:
    reqs, _ = expand_rooms(_brief(beds=3))
    once, _ = apply_layout(reqs, Choice("two_block", "front_back"))
    twice, _ = apply_layout(once, Choice("two_block", "front_back"))
    assert [r.id for r in twice].count(LOUNGE_ID) == 1


def test_topology_routes_through_the_deck() -> None:
    program, _ = build_program(_brief(beds=4), pool=Choice("two_block", "front_back"))
    topo = build_topology(program)
    by_id = {r.id: r for r in program.rooms}
    assert by_id[topo.parent["pool_1"]].type == "living"
    assert topo.parent[LOUNGE_ID] == "pool_1" and topo.parent[POOL_TOILET_ID] == "pool_1"
    for r in program.rooms:
        if r.block == "guest" and r.id != LOUNGE_ID and not r.attached_to:
            assert topo.parent[r.id] == LOUNGE_ID
    assert topo.root != LOUNGE_ID


# ------------------------------------------------------------------- generated plans


@pytest.mark.parametrize("road", ["south", "east"])
def test_centre_pool_has_rooms_all_round(road: str) -> None:
    res = _gen(layout="centre", road=road, w=50, d=55)
    assert res.ok, res.message
    pool = _pool(res.plan)
    assert _edges(res.plan, pool) == set()
    assert all(_room_on(res.plan, pool, s) for s in SIDES)
    assert any(r.id == POOL_TOILET_ID for r in res.plan.rooms)
    assert validate(res.plan, res.program).ok


def test_u_shape_pool_is_open_only_to_the_rear() -> None:
    res = _gen(layout="u_shape")
    assert res.ok, res.message
    pool = _pool(res.plan)
    assert _edges(res.plan, pool) == {"north"}  # road south -> rear north
    assert all(_room_on(res.plan, pool, s) for s in ("south", "east", "west"))


@pytest.mark.parametrize(("w", "d"), [(50, 50), (80, 40)])
def test_two_block_separates_main_and_guest(w: int, d: int) -> None:
    res = _gen(layout="two_block", w=w, d=d)
    assert res.ok, res.message
    plan, program = res.plan, res.program
    W, D, road = plan.plot.width, plan.plot.depth, plan.plot.road_side
    pool = _pool(plan)
    pd0, pd1, pa0, pa1 = rect_frame(pool.x, pool.y, pool.x2, pool.y2, W, D, road)
    blocks = {p.id: p.block for p in program.rooms}
    main = [r for r in plan.rooms if blocks.get(r.id) == "main"]
    guest = [r for r in plan.rooms if blocks.get(r.id) == "guest"]
    assert main and guest
    f = {r.id: rect_frame(r.x, r.y, r.x2, r.y2, W, D, road) for r in main + guest}
    if program.pool_axis == "front_back":
        assert all(f[r.id][1] <= pd0 for r in main) and all(f[r.id][0] >= pd1 for r in guest)
    else:
        left = all(f[r.id][3] <= pa0 for r in main) and all(f[r.id][2] >= pa1 for r in guest)
        right = all(f[r.id][2] >= pa1 for r in main) and all(f[r.id][3] <= pa0 for r in guest)
        assert left or right
    # every guest room is reached from the street through the pool deck
    g = door_graph(plan)
    g.remove_edges_from([(OUTSIDE, "pool_1")])  # only through the house
    for r in guest:
        path = nx.shortest_path(g, OUTSIDE, r.id)
        assert "pool_1" in path and LOUNGE_ID in path or r.id == LOUNGE_ID
    assert validate(plan, program).ok


def test_two_block_that_does_not_fit_falls_back_with_a_note() -> None:
    res = _gen(layout="two_block", w=30, d=40, beds=3)
    assert res.ok, res.message
    assert any("did not fit" in w or "not possible" in w for w in res.warnings)
    assert res.program.pool_layout in ("u_shape", "side")


def test_validator_rejects_a_pool_in_the_wrong_place() -> None:
    res = _gen(layout="u_shape")
    assert res.ok
    wrong = res.program.model_copy(update={"pool_layout": "centre"})
    assert "POOL_LAYOUT" in validate(res.plan, wrong).codes()


# ----------------------------------------------------------------- reading the text


def test_text_pool_layout_adds_the_pool() -> None:
    llm = FakeLLM({"brief_parser": _text(pool_layout="centre", bedrooms=3)})
    pr = parse_brief(
        BriefForm(plot_width=50, plot_depth=50, prompt="pool in the middle of the house"), llm
    )
    assert pr.brief.pool_layout == "centre"
    assert any(r.type == "pool" for r in pr.brief.rooms)


def test_covered_walkway_makes_a_u_shape() -> None:
    llm = FakeLLM(
        {
            "brief_parser": _text(
                pool_layout="two_block",
                covered_walkway=True,
                bedrooms=4,
                rooms=[{"type": "pool"}],
            )
        }
    )
    pr = parse_brief(BriefForm(plot_width=60, plot_depth=60, prompt="x"), llm)
    assert pr.brief.pool_layout == "u_shape"
    assert any("covered walkway" in a for a in pr.brief.assumptions)


def test_only_one_pool() -> None:
    llm = FakeLLM({"brief_parser": _text(bedrooms=3, rooms=[{"type": "pool", "count": 2}])})
    pr = parse_brief(BriefForm(plot_width=60, plot_depth=60, prompt="two pools"), llm)
    pools = [r for r in pr.brief.rooms if r.type == "pool"]
    assert len(pools) == 1 and pools[0].count == 1
    assert any("one swimming pool" in w.lower() for w in pr.warnings)


def test_form_pool_layout_and_text_conflict_text_wins() -> None:
    llm = FakeLLM({"brief_parser": _text(pool_layout="two_block", rooms=[{"type": "pool"}])})
    pr = parse_brief(
        BriefForm(plot_width=60, plot_depth=60, bedrooms=3, pool_layout="centre", prompt="x"),
        llm,
    )
    assert pr.brief.pool_layout == "two_block"
    assert any(c.field == "pool layout" for c in pr.brief.conflicts)


# ---------------------------------------------------------------------- chat edits


def test_edit_moves_the_pool_and_back() -> None:
    side = _gen(layout=None, w=50, d=55, beds=3)
    assert side.ok and side.program.pool_layout == "side"
    two = apply_edit(
        side.plan, side.program, [SetPoolLayout(op="set_pool_layout", layout="two_block")]
    )
    assert two.ok, two.message
    assert two.program.pool_layout == "two_block"
    assert any(r.id == LOUNGE_ID for r in two.plan.rooms)
    assert validate(two.plan, two.program).ok
    back = apply_edit(two.plan, two.program, [SetPoolLayout(op="set_pool_layout", layout="side")])
    assert back.ok, back.message
    ids = {r.id for r in back.plan.rooms}
    assert LOUNGE_ID not in ids  # one house again
    assert any(r.type == "lobby" for r in back.plan.rooms)  # 3 bedrooms need a corridor


def test_edit_same_layout_is_no_change() -> None:
    side = _gen(layout=None, w=50, d=55, beds=3)
    res = apply_edit(side.plan, side.program, [SetPoolLayout(op="set_pool_layout", layout="side")])
    assert res.status == "no_change"


def test_edit_without_a_pool_explains() -> None:
    res0 = _gen(layout=None, w=40, d=50, beds=2, extras=("dining",))
    res = apply_edit(
        res0.plan, res0.program, [SetPoolLayout(op="set_pool_layout", layout="centre")]
    )
    assert res.status == "impossible" and "no pool" in res.message.lower()
