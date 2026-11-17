"""Swimming pool and sit-out/deck: brief -> plan -> drawing, feasibility, chat edits."""

import io

import pytest
from ezdxf import recover
from pydantic import TypeAdapter

from app.modules.ai.floorplan.geometry import pool_water
from app.modules.ai.floorplan.pipeline.brief_parser import parse_brief
from app.modules.ai.floorplan.pipeline.edit_engine import apply_edit
from app.modules.ai.floorplan.pipeline.feasibility import check_feasibility
from app.modules.ai.floorplan.pipeline.generate import generate_plan
from app.modules.ai.floorplan.pipeline.validator import validate
from app.modules.ai.floorplan.render.dxf_renderer import render_dxf
from app.modules.ai.floorplan.render.svg_renderer import POOL_COLORS, render_svg
from app.modules.ai.floorplan.rules import POOL_WALKWAY_CM
from app.modules.ai.floorplan.schemas.brief import BriefForm
from app.modules.ai.floorplan.schemas.edit_ops import EditOp
from app.modules.ai.floorplan.schemas.plan import Room
from tests.floorplan.test_fp_llm_pipeline import FakeLLM, _text

OPS = TypeAdapter(list[EditOp])

POOL_TEXT = _text(
    rooms=[
        {"type": "master_bedroom", "attached_bath": True},
        {"type": "bedroom", "count": 2},
        {"type": "dining"},
        {"type": "pool"},
        {"type": "garden"},
        {"type": "deck"},
    ],
    preferences=[
        {"kind": "adjacent", "a": "pool", "b": "garden", "text": "pool in the garden"},
        {"kind": "adjacent", "a": "deck", "b": "living", "text": "sit-out next to living"},
    ],
)


@pytest.fixture(scope="module")
def pool_plan():
    llm = FakeLLM({"brief_parser": POOL_TEXT})
    form = BriefForm(
        plot_width=60, plot_depth=70, unit="ft", road_side="south", prompt="villa with pool"
    )
    pr = parse_brief(form, llm)
    res = generate_plan(pr.brief, llm=None)
    assert res.ok, (res.message, res.attempts)
    return res


def test_pool_water_leaves_a_walkway() -> None:
    room = Room(id="pool_1", type="pool", label="SWIMMING POOL", x=0, y=0, w=600, h=900)
    x, y, w, h = pool_water(room)
    lo, hi = POOL_WALKWAY_CM
    assert lo <= x <= hi and lo <= y <= hi
    assert w == 600 - 2 * x and h == 900 - 2 * y
    assert min(w, h) >= 300


def test_brief_keeps_pool_and_deck(pool_plan) -> None:
    types = {r.type for r in pool_plan.plan.rooms}
    assert {"pool", "deck", "garden"} <= types


def test_generated_pool_is_outdoors_and_valid(pool_plan) -> None:
    plan = pool_plan.plan
    assert validate(plan, pool_plan.program).ok
    pool = next(r for r in plan.rooms if r.type == "pool")
    on_edge = pool.x == 0 or pool.y == 0 or pool.x2 == plan.plot.width or pool.y2 == plan.plot.depth
    assert on_edge
    assert not any(d.to_room == pool.id or d.from_room == pool.id for d in plan.doors)
    deck = next(r for r in plan.rooms if r.type == "deck")
    assert any(deck.id in (d.to_room, d.from_room) for d in plan.doors)  # sit-out has a door


def test_pool_is_drawn_and_exported(pool_plan) -> None:
    plan = pool_plan.plan
    svg = render_svg(plan)
    assert POOL_COLORS["water"] in svg and "SWIMMING POOL" in svg
    doc, auditor = recover.read(io.BytesIO(render_dxf(plan)))
    assert not auditor.has_errors
    assert len(doc.modelspace().query('LWPOLYLINE[layer=="POOL"]')) == 2  # water edge + coping
    assert len(doc.modelspace().query('LINE[layer=="HATCH"]')) > 0  # deck planks


def test_small_plot_offers_to_drop_the_pool() -> None:
    llm = FakeLLM(
        {"brief_parser": _text(rooms=[{"type": "bedroom", "count": 2}, {"type": "pool"}])}
    )
    pr = parse_brief(BriefForm(plot_width=26, plot_depth=32, unit="ft", prompt="x"), llm)
    feas = check_feasibility(pr.brief)
    assert not feas.ok
    assert any("pool" in o for o in feas.options)


def test_add_pool_by_chat_edit(pool_plan) -> None:
    plan, program = pool_plan.plan, pool_plan.program
    pool = next(r for r in plan.rooms if r.type == "pool")
    removed = apply_edit(plan, program, OPS.validate_python([{"op": "remove_room", "id": pool.id}]))
    assert removed.ok, removed.message
    assert not any(r.type == "pool" for r in removed.plan.rooms)
    garden = next(r for r in removed.plan.rooms if r.type == "garden")
    added = apply_edit(
        removed.plan,
        removed.program,
        OPS.validate_python([{"op": "add_room", "type": "pool", "next_to": garden.id}]),
    )
    if added.ok:
        assert len([r for r in added.plan.rooms if r.type == "pool"]) == 1
        assert validate(added.plan, added.program).ok
        assert any("SWIMMING POOL" in line for line in added.summary)
    else:
        assert added.plan is removed.plan and added.message
