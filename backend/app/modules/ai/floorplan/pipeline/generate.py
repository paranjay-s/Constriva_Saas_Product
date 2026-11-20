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
from app.modules.ai.floorplan.schemas.plan import FloorPlan, Meta, Plot, Setbacks
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


DAYLIGHT_TYPES = (
    "bedroom",
    "master_bedroom",
    "living",
    "family_hall",
    "majlis",
    "kitchen",
    "study",
    "maid_room",
    "driver_room",
)
DAYLIGHT_NOTE = (
    "Not every bedroom, living room and kitchen could get an outside wall on this plot; "
    "see the checks for the rooms without a window."
)


def with_daylight(program: RoomProgram) -> RoomProgram:
    """The program plus a daylight rule for each habitable room that has none yet."""
    from app.modules.ai.floorplan.schemas.rules import Daylight

    have = {r.room for r in program.rules if getattr(r, "kind", "") == "daylight"}
    extra = [
        Daylight(kind="daylight", room=r.id, text="")
        for r in program.rooms
        if r.type in DAYLIGHT_TYPES and r.id not in have
    ]
    if not extra:
        return program
    return program.model_copy(update={"rules": [*program.rules, *extra]})


def plot_from_brief(brief: Brief) -> Plot:
    """The plot to lay out: size on the 5 cm grid, setbacks and the built-up target from
    the settings (or the person's own numbers). See built_up_target."""
    s = get_settings()
    plot = Plot(
        width=round(brief.plot.width_cm / 5) * 5,
        depth=round(brief.plot.depth_cm / 5) * 5,
        road_side=brief.road_side,
    )
    if not s.site_rules:
        return plot
    asked = brief.setbacks
    front = asked.front if asked and asked.front is not None else s.setback_front_m
    side = asked.side if asked and asked.side is not None else s.setback_side_m
    rear = asked.rear if asked and asked.rear is not None else s.setback_rear_m
    plot = plot.model_copy(
        update={
            "setbacks": Setbacks(
                front=round(front * 100),
                rear=round(rear * 100),
                left=round(side * 100),
                right=round(side * 100),
            )
        }
    )
    target, _ = built_up_target(brief, plot)
    return plot.model_copy(update={"built_up_m2": target})


def built_up_target(brief: Brief, plot: Plot) -> tuple[float, list[str]]:
    """Built-up area to aim for (m2) and notes for the person.

    The person's built-up area or share wins. Otherwise the default share of the plot
    (FLOORPLAN_BUILT_UP_SHARE) kept inside FLOORPLAN_BUILT_UP_MIN..MAX. Never more than
    fits inside the setbacks (less the outer half of the exterior walls)."""
    s = get_settings()
    plot_m2 = plot.width * plot.depth / 10_000
    notes: list[str] = []
    if brief.plot.built_up_m2:
        target = brief.plot.built_up_m2
    elif brief.built_up_share:
        target = brief.built_up_share * plot_m2
    else:
        share = min(max(s.built_up_share, s.built_up_min), s.built_up_max)
        target = share * plot_m2
    x0, y0, x1, y1 = plot.buildable()
    fits = max(0.0, (x1 - x0) * (y1 - y0) / 10_000 * 0.98)
    if target > fits:
        notes.append(
            f"The setbacks leave room for about {fits:,.0f} m² of building "
            f"({fits / plot_m2:.0%} of the plot), less than the {target:,.0f} m² aimed for."
        )
        target = fits
    return round(target, 1), notes


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
            # first try with daylight for every habitable room as a hard rule (DBC K.5.4.2)
            trial = with_daylight(program) if attempt == 1 else program
            res = generate_layout(trial, plot, meta, plan_id, time_limit_s=solver_time_s)
            if res.ok and trial is not program:
                res.program = (res.program or trial).model_copy(update={"rules": program.rules})
            elif not res.ok and attempt == 1 and trial is not program:
                res = generate_layout(program, plot, meta, plan_id, time_limit_s=solver_time_s)
                if res.ok:
                    warnings = [*warnings, DAYLIGHT_NOTE]
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
    hint = "Try fewer or smaller rooms, or a larger plot."
    if plot.has_setbacks:
        x0, y0, x1, y1 = plot.buildable()
        sb = plot.setbacks
        hint = (
            f"Inside the setbacks ({sb.front / 100:g} m front, {sb.left / 100:g} m sides, "
            f"{sb.rear / 100:g} m rear) the house can use {(x1 - x0) * (y1 - y0) / 10_000:,.0f} "
            "m² of the plot. Try smaller setbacks (say \"1 m setbacks\" or \"no setbacks\"), "
            "fewer or smaller rooms, or a larger plot."
        )
    return GenerationResult(
        "failed",
        "No valid plan could be made for this brief. Main problems: "
        + "; ".join(reasons)
        + ". "
        + hint,
        program=program,
        feasibility=feas,
        report=report,
        attempts=attempts,
        warnings=warnings,
    )
