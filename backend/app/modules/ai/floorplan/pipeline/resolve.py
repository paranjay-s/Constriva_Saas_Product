"""Full re-solve: lay the whole plan out again from its program and all its rules.

Used when the person asks for it ("break the plan", "start over", "re-plan"), when they
add layout rules, and when an edit does not fit the current layout. Nothing is locked;
the time budget is FLOORPLAN_FULL_RESOLVE_S (30 s by default). If no layout satisfies
every rule, each rule is dropped in turn (newest first) to find the ones that conflict,
and the two closest layouts that work are returned as options the person can pick.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from app.modules.ai.floorplan.pipeline.layout.engine import generate_layout
from app.modules.ai.floorplan.schemas.plan import FloorPlan
from app.modules.ai.floorplan.schemas.program import RoomProgram
from app.modules.ai.floorplan.schemas.rules import describe_rule
from app.modules.ai.floorplan.settings import get_settings

logger = logging.getLogger("construtiva.ai.floorplan.resolve")
Progress = Callable[[str, str], None]
MAX_RULES_TRIED = 6  # conflict search: at most this many rules are dropped in turn
DIAG_SOLVE_S = 6.0


@dataclass
class Option:
    label: str
    plan: FloorPlan
    program: RoomProgram


@dataclass
class ResolveResult:
    plan: FloorPlan | None
    program: RoomProgram
    conflicts: list[str] = field(default_factory=list)
    options: list[Option] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.plan is not None


def _solve(program: RoomProgram, plan: FloorPlan, budget: float) -> tuple[FloorPlan | None, list]:
    limit = max(4.0, (budget - 6.0) / 2)
    res = generate_layout(
        program,
        plan.plot,
        plan.meta,
        plan.id,
        time_limit_s=limit,
        seeds=(0, 1),
    )
    return res.plan, (res.report.feedback()[:3] if res.report else [])


def full_resolve(
    plan: FloorPlan,
    program: RoomProgram,
    *,
    budget_s: float | None = None,
    progress: Progress | None = None,
) -> ResolveResult:
    """Re-solve the whole plan; on failure, name the conflicting rules and offer options."""
    started = time.monotonic()
    budget = budget_s or get_settings().full_resolve_s

    def tell(detail: str) -> None:
        if progress:
            progress("layout", detail)

    names = {r.id: r.label for r in program.rooms}
    tell(f"Re-planning the whole house with {len(program.rules)} rule(s) (up to {budget:.0f} s)")
    new_plan, reasons = _solve(program, plan, budget)
    if new_plan is not None:
        return ResolveResult(new_plan, program, seconds=time.monotonic() - started)

    conflicts: list[str] = []
    options: list[Option] = []
    tried = list(enumerate(program.rules))[::-1][:MAX_RULES_TRIED]
    for n, (i, rule) in enumerate(tried, 1):
        what = describe_rule(rule, names)
        tell(f"Checking which rules conflict ({n} of {len(tried)}): without “{what}”")
        kept = [r for k, r in enumerate(program.rules) if k != i]
        trial = program.model_copy(update={"rules": kept})
        alt, _ = _solve(trial, plan, DIAG_SOLVE_S * 2 + 6.0)
        if alt is not None:
            conflicts.append(what)
            if len(options) < 2:
                options.append(Option(f"without “{what}”", alt, trial))
    if not conflicts and program.rules:
        conflicts = [describe_rule(r, names) for r in program.rules]
    return ResolveResult(
        None,
        program,
        conflicts=conflicts,
        options=options,
        reasons=reasons,
        seconds=time.monotonic() - started,
    )
