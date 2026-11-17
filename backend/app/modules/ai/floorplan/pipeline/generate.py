"""Generation orchestrator: confirmed Brief -> validated FloorPlan (or a clear reason).

    feasibility (code) -> room program (LLM) -> layout (code) -> validator (code)
          ^-------------- validator errors, at most FLOORPLAN_MAX_ATTEMPTS -------|

A plan is returned only after it passed the validator. Progress is reported through an
optional callback: progress(stage, detail) with stages
"feasibility", "program", "layout", "checking", "done".
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from app.modules.ai.floorplan.pipeline.brief_parser import missing_required
from app.modules.ai.floorplan.pipeline.feasibility import FeasibilityResult, check_feasibility
from app.modules.ai.floorplan.pipeline.layout import generate_layout
from app.modules.ai.floorplan.pipeline.pool_layouts import Choice, fallback_note, layout_chain
from app.modules.ai.floorplan.pipeline.room_program import build_program
from app.modules.ai.floorplan.pipeline.validator import ValidationReport
from app.modules.ai.floorplan.schemas.brief import Brief
from app.modules.ai.floorplan.schemas.plan import FloorPlan, Meta, Plot
from app.modules.ai.floorplan.schemas.program import RoomProgram
from app.modules.ai.floorplan.settings import get_settings
from app.modules.ai.llm.client import LLMClient

Progress = Callable[[str, str], None]
Status = Literal["ok", "incomplete", "infeasible", "failed"]


@dataclass
class GenerationResult:
    status: Status
    message: str = ""
    plan: FloorPlan | None = None
    program: RoomProgram | None = None
    feasibility: FeasibilityResult | None = None
    report: ValidationReport | None = None
    attempts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    method: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def plot_from_brief(brief: Brief) -> Plot:
    return Plot(width=brief.plot.width_cm, depth=brief.plot.depth_cm, road_side=brief.road_side)


def meta_from_brief(brief: Brief) -> Meta:
    return Meta(
        project=brief.project_name,
        owner=brief.owner_name,
        floor_name="GROUND FLOOR",
        unit_display="ft" if brief.plot.input_unit == "ft" else "cm",
    )


def pool_choices(brief: Brief) -> tuple[list[Choice], list[str]]:
    """Pool layouts to try, best first, and notes for any skipped because the plot is
    too small. Without a pool (or with a pool beside the house) there is one choice."""
    has_pool = any(r.type == "pool" for r in brief.rooms)
    if not has_pool or brief.pool_layout in (None, "side"):
        return [Choice("side")], []
    beds = brief.bedrooms
    if beds is None:
        beds = sum(r.count for r in brief.rooms if r.type in ("bedroom", "master_bedroom"))
    chain, notes = layout_chain(
        brief.pool_layout,
        brief.plot.width_cm,
        brief.plot.depth_cm,
        brief.road_side,
        beds,
        brief.plot.input_unit,
    )
    return chain or [Choice("side")], notes


def generate_plan(
    brief: Brief,
    *,
    llm: LLMClient | None = None,
    progress: Progress | None = None,
    plan_id: str | None = None,
    max_attempts: int | None = None,
    solver_time_s: float | None = None,
) -> GenerationResult:
    s = get_settings()
    max_attempts = max_attempts or s.max_attempts
    solver_time_s = solver_time_s or s.solver_time_s

    def tell(stage: str, detail: str = "") -> None:
        if progress:
            progress(stage, detail)

    missing = missing_required(brief)
    if missing:
        return GenerationResult("incomplete", "Missing: " + ", ".join(missing))

    tell("feasibility", "Checking the rooms fit the plot")
    feas = check_feasibility(brief)
    if not feas.ok:
        return GenerationResult("infeasible", feas.message, feasibility=feas)

    plot, meta = plot_from_brief(brief), meta_from_brief(brief)
    chain, pool_notes = pool_choices(brief)

    attempts: list[str] = []
    warnings: list[str] = []
    report: ValidationReport | None = None
    program: RoomProgram | None = None
    for i, choice in enumerate(chain):
        last = i == len(chain) - 1
        tries = max_attempts if last else min(2, max_attempts)
        tell("program", "Sizing the rooms")
        program, warnings = build_program(brief, llm, pool=choice)
        for attempt in range(1, tries + 1):
            tell("layout", f"Placing rooms (attempt {attempt} of {tries})")
            res = generate_layout(program, plot, meta, plan_id, time_limit_s=solver_time_s)
            attempts += [f"#{attempt} {choice.layout} {a}" for a in res.attempts]
            tell("checking", "Checking the plan")
            if res.ok:
                tell("done", "Plan ready")
                return GenerationResult(
                    "ok",
                    plan=res.plan,
                    program=res.program or program,
                    feasibility=feas,
                    report=res.report,
                    attempts=attempts,
                    warnings=pool_notes + warnings,
                    method=res.method,
                )
            report = res.report
            feedback = (
                report.feedback()
                if report
                else ["NO_LAYOUT: the rooms could not be arranged on the plot"]
            )
            if attempt < tries:
                program, more = build_program(
                    brief, llm, feedback=feedback, previous=program, pool=choice
                )
                warnings += [w for w in more if w not in warnings]
        if not last:
            pool_notes.append(fallback_note(choice.layout, chain[i + 1].layout))
            tell("layout", f"Trying a {chain[i + 1].layout.replace('_', ' ')} pool instead")

    reasons = report.feedback()[:3] if report else ["the rooms could not be arranged on the plot"]
    return GenerationResult(
        "failed",
        "No valid plan could be made for this brief. Main problems: "
        + "; ".join(reasons)
        + ". Try fewer or smaller rooms, or a larger plot.",
        program=program,
        feasibility=feas,
        report=report,
        attempts=attempts,
        warnings=warnings,
    )
