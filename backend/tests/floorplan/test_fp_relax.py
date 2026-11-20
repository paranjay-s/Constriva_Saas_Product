"""A1: wishes as weighted soft constraints, the relaxation ladder, and a plan every time."""

import pytest

from app.modules.ai.floorplan.pipeline.generate import plot_from_brief
from app.modules.ai.floorplan.pipeline.layout.solver import solve_layout
from app.modules.ai.floorplan.pipeline.layout.topology import build_topology
from app.modules.ai.floorplan.pipeline.room_program import build_program
from app.modules.ai.floorplan.schemas.brief import Brief, PlotSpec, RoomRequest
from app.modules.ai.floorplan.schemas.rules import Place, Touches

pytestmark = pytest.mark.site_rules
FT = 30.48


def _brief(rules=(), w=50, d=80) -> Brief:
    return Brief(
        plot=PlotSpec(width_cm=round(w * FT), depth_cm=round(d * FT), input_unit="ft"),
        bedrooms=2,
        bathrooms=2,
        road_side="south",
        rooms=[
            RoomRequest(type="master_bedroom", attached_bath=True),
            RoomRequest(type="bedroom", attached_bath=True),
            RoomRequest(type="living"),
            RoomRequest(type="kitchen"),
            RoomRequest(type="garden"),
        ],
        rules=list(rules),
    )


def test_contradictory_wishes_are_infeasible_hard_but_solved_soft() -> None:
    rules = [
        Place(kind="place", room="garden", side="front", text="garden at the front"),
        Place(kind="place", room="garden", side="rear", text="garden at the back"),
        Touches(kind="touches", room="kitchen", others=["garden"], text="kitchen by the garden"),
    ]
    b = _brief(rules)
    program, _ = build_program(b, None)
    plot = plot_from_brief(b)
    topo = build_topology(program)
    hard: dict = {}
    assert solve_layout(program, plot, topo, time_limit_s=4, info=hard) is None
    assert hard["status"] == "INFEASIBLE"
    soft: dict = {}
    rooms = solve_layout(program, plot, topo, time_limit_s=6, soft=True, info=soft)
    assert rooms is not None
    # exactly one of the two sides is given up; the touching wish is kept
    assert len(set(soft["unmet"]) & {0, 1}) == 1 and 2 not in soft["unmet"]


@pytest.mark.parametrize("road", ["south", "north", "east", "west"])
def test_the_corridor_layout_always_places_every_room(road: str) -> None:
    from app.modules.ai.floorplan.pipeline.layout.engine import with_spare_garden
    from app.modules.ai.floorplan.pipeline.layout.fallback import corridor_layout

    b = _brief().model_copy(update={"road_side": road})
    program, _ = build_program(b, None)
    plot = plot_from_brief(b)
    program = with_spare_garden(program, plot)
    fb = corridor_layout(program, plot)
    placed = {r.id for r in fb.rooms}
    assert {r.id for r in program.rooms} <= placed
    for r in fb.rooms:
        assert 0 <= r.x and r.x2 <= plot.width and 0 <= r.y and r.y2 <= plot.depth
    for i, a in enumerate(fb.rooms):
        for c in fb.rooms[i + 1 :]:
            ox = min(a.x2, c.x2) - max(a.x, c.x)
            oy = min(a.y2, c.y2) - max(a.y, c.y)
            assert ox <= 0 or oy <= 0, (a.id, c.id)


def test_the_ladder_falls_back_to_the_corridor_layout_and_reports_issues() -> None:
    from app.modules.ai.floorplan.pipeline.generate import meta_from_brief
    from app.modules.ai.floorplan.pipeline.relax import _fallback

    b = _brief()
    program, _ = build_program(b, None)
    res = _fallback(program, plot_from_brief(b), meta_from_brief(b), "p1", [], [], 0.0)
    assert res.step == "fallback" and res.plan.rooms and res.plan.doors
    assert any("corridor" in a for a in res.adjustments)
    assert res.report is not None and not res.report.errors  # errors become notes


def test_random_briefs_always_get_a_plan() -> None:
    """A small, fast slice of tools/floorplan_cases/random_briefs.py (the full run of 50 is
    in docs/pro2/2d/RELAXATION.md)."""
    import random
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools" / "floorplan_cases"))
    from random_briefs import random_brief

    from app.modules.ai.floorplan.pipeline.generate import generate_plan

    rng = random.Random(11)
    for _ in range(6):
        brief = random_brief(rng)
        res = generate_plan(brief, llm=None, solver_time_s=2.0)
        assert res.ok and res.plan is not None and res.plan.rooms
        assert res.report is not None and res.report.ok
