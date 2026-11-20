"""Layout orchestrator: room program -> validated FloorPlan.

Order: templates first, then the CP-SAT solver (a few seeds). Every candidate gets doors,
windows and fixtures placed by code, then must pass the validator. Only a valid plan is
returned in `plan`; otherwise `plan` is None and `report` explains why.
"""

import uuid
from dataclasses import dataclass, field

from app.modules.ai.floorplan.pipeline.layout.fixtures import place_fixtures
from app.modules.ai.floorplan.pipeline.layout.openings import place_doors, place_windows
from app.modules.ai.floorplan.pipeline.layout.solver import (
    fill_gaps,
    fill_holes_with_shafts,
    solve_layout,
)
from app.modules.ai.floorplan.pipeline.layout.templates import compact_rows
from app.modules.ai.floorplan.pipeline.layout.topology import Topology, build_topology
from app.modules.ai.floorplan.pipeline.pool_layouts import is_special
from app.modules.ai.floorplan.pipeline.validator import ValidationReport, validate
from app.modules.ai.floorplan.rules import GARDEN_MIN_SPARE
from app.modules.ai.floorplan.schemas.common import ZONE_BY_TYPE
from app.modules.ai.floorplan.schemas.plan import FloorPlan, Meta, Plot, Room
from app.modules.ai.floorplan.schemas.program import ProgramRoom, RoomProgram


@dataclass
class LayoutResult:
    plan: FloorPlan | None
    report: ValidationReport | None
    method: str = ""
    attempts: list[str] = field(default_factory=list)
    program: RoomProgram | None = None  # the program actually laid out (may add a garden)

    @property
    def ok(self) -> bool:
        return self.plan is not None


def with_spare_garden(program: RoomProgram, plot: Plot) -> RoomProgram:
    """Add a garden when the program leaves real space spare and has none.

    Parking and courtyards are capped, so the garden is what takes leftover plot area
    (at the front, on the road side) instead of rooms being stretched or holes left.
    """
    if any(r.type == "garden" for r in program.rooms):
        return program
    plot_m2 = plot.width * plot.depth / 10_000
    spare = plot_m2 - sum(r.target_area_m2 for r in program.rooms) * 1.08
    if spare < max(6.0, GARDEN_MIN_SPARE * plot_m2):
        return program
    ids = {r.id for r in program.rooms}
    gid = next(f"garden_{i}" for i in range(1, 99) if f"garden_{i}" not in ids)
    garden = ProgramRoom(
        id=gid,
        type="garden",
        label="GARDEN",
        target_area_m2=round(max(6.0, spare * 0.5), 2),
        zone=ZONE_BY_TYPE["garden"],
    )
    return program.model_copy(update={"rooms": [*program.rooms, garden]})


def assemble(
    rooms: list[Room],
    topo: Topology,
    plot: Plot,
    meta: Meta,
    plan_id: str,
    program: RoomProgram | None = None,
) -> FloorPlan:
    """Rooms + topology -> plan with doors, windows and fixtures placed by code; the
    program's rules add the doors they ask for (rules_check.add_rule_doors)."""
    plan = FloorPlan(id=plan_id, meta=meta, plot=plot, rooms=rooms)
    plan = plan.model_copy(update={"doors": place_doors(plan, topo, plot.road_side)})
    if program is not None and program.rules:
        from app.modules.ai.floorplan.pipeline.rules_check import add_rule_doors

        plan = add_rule_doors(plan, program)
    plan = plan.model_copy(update={"windows": place_windows(plan)})
    plan = plan.model_copy(update={"fixtures": place_fixtures(plan)})
    return FloorPlan.model_validate(plan.model_dump(by_alias=True))


def generate_layout(
    program: RoomProgram,
    plot: Plot,
    meta: Meta | None = None,
    plan_id: str | None = None,
    *,
    use_templates: bool = True,
    fixed: dict[str, Room] | None = None,
    time_limit_s: float = 8.0,
    seeds: tuple[int, ...] = (0, 1),
    workers: int = 8,
) -> LayoutResult:
    meta = meta or Meta()
    if not fixed:
        program = with_spare_garden(program, plot)
    plan_id = plan_id or f"plan_{uuid.uuid4().hex[:12]}"
    attempts: list[str] = []
    best: tuple[int, FloorPlan, ValidationReport, str] | None = None

    def consider(plan: FloorPlan, method: str) -> LayoutResult | None:
        nonlocal best
        rep = validate(plan, program)
        attempts.append(f"{method}: {'ok' if rep.ok else '; '.join(rep.feedback()[:3])}")
        if rep.ok:
            return LayoutResult(plan, rep, method, attempts, program)
        if best is None or len(rep.errors) < best[0]:
            best = (len(rep.errors), plan, rep, method)
        return None

    templates_ok = not plot.has_setbacks  # the row templates fill the whole plot
    if use_templates and templates_ok and not fixed and not is_special(program.pool_layout):
        tpl = compact_rows(program, plot)
        if tpl is None:
            attempts.append("compact_rows: not applicable")
        else:
            topo = Topology(root=tpl.root, parent=tpl.parent)
            res = consider(assemble(tpl.rooms, topo, plot, meta, plan_id, program), tpl.name)
            if res:
                return res

    topo = build_topology(program)
    targets = {r.id: r.target_area_m2 for r in program.rooms}
    # First try an exact tiling (no gaps at all); then relaxed solves whose leftover gaps
    # are absorbed by neighbours or become open shafts.
    # Exact tiling is much easier with edges on every second grid line (30 cm);
    # relaxed runs use the full 15 cm grid. With locked rooms only relaxed runs are used.
    runs = [] if fixed else [(seeds[0], True, 2, min(time_limit_s, 6.0))]
    runs += [(s, False, 1, time_limit_s) for s in seeds]
    for seed, exact, coarse, limit in runs:
        name = f"solver({'exact' if exact else 'relaxed'}, seed={seed})"
        rooms = solve_layout(
            program,
            plot,
            topo,
            fixed=fixed,
            time_limit_s=limit,
            seed=seed,
            workers=workers,
            exact_tiling=exact,
            coarse=coarse,
        )
        if rooms is None:
            attempts.append(f"{name}: no layout found in time")
            continue
        if not exact:
            rooms = fill_holes_with_shafts(fill_gaps(rooms, plot, targets), plot)
        res = consider(assemble(rooms, topo, plot, meta, plan_id, program), name)
        if res:
            return res

    return LayoutResult(None, best[2] if best else None, best[3] if best else "", attempts, program)
