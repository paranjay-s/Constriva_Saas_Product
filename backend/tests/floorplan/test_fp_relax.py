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
