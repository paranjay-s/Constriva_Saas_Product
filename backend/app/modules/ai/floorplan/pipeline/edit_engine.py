"""Edit engine: typed edit operations -> a new validated plan, or a clear "not possible".

    result = apply_edit(plan, program, ops)            # ops from the chat (LLM) or the UI
    result = edit_plan(plan, program, "make bedroom 2 bigger", llm)

Rules
  - Rooms not named by an operation are locked: they keep their exact coordinates, and
    their doors, windows and furniture are kept as they were.
  - Layout changes are tried in widening steps, stopping at the first valid plan:
      1. only the named rooms move, using spare open space (garden, leftover gaps)
      2. their direct neighbours may also move (reported in the summary)
      3. everything may move, only when the person allowed it (`allow_reflow`)
  - Every result is checked by the validator. If no step works, the plan is unchanged
    and the result explains why and suggests alternatives.
  - Renames, door moves and new windows do not move any room.
The LLM only turns the message into operations; it never places anything.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.ai.floorplan.geometry import (
    exterior_intervals,
    opening_is_exterior,
    shared_wall_interval,
    span_interval,
    wall_line,
    window_span,
)
from app.modules.ai.floorplan.pipeline.edit_resolve import resolve_edit
from app.modules.ai.floorplan.pipeline.layout.engine import assemble, generate_layout
from app.modules.ai.floorplan.pipeline.layout.openings import (
    CLEAR,
    _door_spans_on_line,
    _subtract,
)
from app.modules.ai.floorplan.pipeline.layout.solver import (
    fill_gaps,
    fill_holes_with_shafts,
    solve_layout,
)
from app.modules.ai.floorplan.pipeline.layout.topology import (
    OPEN_EDGE,
    Topology,
    _break_cycles,
    build_topology,
    door_span_needed,
)
from app.modules.ai.floorplan.pipeline.plan_report import InfoTopic, report
from app.modules.ai.floorplan.pipeline.plan_tools import TOOL_OPS, ToolError, apply_tool, facing
from app.modules.ai.floorplan.pipeline.pool_layouts import LOUNGE_ID as POOL_LOUNGE_ID
from app.modules.ai.floorplan.pipeline.pool_layouts import NAMES as POOL_NAMES
from app.modules.ai.floorplan.pipeline.pool_layouts import (
    apply_layout,
    layout_chain,
    pool_target_m2,
)
from app.modules.ai.floorplan.pipeline.pool_layouts import fallback_note as pool_fallback_note
from app.modules.ai.floorplan.pipeline.requirements import ReqRoom
from app.modules.ai.floorplan.pipeline.validator import ValidationReport, validate
from app.modules.ai.floorplan.prompts import load_prompt
from app.modules.ai.floorplan.rules import (
    DOOR_MIN_WIDTH_CM,
    MIN_ROOM,
    OPEN_AREA_CAP,
    SHAFT_WARN_M2,
    TYPICAL_ROOM_M2,
)
from app.modules.ai.floorplan.schemas.common import DEFAULT_LABEL, ZONE_BY_TYPE
from app.modules.ai.floorplan.schemas.edit_ops import (
    RESOLVE_OPS,
    WHOLE_PLAN_OPS,
    AddRoom,
    AddWindow,
    ChooseOption,
    EditOp,
    MoveDoor,
    MoveRoom,
    RemoveRoom,
    RenameRoom,
    ResizeRoom,
    SetPlot,
    SetPoolLayout,
    SetSetbacks,
    SwapRooms,
    Undo,
)
from app.modules.ai.floorplan.schemas.plan import Door, FloorPlan, Plot, Room, Window
from app.modules.ai.floorplan.schemas.program import Adjacency, ProgramRoom, RoomProgram
from app.modules.ai.floorplan.schemas.rules import describe_rule
from app.modules.ai.floorplan.units import fmt_length, fmt_size
from app.modules.ai.llm.client import LLMClient, LLMError

logger = logging.getLogger("construtiva.ai.floorplan")

SIDES = ("north", "south", "east", "west")
LAYOUT_OPS = (ResizeRoom, MoveRoom, SwapRooms, AddRoom, RemoveRoom)
SPARE_TYPES = ("garden",)  # open space that step 1 may take from
SIZE_STEP_CM = 15  # a requested side is met within one planning-grid step
OTHER_SIDE_SLACK = 0.10  # the side not mentioned stays within 10 % of its size
RESIZE_STEP_CM = 60  # "bigger"/"smaller" with no number: about 2 ft on the longer side
MIN_WINDOW_CM = 50  # baths, stores, utility
MIN_WINDOW_HABITABLE_CM = 90  # anything smaller is not a useful window in a living space
MAX_WINDOW_CM = 240
GIVE_MIN = 0.7  # a neighbour that makes space keeps at least 70 % of its area
TAKE_MAX = 1.8  # a neighbour that takes over a removed room's space grows at most 80 %
PARENT_PREFERENCE = ("lobby", "passage", "living", "family_hall", "foyer", "dining")
NEVER_PARENT = (
    "bath",
    "toilet",
    "store",
    "dress",
    "shaft",
    "garden",
    "parking",
    "balcony",
    "pool",
)
ANCHOR_SIDES = {
    "north": ["north"],
    "south": ["south"],
    "east": ["east"],
    "west": ["west"],
    "north-east": ["north", "east"],
    "north-west": ["north", "west"],
    "south-east": ["south", "east"],
    "south-west": ["south", "west"],
}

Status = Literal["ok", "no_change", "impossible", "needs_clarification", "failed", "info"]


class EditInterpretation(BaseModel):
    """What the LLM returns for one chat message."""

    ops: list[EditOp] = Field(default_factory=list)
    question: str | None = Field(
        default=None, description="Ask this instead of guessing when the request is unclear"
    )
    unsupported: list[str] = Field(default_factory=list)
    allow_reflow: bool = Field(
        default=False, description="True only if the person said other rooms may move"
    )
    info: InfoTopic | None = Field(
        default=None,
        description="A question about the plan (areas, schedule, openings, orientation, help), "
        "answered by code; use with no ops",
    )


@dataclass
class EditResult:
    status: Status
    plan: FloorPlan  # the new plan when ok, otherwise the unchanged original
    program: RoomProgram
    summary: list[str] = field(default_factory=list)
    message: str = ""
    alternatives: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ops: list[EditOp] = field(default_factory=list)
    moved: list[str] = field(default_factory=list)  # ids of rooms whose geometry changed
    undo: Undo | None = None  # the person asked to go back; the service restores history
    options: list = field(default_factory=list)  # resolve.Option: layouts offered on conflict
    resolved: bool = False  # the whole plan was laid out again
    choose: int | None = None  # the person picked an offered option (service applies it)

    @property
    def ok(self) -> bool:
        return self.status == "ok"


class EditError(Exception):
    """An operation that cannot be applied at all (unknown id, too small, ...)."""

    def __init__(self, message: str, alternatives: list[str] | None = None) -> None:
        super().__init__(message)
        self.alternatives = alternatives or []


class NoFitError(EditError):
    """A valid request that does not fit the current layout: the plan is re-solved."""


# ======================================================================= the LLM side


def describe_plan(plan: FloorPlan) -> dict:
    """What the LLM sees: ids, names, sizes and rough positions. No coordinates."""
    unit = plan.meta.unit_display
    names = {r.id: r.label for r in plan.rooms}
    return {
        "unit": unit,
        "plot": fmt_size(plan.plot.width, plan.plot.depth, unit),
        "road_side": plan.plot.road_side,
        "facing": facing(plan),
        "rooms": [
            {
                "id": r.id,
                "type": r.type,
                "label": r.label,
                "size": fmt_size(r.w, r.h, unit),
                "width_cm": r.w,
                "depth_cm": r.h,
                "position": _where(r, plan.plot),
            }
            for r in plan.rooms
            if r.type != "shaft"
        ],
        "doors": [
            {
                "id": d.id,
                "between": [names[d.from_room] if d.from_room else "OUTSIDE", names[d.to_room]],
                "room": d.to_room,
                "wall": d.wall,
                "width": fmt_length(d.width, unit),
            }
            for d in plan.doors
        ],
        "windows": [
            {"id": w.id, "room": w.room, "wall": w.wall, "width": fmt_length(w.width, unit)}
            for w in plan.windows
        ],
    }


def interpret_edit(
    message: str, plan: FloorPlan, llm: LLMClient, program: RoomProgram | None = None
) -> EditInterpretation:
    described = describe_plan(plan)
    if program is not None and program.rules:
        names = {r.id: r.label for r in plan.rooms}
        described["rules"] = [
            f"{i}. {describe_rule(r, names)}" for i, r in enumerate(program.rules, 1)
        ]
    payload = {"plan": described, "request": message.strip()}
    return llm.structured(
        system=load_prompt("edit_ops"),
        user=json.dumps(payload, ensure_ascii=False),
        schema=EditInterpretation,
        task="edit_ops",
    )


def edit_plan(
    plan: FloorPlan,
    program: RoomProgram | None,
    message: str,
    llm: LLMClient | None,
    *,
    allow_reflow: bool = True,
    time_limit_s: float = 5.0,
    progress=None,
) -> EditResult:
    program = program or program_from_plan(plan)
    if llm is None:
        return EditResult(
            "failed", plan, program, message="Chat edits need the AI, which is not configured."
        )
    try:
        interp = interpret_edit(message, plan, llm, program)
    except LLMError as e:
        logger.warning("edit: LLM failed: %s", e)
        return EditResult(
            "failed",
            plan,
            program,
            message="The request could not be understood just now. Please try again.",
        )
    warnings = (
        ["Not part of the floor plan, so not changed: " + "; ".join(interp.unsupported)]
        if interp.unsupported
        else []
    )
    undo = next((o for o in interp.ops if isinstance(o, Undo)), None)
    if undo is not None:
        return EditResult("no_change", plan, program, undo=undo, warnings=warnings)
    choose = next((o for o in interp.ops if isinstance(o, ChooseOption)), None)
    if choose is not None:
        return EditResult("no_change", plan, program, choose=choose.n, warnings=warnings)
    if not interp.ops and interp.info and not interp.question:
        return EditResult("info", plan, program, message=report(plan, interp.info))
    if not interp.ops:
        status: Status = "needs_clarification" if interp.question else "no_change"
        msg = interp.question or "Nothing to change was found in that request."
        if interp.unsupported and not interp.question:
            msg = warnings[0] + "."
        return EditResult(status, plan, program, message=msg, warnings=warnings)
    res = apply_edit(
        plan,
        program,
        interp.ops,
        allow_reflow=allow_reflow or interp.allow_reflow,
        time_limit_s=time_limit_s,
        progress=progress,
    )
    res.warnings = warnings + res.warnings
    return res


# ===================================================================== applying ops


def apply_edit(
    plan: FloorPlan,
    program: RoomProgram | None,
    ops: list[EditOp],
    *,
    allow_reflow: bool = True,
    time_limit_s: float = 5.0,
    seed: int = 0,
    progress=None,
) -> EditResult:
    program = program or program_from_plan(plan)
    if not ops:
        return EditResult("no_change", plan, program, message="No changes were requested.")
    ops = [_explicit_resize(op, plan) for op in ops]
    if any(isinstance(o, RESOLVE_OPS) for o in ops):
        return _with_simple_ops(
            resolve_edit(
                plan,
                program,
                [o for o in ops if isinstance(o, RESOLVE_OPS + LAYOUT_OPS)],
                progress=progress,
            ),
            [o for o in ops if not isinstance(o, RESOLVE_OPS + LAYOUT_OPS)],
        )
    try:
        if any(isinstance(o, SetSetbacks) for o in ops):
            if len(ops) > 1:
                raise EditError("Change the setbacks on their own, then make other changes.")
            return _set_setbacks(plan, program, ops[0], time_limit_s)
        if any(isinstance(o, SetPlot) for o in ops):
            if len(ops) > 1:
                raise EditError("Change the plot size on its own, then make other changes.")
            return _set_plot(plan, program, ops[0], time_limit_s)
        if any(isinstance(o, SetPoolLayout) for o in ops):
            if len(ops) > 1:
                raise EditError("Move the pool on its own, then make other changes.")
            return _set_pool_layout(plan, program, ops[0], time_limit_s)
        if any(isinstance(o, Undo) for o in ops):
            raise EditError("Undo on its own, then make other changes.")
        if any(isinstance(o, WHOLE_PLAN_OPS) for o in ops):
            if len(ops) > 1:
                raise EditError(
                    "Turn or mirror the house on its own, then make other changes "
                    "(wall directions change when the house turns)."
                )
            return _whole_plan(plan, program, ops[0])
        layout_ops = [o for o in ops if isinstance(o, LAYOUT_OPS)]
        other_ops = [o for o in ops if not isinstance(o, LAYOUT_OPS)]
        new_plan, new_program, notes, moved = plan, program, [], []
        if layout_ops:
            try:
                new_plan, new_program, notes, moved = _relayout(
                    plan, program, layout_ops, allow_reflow, time_limit_s, seed
                )
            except EditError as full:
                best = _as_large_as_fits(
                    plan, program, layout_ops, allow_reflow, time_limit_s, seed
                )
                if best is None:
                    raise full from None
                new_plan, new_program, notes, moved = best
        for op in other_ops:
            if isinstance(op, TOOL_OPS):
                try:
                    new_plan, new_program, note = apply_tool(new_plan, new_program, op)
                except ToolError as e:
                    raise EditError(str(e), e.alternatives) from None
            else:
                new_plan, new_program, note = _apply_simple(new_plan, new_program, op)
            notes.append(note)
    except EditError as e:
        layout_ops = [o for o in ops if isinstance(o, LAYOUT_OPS)]
        if layout_ops and isinstance(e, NoFitError):
            # it does not fit the current layout: lay the whole plan out again with the
            # request as rules (never "not possible" for a spatial request)
            res = resolve_edit(
                plan,
                program,
                layout_ops,
                why=f"That did not fit the current layout ({e}), so I re-planned the house",
                progress=progress,
            )
            return _with_simple_ops(res, [o for o in ops if not isinstance(o, LAYOUT_OPS)])
        return EditResult(
            "impossible", plan, program, message=str(e), alternatives=e.alternatives, ops=ops
        )
    rep = validate(new_plan, new_program)
    if not rep.ok:  # simple ops are validated here; layout ops were validated per step
        return EditResult(
            "impossible",
            plan,
            program,
            message="That change would break the plan: " + "; ".join(rep.feedback()[:2]),
            alternatives=_generic_alternatives(ops, allow_reflow),
            ops=ops,
        )
    summary = summarize(plan, new_plan, notes)
    return EditResult("ok", new_plan, new_program, summary=summary, ops=ops, moved=moved)


def _with_simple_ops(res: EditResult, ops: list[EditOp]) -> EditResult:
    """Renames, doors, windows and the like, applied on top of a re-solved plan."""
    if not res.ok or not ops:
        return res
    plan, program, notes = res.plan, res.program, []
    for op in ops:
        try:
            if isinstance(op, TOOL_OPS):
                plan, program, note = apply_tool(plan, program, op)
            else:
                plan, program, note = _apply_simple(plan, program, op)
            notes.append(note)
        except (ToolError, EditError) as e:
            res.warnings.append(str(e))
    res.plan, res.program = plan, program
    res.summary += notes
    return res


def _whole_plan(plan: FloorPlan, program: RoomProgram, op: EditOp) -> EditResult:
    """Facing / rotate / mirror: an exact transform, so only one summary line."""
    try:
        new_plan, new_program, note = apply_tool(plan, program, op)
    except ToolError as e:
        return EditResult(
            "impossible", plan, program, message=str(e), alternatives=e.alternatives, ops=[op]
        )
    rep = validate(new_plan, new_program)
    if not rep.ok:  # a transform keeps every relation, so this should not happen
        logger.error("whole-plan edit broke the plan: %s", rep.feedback()[:3])
        return EditResult(
            "failed", plan, program, message="That change could not be checked; nothing changed."
        )
    return EditResult(
        "ok",
        new_plan,
        new_program,
        summary=[note],
        ops=[op],
        moved=[r.id for r in new_plan.rooms],
    )


# ------------------------------------------------------------------ layout changes


@dataclass
class _Work:
    rooms: dict[str, Room]  # current geometry of rooms that stay
    program: dict[str, ProgramRoom]
    adjacency: list[Adjacency]
    named: set[str] = field(default_factory=set)  # rooms the ops talk about
    forced: dict[str, Room] = field(default_factory=dict)  # exact new rects (swap)
    anchors: dict[str, list[str]] = field(default_factory=dict)
    adjoin: list[tuple[str, str]] = field(default_factory=list)
    sizes: dict[str, tuple[tuple[int, int] | None, tuple[int, int] | None, bool]] = field(
        default_factory=dict
    )
    reparent: set[str] = field(default_factory=set)  # rooms whose door must be re-chosen
    parent_hint: dict[str, str] = field(default_factory=dict)  # new room -> room it opens into
    removed_area: dict[str, Room] = field(default_factory=dict)
    absorb: set[str] = field(default_factory=set)  # neighbours that take a removed room's space
    givers: set[str] = field(default_factory=set)  # rooms (and their neighbours) freed in step 2
    notes: list[str] = field(default_factory=list)


def _relayout(
    plan: FloorPlan,
    program: RoomProgram,
    ops: list[EditOp],
    allow_reflow: bool,
    time_limit_s: float,
    seed: int,
) -> tuple[FloorPlan, RoomProgram, list[str], list[str]]:
    _check_program_matches(plan, program)
    work = _Work(
        rooms={r.id: r for r in plan.rooms if r.type != "shaft"},
        program={p.id: p for p in program.rooms},
        adjacency=list(program.adjacency),
    )
    for op in ops:
        _stage(op, plan, work)

    new_program = RoomProgram(
        rooms=list(work.program.values()),
        adjacency=[a for a in work.adjacency if a.a in work.program and a.b in work.program],
        entrance_side=program.entrance_side,
    )
    topo = _edit_topology(plan, new_program, work)
    for rid in work.program:
        if rid not in work.rooms and topo.parent.get(rid):
            work.givers.add(topo.parent[rid])  # a new room needs space next to its door room
    named = {n for n in work.named if n in work.program}
    old_geom = {r.id: r for r in plan.rooms}
    user_locked = {r.id for r in plan.rooms if r.locked}

    steps: list[tuple[str, set[str]]] = []
    spare = {r for r in work.rooms if work.rooms[r].type in SPARE_TYPES}
    absorb: set[str] = set()
    for gone in work.removed_area.values():
        absorb |= _neighbours(gone, work.rooms.values())
    work.absorb = absorb
    steps.append(("named", named | spare | absorb))
    near = set(absorb)
    for rid in named:
        geom = work.forced.get(rid) or old_geom.get(rid) or work.removed_area.get(rid)
        if geom is not None:
            near |= _neighbours(geom, work.rooms.values())
    for _a, b in work.adjoin:
        if b in work.rooms:
            work.givers.add(b)
    for g in work.givers:
        if g in work.rooms:
            near |= {g} | _neighbours(work.rooms[g], work.rooms.values())
    steps.append(("neighbours", named | spare | near))
    if allow_reflow:
        steps.append(("all", set(work.program)))

    last: ValidationReport | None = None
    fallback: FloorPlan | None = None
    old_shafts = _shaft_area(plan)
    tried: set[frozenset[str]] = set()
    for step, free in steps:
        free = (free - user_locked) & set(work.program)
        if frozenset(free) in tried:
            continue
        tried.add(frozenset(free))
        result = _solve_step(plan, new_program, topo, work, free, time_limit_s, seed)
        if result is None:
            continue
        cand, rep = result
        if rep.ok and _shaft_area(cand) - old_shafts > SHAFT_WARN_M2 and step != steps[-1][0]:
            fallback = fallback or cand
            continue
        if rep.ok:
            moved = [
                r.id
                for r in cand.rooms
                if r.type != "shaft" and (r.id not in old_geom or _rect(old_geom[r.id]) != _rect(r))
            ]
            notes = list(work.notes)
            if step == "all":
                notes.append("Other rooms were re-arranged to make this fit.")
            if _shaft_area(cand) - old_shafts > SHAFT_WARN_M2:
                notes.append("Part of the freed space is left open to the sky (OPEN).")
            others = sorted(set(moved) - named - set(work.forced))
            if others:
                labels = ", ".join(_name(cand, i) for i in others)
                notes.append(f"To make space, these also changed: {labels}.")
            final_program = _program_after(new_program, cand, moved)
            return cand, final_program, notes, moved
        last = rep

    if fallback is not None:  # only plans that leave part of the space open worked
        moved = [
            r.id
            for r in fallback.rooms
            if r.type != "shaft" and (r.id not in old_geom or _rect(old_geom[r.id]) != _rect(r))
        ]
        notes = [*work.notes, "Part of the freed space is left open to the sky (OPEN)."]
        return fallback, _program_after(new_program, fallback, moved), notes, moved

    reason = "; ".join(last.feedback()[:2]) if last else "the rooms could not be arranged that way"
    raise NoFitError(
        f"That change does not fit without breaking the plan ({reason}).",
        _layout_alternatives(ops, plan, allow_reflow),
    )


def _explicit_resize(op: EditOp, plan: FloorPlan) -> EditOp:
    """ "Make it bigger/smaller" without numbers -> a real size: the longer side +-60 cm."""
    if not isinstance(op, ResizeRoom) or op.width_cm or op.height_cm:
        return op
    if op.id not in {r.id for r in plan.rooms}:
        return op
    r = plan.room(op.id)
    step = -RESIZE_STEP_CM if op.change == "smaller" else RESIZE_STEP_CM
    if r.w >= r.h:
        return op.model_copy(update={"width_cm": r.w + step})
    return op.model_copy(update={"height_cm": r.h + step})


BEST_EFFORT_STEPS = (0.75, 0.5, 0.25)  # share of a resize tried when the full one fails


def _as_large_as_fits(
    plan: FloorPlan,
    program: RoomProgram,
    ops: list[EditOp],
    allow_reflow: bool,
    time_limit_s: float,
    seed: int,
):
    """A resize that does not fully fit is done as far as it fits (largest step first)."""
    if len(ops) != 1 or not isinstance(ops[0], ResizeRoom):
        return None
    op = ops[0]
    if op.id not in {r.id for r in plan.rooms}:
        return None
    r = plan.room(op.id)
    grows = (op.width_cm or 0) > r.w or (op.height_cm or 0) > r.h
    too_small = min(op.width_cm or r.w, op.height_cm or r.h) < MIN_ROOM[r.type].short_side_cm
    if not grows or too_small:
        return None  # only enlarging is done "as far as it fits"
    unit = plan.meta.unit_display
    asked = fmt_size(op.width_cm or r.w, op.height_cm or r.h, unit)
    for share in BEST_EFFORT_STEPS:
        w = round(r.w + (op.width_cm - r.w) * share) if op.width_cm else None
        h = round(r.h + (op.height_cm - r.h) * share) if op.height_cm else None
        if (w is None or abs(w - r.w) < SIZE_STEP_CM) and (
            h is None or abs(h - r.h) < SIZE_STEP_CM
        ):
            break  # no meaningful change left
        try:
            new_plan, new_program, notes, moved = _relayout(
                plan,
                program,
                [ResizeRoom(op="resize_room", id=op.id, width_cm=w, height_cm=h)],
                allow_reflow,
                time_limit_s,
                seed,
            )
        except EditError:
            continue
        got = new_plan.room(op.id)
        notes = [n for n in notes if not n.startswith("Resized ")]
        notes.insert(
            0,
            f"{r.label} could not be made {asked} without breaking the plan; it was made as "
            f"large as fits: {fmt_size(got.w, got.h, unit)}.",
        )
        return new_plan, new_program, notes, moved
    return None


def _stage(op: EditOp, plan: FloorPlan, work: _Work) -> None:
    unit = plan.meta.unit_display
    if isinstance(op, ResizeRoom):
        room = _room(work, op.id)
        w = op.width_cm or room.w
        h = op.height_cm or room.h
        rule = MIN_ROOM[room.type]
        if min(w, h) < rule.short_side_cm or w * h / 10_000 < rule.area_m2:
            raise EditError(
                f"{room.label} cannot be {fmt_size(w, h, unit)}: the minimum for this room is "
                f"{fmt_length(rule.short_side_cm, unit)} on its short side and "
                f"{rule.area_m2:g} m2.",
                [f"Keep {room.label} at least {fmt_length(rule.short_side_cm, unit)} wide."],
            )
        pw, pd = plan.plot.width, plan.plot.depth
        if not ((w <= pw and h <= pd) or (h <= pw and w <= pd)):
            raise EditError(f"{fmt_size(w, h, unit)} is larger than the plot.")
        work.named.add(room.id)
        # the side asked for within one grid step; the other side may give a little
        work.sizes[room.id] = (
            _span(op.width_cm, room.w),
            _span(op.height_cm, room.h),
            bool(op.width_cm and op.height_cm),
        )
        _set_target(work, room.id, w * h / 10_000)
        work.notes.append(f"Resized {room.label} as asked.")
    elif isinstance(op, MoveRoom):
        room = _room(work, op.id)
        if not op.anchor and not op.next_to:
            raise EditError(f"Where should {room.label} go? Say a side or a room to be next to.")
        work.named.add(room.id)
        if op.anchor:
            work.anchors[room.id] = ANCHOR_SIDES[op.anchor]
        if op.next_to:
            other = _room(work, op.next_to)
            work.adjoin.append((room.id, other.id))
        work.reparent.add(room.id)
    elif isinstance(op, SwapRooms):
        a, b = _room(work, op.a), _room(work, op.b)
        if a.id == b.id:
            raise EditError("Choose two different rooms to swap.")
        for x, spot in ((a, b), (b, a)):
            rule = MIN_ROOM[x.type]
            if min(spot.w, spot.h) < rule.short_side_cm or spot.area_m2 < rule.area_m2:
                raise EditError(
                    f"{x.label} would not fit where {spot.label} is "
                    f"({fmt_size(spot.w, spot.h, unit)} is below its minimum size)."
                )
        beds = ("bedroom", "master_bedroom")
        if a.type in beds and b.type in beds:
            for pid, pr in list(work.program.items()):
                if pr.attached_to in (a.id, b.id):
                    owner = b.id if pr.attached_to == a.id else a.id
                    work.program[pid] = pr.model_copy(update={"attached_to": owner})
                    work.reparent.add(pid)
                    work.notes.append(
                        f"{pr.label} stays in place and now belongs to {work.rooms[owner].label}."
                    )
        work.forced[a.id] = a.model_copy(update={"x": b.x, "y": b.y, "w": b.w, "h": b.h})
        work.forced[b.id] = b.model_copy(update={"x": a.x, "y": a.y, "w": a.w, "h": a.h})
        _set_target(work, a.id, b.area_m2)
        _set_target(work, b.id, a.area_m2)
        work.named |= {a.id, b.id}
        work.reparent |= {a.id, b.id}
        work.notes.append(f"Swapped {a.label} and {b.label}.")
    elif isinstance(op, AddRoom):
        rid = _new_id(work, op.type)
        label = _clean_label(op.label) or DEFAULT_LABEL[op.type]
        target = max(_min_area(op.type), op.target_area_m2 or TYPICAL_ROOM_M2[op.type])
        attached = None
        if op.next_to:
            other = _room(work, op.next_to)
            if op.type in ("bath", "toilet", "dress") and other.type in (
                "bedroom",
                "master_bedroom",
            ):
                attached = other.id
                work.givers.add(other.id)  # a bedroom may give up space for its own bath
            else:
                work.adjoin.append((rid, other.id))
                if other.type not in NEVER_PARENT and op.type not in OPEN_EDGE:
                    work.parent_hint[rid] = other.id
        work.program[rid] = ProgramRoom(
            id=rid,
            type=op.type,
            label=label,
            target_area_m2=round(target, 2),
            zone=ZONE_BY_TYPE[op.type],
            attached_to=attached,
        )
        work.named.add(rid)
        work.reparent.add(rid)
        where = f" next to {work.rooms[op.next_to].label}" if op.next_to else ""
        work.notes.append(f"Added {label}{where}.")
    elif isinstance(op, RemoveRoom):
        room = _room(work, op.id)
        gone = [room.id] + [p.id for p in work.program.values() if p.attached_to == room.id]
        for gid in gone:
            if gid in work.rooms:
                work.removed_area[gid] = work.rooms.pop(gid)
            work.program.pop(gid, None)
            work.named.discard(gid)
        extra = [plan.room(g).label for g in gone[1:] if g in {r.id for r in plan.rooms}]
        tail = f" (and its attached {', '.join(extra)})" if extra else ""
        work.notes.append(f"Removed {room.label}{tail}.")


def _solve_step(
    plan: FloorPlan,
    program: RoomProgram,
    topo: Topology,
    work: _Work,
    free: set[str],
    time_limit_s: float,
    seed: int,
) -> tuple[FloorPlan, ValidationReport] | None:
    fixed: dict[str, Room] = {}
    for rid in work.program:
        if rid in work.forced:
            fixed[rid] = work.forced[rid]
        elif rid in work.rooms and rid not in free:
            fixed[rid] = work.rooms[rid]
    # Rooms that are free but were not named only make or take space: they get a range
    # instead of a target, and afterwards are judged on minimum sizes only.
    targets: dict[str, float] = {}
    bounds: dict[str, tuple[float, float]] = {}
    rooms_out = []
    plot_m2 = plan.plot.width * plan.plot.depth / 10_000
    for p in program.rooms:
        t = p.target_area_m2
        if p.id in free and p.id in work.rooms and p.id not in work.named:
            cur = work.rooms[p.id].area_m2
            low = max(_min_area(p.type), cur * GIVE_MIN)
            if p.type in SPARE_TYPES:
                t, bounds[p.id] = cur, (_min_area(p.type), plot_m2)
            elif p.type in OPEN_AREA_CAP:
                bounds[p.id] = (low, p.target_area_m2 * OPEN_AREA_CAP[p.type])
            elif p.id in work.absorb:
                t, bounds[p.id] = cur * 1.3, (max(low, cur * 0.95), cur * TAKE_MAX)
            else:
                t, bounds[p.id] = cur, (low, cur * 1.2)
        targets[p.id] = t
        rooms_out.append(p.model_copy(update={"target_area_m2": round(t, 2)}))
    step_program = program.model_copy(update={"rooms": rooms_out})
    rooms = solve_layout(
        step_program,
        plan.plot,
        topo,
        fixed=fixed,
        time_limit_s=time_limit_s,
        seed=seed,
        workers=8,
        anchors={k: v for k, v in work.anchors.items() if k not in fixed},
        adjoin=[(a, b) for a, b in work.adjoin if a in work.program and b in work.program],
        sizes=work.sizes,
        area_bounds=bounds,
    )
    if rooms is None:
        return None
    rooms = fill_gaps(rooms, plan.plot, targets, keep=set(work.sizes))
    rooms = fill_holes_with_shafts(rooms, plan.plot)
    cand = assemble(rooms, topo, plan.plot, plan.meta, plan.id, step_program)
    cand = _keep_locked_openings(plan, cand, set(fixed) - set(work.forced))
    actual = {r.id: r.area_m2 for r in cand.rooms}
    check_program = step_program.model_copy(
        update={
            "rooms": [
                p.model_copy(update={"target_area_m2": round(actual[p.id], 2)})
                if p.id in bounds and p.id in actual
                else p
                for p in step_program.rooms
            ]
        }
    )
    return cand, validate(cand, check_program)


def _edit_topology(plan: FloorPlan, program: RoomProgram, work: _Work) -> Topology:
    """Keep today's door tree; re-choose doors only where an op requires it."""
    current = topology_from_plan(plan)
    desired = build_topology(program)
    ids = {p.id for p in program.rooms}
    root = current.root if current.root in ids else desired.root
    parent: dict[str, str | None] = {}
    geom = {**work.rooms, **work.forced}
    for p in program.rooms:
        rid = p.id
        if rid == root:
            parent[rid] = None
            continue
        old = current.parent.get(rid)
        keep = (
            old is not None
            and old in ids
            and rid not in work.reparent
            and (
                old not in work.reparent
                or rid not in geom
                or _shares_door_wall(geom, rid, old, p.type)
            )
        )
        if p.attached_to and p.attached_to in ids:
            parent[rid] = p.attached_to
        elif rid in work.parent_hint and work.parent_hint[rid] in ids:
            parent[rid] = work.parent_hint[rid]
        elif keep:
            parent[rid] = old
        elif rid in geom and rid in work.forced:
            parent[rid] = _choose_parent(rid, p.type, geom, desired.parent.get(rid), root)
        else:
            parent[rid] = desired.parent.get(rid)
        if parent[rid] is None and p.type not in OPEN_EDGE:
            parent[rid] = desired.parent.get(rid) or root
    _break_cycles(parent, root)
    return Topology(root=root, parent=parent)


def topology_from_plan(plan: FloorPlan) -> Topology:
    """The door tree of an existing plan, rooted at the room with the entrance door."""
    entrance = next((d for d in plan.doors if d.from_room is None), None)
    root = entrance.to_room if entrance else plan.rooms[0].id
    links: dict[str, set[str]] = {r.id: set() for r in plan.rooms}
    for d in plan.doors:
        if d.from_room:
            links[d.from_room].add(d.to_room)
            links[d.to_room].add(d.from_room)
    parent: dict[str, str | None] = {r.id: None for r in plan.rooms}
    seen, queue = {root}, [root]
    while queue:
        node = queue.pop(0)
        for nxt in sorted(links[node]):
            if nxt not in seen:
                seen.add(nxt)
                parent[nxt] = node
                queue.append(nxt)
    return Topology(root=root, parent=parent)


def _choose_parent(
    rid: str, rtype: str, geom: dict[str, Room], desired: str | None, root: str
) -> str | None:
    need = door_span_needed(rtype)
    cands = [
        o
        for o in geom.values()
        if o.id != rid and o.type not in NEVER_PARENT and _shared_len(geom[rid], o) >= need
    ]
    if not cands:
        return desired
    ids = {c.id for c in cands}
    if desired in ids:
        return desired
    for t in PARENT_PREFERENCE:
        for c in cands:
            if c.type == t:
                return c.id
    if root in ids:
        return root
    private = ("bedroom", "master_bedroom", "kitchen", "maid_room", "study")
    open_cands = [c for c in cands if c.type not in private]
    return (open_cands or cands)[0].id


def _keep_locked_openings(old: FloorPlan, cand: FloorPlan, locked: set[str]) -> FloorPlan:
    """Rooms that did not move keep their exact doors, windows and furniture.

    `locked` rooms could not move; any other room that ended up with the same rectangle
    counts as unmoved too. An old door is kept when both its rooms are unmoved and the
    new layout still connects them (or still enters that room from outside). Furniture
    is kept for an unmoved room whose doors are all unchanged.
    """
    room_ids = {r.id for r in cand.rooms}
    before = {r.id: r for r in old.rooms}
    unmoved = set(locked) | {
        r.id for r in cand.rooms if r.id in before and _rect(before[r.id]) == _rect(r)
    }
    new_pairs = {frozenset((d.from_room, d.to_room)) for d in cand.doors}

    def keep_door(d: Door) -> bool:
        return (
            d.to_room in unmoved
            and (d.from_room is None or d.from_room in unmoved)
            and frozenset((d.from_room, d.to_room)) in new_pairs
        )

    kept_doors = [d for d in old.doors if keep_door(d)]
    pairs = {frozenset((d.from_room, d.to_room)) for d in kept_doors}
    new_doors = [d for d in cand.doors if frozenset((d.from_room, d.to_room)) not in pairs]

    draft = cand.model_copy(update={"doors": kept_doors + new_doors})
    kept_windows: list[Window] = []
    with_windows: set[str] = set()
    for w in old.windows:
        if w.room in unmoved and w.room in room_ids:
            if opening_is_exterior(draft, window_span(draft, w)):
                kept_windows.append(w)
                with_windows.add(w.room)
    new_windows = [w for w in cand.windows if w.room not in with_windows]

    def door_key(plan_doors, rid):
        return {
            (d.id, d.wall, d.offset, d.width, d.swing)
            for d in plan_doors
            if rid in (d.to_room, d.from_room)
        }

    used = {o.id for o in (*kept_doors, *kept_windows, *old.fixtures)} | room_ids
    doors = kept_doors + [_fresh(d, "d", used) for d in new_doors]
    windows = kept_windows + [_fresh(w, "w", used) for w in new_windows]
    # furniture stays only where the room's final doors are exactly the old ones
    same_doors = {rid for rid in unmoved if door_key(old.doors, rid) == door_key(doors, rid)}
    kept_fixtures = [f for f in old.fixtures if f.room in same_doors and f.room in room_ids]
    used = {o.id for o in (*doors, *windows, *kept_fixtures)} | room_ids
    fixtures = kept_fixtures + [
        _fresh(f, "f", used) for f in cand.fixtures if f.room not in same_doors
    ]
    # last guard: drop any kept window the merged plan no longer accepts
    merged = cand.model_copy(update={"doors": doors, "windows": windows})
    bad = {
        i for issue in validate(merged).errors if issue.code.startswith("WINDOW") for i in issue.ids
    }
    windows = [w for w in windows if w.id not in bad]
    locked_flags = {r.id: r.locked for r in old.rooms}
    rooms = [r.model_copy(update={"locked": locked_flags.get(r.id, False)}) for r in cand.rooms]
    data = cand.model_copy(
        update={"rooms": rooms, "doors": doors, "windows": windows, "fixtures": fixtures}
    ).model_dump(by_alias=True)
    return FloorPlan.model_validate(data)


def _fresh(obj, prefix: str, used: set[str]):
    if obj.id not in used:
        used.add(obj.id)
        return obj
    n = 1
    while f"{prefix}{n}" in used:
        n += 1
    used.add(f"{prefix}{n}")
    return obj.model_copy(update={"id": f"{prefix}{n}"})


def _program_after(program: RoomProgram, plan: FloorPlan, moved: list[str]) -> RoomProgram:
    """Targets of changed rooms follow their new size so later checks stay consistent."""
    rooms = []
    by_id = {r.id: r for r in plan.rooms}
    for p in program.rooms:
        if p.id in moved and p.id in by_id:
            p = p.model_copy(update={"target_area_m2": round(by_id[p.id].area_m2, 2)})
        rooms.append(p)
    return program.model_copy(update={"rooms": rooms})


def _set_plot(
    plan: FloorPlan, program: RoomProgram, op: SetPlot, time_limit_s: float
) -> EditResult:
    unit = plan.meta.unit_display
    plot = Plot(width=op.width_cm, depth=op.depth_cm, road_side=plan.plot.road_side)
    res = generate_layout(program, plot, plan.meta, plan.id, time_limit_s=max(time_limit_s, 6))
    if not res.ok:
        why = "; ".join(res.report.feedback()[:2]) if res.report else "the rooms do not fit"
        return EditResult(
            "impossible",
            plan,
            program,
            message=f"The rooms do not fit on a {fmt_size(op.width_cm, op.depth_cm, unit)} "
            f"plot ({why}).",
            alternatives=["Use a larger plot.", "Remove a room first."],
            ops=[op],
        )
    new_program = res.program or program
    note = (
        f"Plot changed from {fmt_size(plan.plot.width, plan.plot.depth, unit)} to "
        f"{fmt_size(op.width_cm, op.depth_cm, unit)}; the whole layout was re-planned."
    )
    return EditResult(
        "ok",
        res.plan,
        new_program,
        summary=[note],
        ops=[op],
        moved=[r.id for r in res.plan.rooms],
    )


def _set_setbacks(
    plan: FloorPlan, program: RoomProgram, op: SetSetbacks, time_limit_s: float
) -> EditResult:
    """New setbacks (metres; a side not given keeps its value): the layout is re-planned."""
    from app.modules.ai.floorplan.schemas.plan import Setbacks

    old = plan.plot.setbacks
    side = None if op.side is None else round(op.side * 100)
    new = Setbacks(
        front=old.front if op.front is None else round(op.front * 100),
        rear=old.rear if op.rear is None else round(op.rear * 100),
        left=old.left if side is None else side,
        right=old.right if side is None else side,
    )
    if new == old:
        return EditResult(
            "no_change", plan, program, message="The plan already has those setbacks."
        )
    plot = plan.plot.model_copy(update={"setbacks": new})
    res = generate_layout(program, plot, plan.meta, plan.id, time_limit_s=max(time_limit_s, 6))
    words = (
        f"{new.front / 100:g} m front, {new.left / 100:g} m sides, {new.rear / 100:g} m rear"
        if new.front or new.left or new.right or new.rear
        else "no setbacks"
    )
    if not res.ok:
        why = "; ".join(res.report.feedback()[:2]) if res.report else "the rooms do not fit"
        return EditResult(
            "impossible",
            plan,
            program,
            message=f"The rooms do not fit with {words} ({why}).",
            alternatives=["Use smaller setbacks.", "Remove or shrink a room first."],
            ops=[op],
        )
    return EditResult(
        "ok",
        res.plan,
        res.program or program,
        summary=[f"Setbacks set to {words}; the whole layout was re-planned."],
        ops=[op],
        moved=[r.id for r in res.plan.rooms],
    )


def _set_pool_layout(
    plan: FloorPlan, program: RoomProgram, op: SetPoolLayout, time_limit_s: float
) -> EditResult:
    """Put the pool beside / in the middle of / between two blocks of the house. The
    whole layout is re-planned (rooms keep their sizes); simpler layouts are tried when
    the asked one does not fit, and the reply says so."""
    pool = next((r for r in plan.rooms if r.type == "pool"), None)
    if pool is None:
        raise EditError(
            "There is no pool in this plan yet.", ["Add one first: 'add a swimming pool'."]
        )
    current = program.pool_layout or "side"
    if op.layout == current:
        return EditResult(
            "no_change",
            plan,
            program,
            message=f"The plan already has a {POOL_NAMES[current]}.",
            ops=[op],
        )
    unit = "ft" if plan.meta.unit_display == "ft" else "m"
    beds = sum(1 for r in plan.rooms if r.type in ("bedroom", "master_bedroom"))
    p = plan.plot
    chain, notes = layout_chain(op.layout, p.width, p.depth, p.road_side, beds, unit)
    reqs = [
        ReqRoom(
            r.id,
            r.type,
            r.label,
            attached_to=r.attached_to,
            block="pool" if r.block == "pool" else None,
        )
        for r in program.rooms
    ]
    old = {r.id: r for r in program.rooms}
    for i, choice in enumerate(chain):
        base = reqs
        if choice.layout != "two_block":  # one house again: no guest lounge, a lobby back
            base = [r for r in reqs if r.id != POOL_LOUNGE_ID]
            if beds >= 3 and not any(r.type in ("lobby", "passage") for r in base):
                base.append(ReqRoom("lobby_1", "lobby", "LOBBY"))
        new_reqs, layout_notes = apply_layout(base, choice)
        target = pool_target_m2(choice, p.width, p.depth, p.road_side)
        rooms = [
            ProgramRoom(
                id=r.id,
                type=r.type,  # type: ignore[arg-type]
                label=r.label,
                target_area_m2=round(
                    target
                    if r.type == "pool" and target
                    else (old[r.id].target_area_m2 if r.id in old else TYPICAL_ROOM_M2[r.type]),
                    2,
                ),
                zone=ZONE_BY_TYPE[r.type],
                attached_to=r.attached_to,
                block=r.block,  # type: ignore[arg-type]
            )
            for r in new_reqs
        ]
        ids = {r.id for r in rooms}
        new_program = program.model_copy(
            update={
                "rooms": rooms,
                "adjacency": [a for a in program.adjacency if a.a in ids and a.b in ids],
                "pool_layout": choice.layout,
                "pool_axis": choice.axis,
            }
        )
        res = generate_layout(new_program, p, plan.meta, plan.id, time_limit_s=max(time_limit_s, 6))
        if res.ok:
            done = f"Moved the pool: {POOL_NAMES[choice.layout]}. The whole layout was re-planned."
            return EditResult(
                "ok",
                res.plan,
                res.program or new_program,
                summary=[done, *notes, *layout_notes],
                ops=[op],
                moved=[r.id for r in res.plan.rooms],
            )
        if i + 1 < len(chain):
            notes.append(pool_fallback_note(choice.layout, chain[i + 1].layout))
    return EditResult(
        "impossible",
        plan,
        program,
        message=f"A {POOL_NAMES[op.layout]} does not fit with these rooms on this plot.",
        alternatives=["Remove or shrink a room first.", "Use a larger plot."],
        ops=[op],
    )


# ------------------------------------------------------------------ simple changes


def _apply_simple(
    plan: FloorPlan, program: RoomProgram, op: EditOp
) -> tuple[FloorPlan, RoomProgram, str]:
    unit = plan.meta.unit_display
    if isinstance(op, RenameRoom):
        room = _plan_room(plan, op.id)
        label = _clean_label(op.label)
        if not label:
            raise EditError("The new name has no usable letters.")
        rooms = [
            r.model_copy(update={"label": label}) if r.id == room.id else r for r in plan.rooms
        ]
        prog = program.model_copy(
            update={
                "rooms": [
                    p.model_copy(update={"label": label}) if p.id == room.id else p
                    for p in program.rooms
                ]
            }
        )
        return plan.model_copy(update={"rooms": rooms}), prog, f"Renamed {room.label} to {label}."
    if isinstance(op, MoveDoor):
        door = next((d for d in plan.doors if d.id == op.id), None)
        if door is None:
            raise EditError(f"There is no door {op.id}.")
        to = plan.room(door.to_room)
        wall = op.wall or door.wall
        if door.from_room is None:
            ivs = exterior_intervals(plan, to, wall)
            if not ivs:
                raise EditError(f"The {wall} wall of {to.label} is not an outside wall.")
            iv = max(ivs, key=lambda i: i[1] - i[0])
        else:
            iv = shared_wall_interval(to, wall, plan.room(door.from_room))
            if iv is None:
                other = plan.room(door.from_room).label
                raise EditError(
                    f"The {wall} wall of {to.label} does not touch {other}, so the door "
                    "cannot go there."
                )
        start = _wall_start(to, wall)
        lo, hi = iv[0] + CLEAR - start, iv[1] - CLEAR - door.width - start
        if hi < lo:
            raise EditError(f"That wall is too short for a {fmt_length(door.width, unit)} door.")
        if op.offset is not None:
            offset = op.offset
            if not lo <= offset <= hi:
                raise EditError(
                    f"The door must start between {fmt_length(lo, unit)} and "
                    f"{fmt_length(hi, unit)} along that wall.",
                    [f"Use an offset of about {fmt_length(round((lo + hi) / 2), unit)}."],
                )
        else:
            offset = round((lo + hi) / 2)
        doors = [
            d.model_copy(update={"wall": wall, "offset": int(offset)}) if d.id == door.id else d
            for d in plan.doors
        ]
        moved_plan = FloorPlan.model_validate(
            plan.model_copy(update={"doors": doors}).model_dump(by_alias=True)
        )
        return moved_plan, program, f"Moved the door of {to.label}."
    if isinstance(op, AddWindow):
        return _add_window(plan, program, op)
    raise EditError(f"Unsupported operation {type(op).__name__}.")


def _window_slots(plan: FloorPlan, room: Room, wall: str) -> list[tuple[float, float]]:
    """Free stretches of an outside wall: not under a door and clear of other windows."""
    horizontal = wall in ("north", "south")
    (x1, y1), _ = wall_line(room, wall)
    coord = y1 if horizontal else x1
    taken = _door_spans_on_line(plan, horizontal, coord)
    for w in plan.windows:
        span = window_span(plan, w)
        if span.horizontal == horizontal:
            line = span.start[1] if horizontal else span.start[0]
            if abs(line - coord) <= 0.5:
                taken.append(span_interval(span))
    slots = []
    for iv in exterior_intervals(plan, room, wall):
        slots += _subtract(iv, taken, margin=20)
    small_room = room.type in ("bath", "toilet", "store", "utility", "dress", "shaft")
    least = MIN_WINDOW_CM if small_room else MIN_WINDOW_HABITABLE_CM
    return [sl for sl in slots if sl[1] - sl[0] >= least + 2 * CLEAR]


def _add_window(
    plan: FloorPlan, program: RoomProgram, op: AddWindow
) -> tuple[FloorPlan, RoomProgram, str]:
    """Add the window asked for: on the wall named if it is an outside wall with space,
    otherwise on the best other outside wall of the room (and say so)."""
    unit = plan.meta.unit_display
    room = _plan_room(plan, op.room)
    if room.is_open or room.type == "shaft":
        raise EditError(f"{room.label} is open to the sky, so it does not need a window.")
    order = [op.wall] if op.wall else []
    has_window = {w.wall for w in plan.windows if w.room == room.id}
    others = sorted(
        (s for s in SIDES if s != op.wall),
        key=lambda s: (
            s in has_window,
            -max((b - a for a, b in _window_slots(plan, room, s)), default=0),
        ),
    )
    for wall in order + others:
        slots = _window_slots(plan, room, wall)
        if not slots:
            continue
        lo, hi = max(slots, key=lambda sl: sl[1] - sl[0])
        width = int(min(op.width, hi - lo - 2 * CLEAR))
        start = _wall_start(room, wall)
        if op.offset is not None and wall == op.wall and lo <= start + op.offset <= hi - width:
            offset = op.offset
        else:
            offset = round((lo + hi - width) / 2) - start
        used = {o.id for o in (*plan.rooms, *plan.doors, *plan.windows, *plan.fixtures)}
        win = _fresh(
            Window(id="w1", room=room.id, wall=wall, offset=int(offset), width=width), "w", used
        )
        new = FloorPlan.model_validate(
            plan.model_copy(update={"windows": [*plan.windows, win]}).model_dump(by_alias=True)
        )
        note = f"Added a {fmt_length(width, unit)} window on the {wall} wall of {room.label}."
        if op.wall and wall != op.wall:
            why = (
                "is an inside wall"
                if not exterior_intervals(plan, room, op.wall)
                else "has no free space left"
            )
            note += f" (The {op.wall} wall {why}, so the window went on the {wall} wall.)"
        if width < op.width:
            note += f" It is {fmt_length(width, unit)} wide, the most that fits there."
        return new, program, note
    # Every outside wall already has a window: make the one on the wall asked for (or the
    # best one) as wide as the wall allows.
    for wall in order + others:
        wins = [w for w in plan.windows if w.room == room.id and w.wall == wall]
        if not wins:
            continue
        old_win = max(wins, key=lambda w: w.width)
        without = plan.model_copy(
            update={"windows": [w for w in plan.windows if w.id != old_win.id]}
        )
        lo_w, hi_w = span_interval(window_span(plan, old_win))
        slot = next(
            (sl for sl in _window_slots(without, room, wall) if sl[0] <= lo_w and hi_w <= sl[1]),
            None,
        )
        if slot is None:
            continue
        width = int(min(MAX_WINDOW_CM, slot[1] - slot[0] - 2 * CLEAR))
        if width < old_win.width + SIZE_STEP_CM:
            continue
        offset = round((slot[0] + slot[1] - width) / 2) - _wall_start(room, wall)
        windows = [
            w.model_copy(update={"width": width, "offset": int(offset)})
            if w.id == old_win.id
            else w
            for w in plan.windows
        ]
        new = FloorPlan.model_validate(
            plan.model_copy(update={"windows": windows}).model_dump(by_alias=True)
        )
        note = (
            f"The {wall} wall of {room.label} already had a window, so it was widened from "
            f"{fmt_length(old_win.width, unit)} to {fmt_length(width, unit)}."
        )
        return new, program, note
    if any(exterior_intervals(plan, room, s) for s in SIDES):
        raise EditError(
            f"{room.label} already has the largest windows that fit on its outside walls.",
            [f"Make {room.label} longer on an outside wall, then add a window."],
        )
    raise EditError(
        f"{room.label} has no outside wall, so a window would only look into another room.",
        [
            f"Move {room.label} to an outside wall first (for example, swap it with a room "
            "on the edge of the plot)."
        ],
    )


# ------------------------------------------------------------------------ summary


def summarize(old: FloorPlan, new: FloorPlan, notes: list[str]) -> list[str]:
    """Plain-language list of what changed (and how many rooms stayed exactly put)."""
    unit = new.meta.unit_display
    out = list(notes)
    before = {r.id: r for r in old.rooms if r.type != "shaft"}
    after = {r.id: r for r in new.rooms if r.type != "shaft"}
    for rid, r in after.items():
        o = before.get(rid)
        name = _name(new, rid)
        if o is None:
            out.append(f"{name} is {fmt_size(r.w, r.h, unit)}.")
        elif (o.w, o.h) != (r.w, r.h):
            out.append(f"{name}: {fmt_size(o.w, o.h, unit)} -> {fmt_size(r.w, r.h, unit)}.")
        elif (o.x, o.y) != (r.x, r.y):
            out.append(f"{name} moved ({fmt_size(r.w, r.h, unit)}).")
    same = [rid for rid in after if rid in before and _rect(before[rid]) == _rect(after[rid])]
    if before and same and len(same) < len(after):
        out.append(f"{len(same)} other room(s) kept their exact place and size.")
    if not out:
        out.append("Nothing changed.")
    return list(dict.fromkeys(out))


# ------------------------------------------------------------------- alternatives


def _layout_alternatives(ops: list[EditOp], plan: FloorPlan, allow_reflow: bool) -> list[str]:
    alts: list[str] = []
    for op in ops:
        if isinstance(op, AddRoom):
            gardens = [r.label for r in plan.rooms if r.type in ("garden", "courtyard", "deck")]
            if gardens:
                alts.append(f"Make it smaller, or take the space from the {gardens[0]}.")
            else:
                alts.append("Make it smaller, or remove another room first.")
        if isinstance(op, MoveRoom) and op.anchor:
            sides = ANCHOR_SIDES[op.anchor]
            here = [
                o.label
                for o in plan.rooms
                if o.id != op.id
                and o.type not in ("shaft", "garden", "courtyard", "parking", "balcony", "pool")
                and all(_touches(o, plan.plot, s) for s in sides)
            ]
            if here and op.id in {r.id for r in plan.rooms}:
                alts.append(f"Swap {plan.room(op.id).label} with {here[0]} instead.")
    alts += _generic_alternatives(ops, allow_reflow)
    return list(dict.fromkeys(alts))


def _generic_alternatives(ops: list[EditOp], allow_reflow: bool) -> list[str]:
    if allow_reflow or not any(isinstance(o, LAYOUT_OPS) for o in ops):
        return []
    return ["Allow other rooms to move (the layout around your change is re-planned)."]


# ------------------------------------------------------------------------ helpers


def program_from_plan(plan: FloorPlan) -> RoomProgram:
    """A program matching an existing plan (used when the original program is lost)."""
    door_pairs: dict[str, set[str]] = {}
    for d in plan.doors:
        if d.from_room:
            door_pairs.setdefault(d.to_room, set()).add(d.from_room)
            door_pairs.setdefault(d.from_room, set()).add(d.to_room)
    rooms = []
    types = {r.id: r.type for r in plan.rooms}
    for r in plan.rooms:
        if r.type == "shaft":
            continue
        attached = None
        links = door_pairs.get(r.id, set())
        if r.type in ("bath", "toilet", "dress") and len(links) == 1:
            (only,) = links
            if types.get(only) in ("bedroom", "master_bedroom"):
                attached = only
        rooms.append(
            ProgramRoom(
                id=r.id,
                type=r.type,
                label=r.label,
                target_area_m2=round(r.area_m2, 2),
                zone=ZONE_BY_TYPE[r.type],
                attached_to=attached,
            )
        )
    return RoomProgram(rooms=rooms, entrance_side=plan.plot.road_side)


def _check_program_matches(plan: FloorPlan, program: RoomProgram) -> None:
    plan_ids = {r.id for r in plan.rooms if r.type != "shaft"}
    prog_ids = {p.id for p in program.rooms}
    if plan_ids != prog_ids:
        raise EditError("The saved plan and its room list are out of step; regenerate the plan.")


def _room(work: _Work, rid: str) -> Room:
    if rid in work.rooms:
        return work.rooms[rid]
    names = ", ".join(f"{r.label} ({r.id})" for r in work.rooms.values())
    raise EditError(f"There is no room '{rid}' in this plan. Rooms: {names}.")


def _plan_room(plan: FloorPlan, rid: str) -> Room:
    try:
        return plan.room(rid)
    except KeyError:
        raise EditError(f"There is no room '{rid}' in this plan.") from None


def _set_target(work: _Work, rid: str, area: float) -> None:
    work.program[rid] = work.program[rid].model_copy(update={"target_area_m2": round(area, 2)})


def _new_id(work: _Work, t: str) -> str:
    n = 1
    while f"{t}_{n}" in work.program or f"{t}_{n}" in work.rooms:
        n += 1
    return f"{t}_{n}"


def _clean_label(label: str | None) -> str:
    return re.sub(r"[^A-Z0-9 ./&-]", "", (label or "").strip().upper())[:24].strip()


def _min_area(t: str) -> float:
    return max(MIN_ROOM[t].area_m2, (MIN_ROOM[t].short_side_cm / 100) ** 2)


def _span(asked: int | None, current: int) -> tuple[int, int]:
    if asked is not None:
        return (asked - SIZE_STEP_CM, asked + SIZE_STEP_CM)
    return (round(current * (1 - OTHER_SIDE_SLACK)), round(current * (1 + OTHER_SIDE_SLACK)))


def _name(plan: FloorPlan, rid: str) -> str:
    """Room label, with its position when several rooms share that label."""
    r = plan.room(rid)
    if sum(o.label == r.label for o in plan.rooms) > 1:
        return f"{r.label} ({_where(r, plan.plot)})"
    return r.label


def _shaft_area(plan: FloorPlan) -> float:
    return sum(r.area_m2 for r in plan.rooms if r.type == "shaft" and not r.part_of)


def _rect(r: Room) -> tuple[int, int, int, int]:
    return (r.x, r.y, r.w, r.h)


def _wall_start(room: Room, wall: str) -> int:
    return room.x if wall in ("north", "south") else room.y


def _shared_len(a: Room, b: Room) -> float:
    best = 0.0
    for wall in SIDES:
        iv = shared_wall_interval(a, wall, b)
        if iv:
            best = max(best, iv[1] - iv[0])
    return best


def _shares_door_wall(geom: dict[str, Room], a: str, b: str, a_type: str) -> bool:
    if a not in geom or b not in geom:
        return True  # the solver will place it
    return _shared_len(geom[a], geom[b]) >= max(door_span_needed(a_type), DOOR_MIN_WIDTH_CM)


def _neighbours(room: Room, others) -> set[str]:
    return {o.id for o in others if o.id != room.id and _shared_len(room, o) > 0}


def _touches(r: Room, plot: Plot, side: str) -> bool:
    return {
        "north": r.y == 0,
        "south": r.y2 == plot.depth,
        "west": r.x == 0,
        "east": r.x2 == plot.width,
    }[side]


def _where(r: Room, plot: Plot) -> str:
    cx, cy = (r.x + r.w / 2) / plot.width, (r.y + r.h / 2) / plot.depth
    ns = "north" if cy < 1 / 3 else ("south" if cy > 2 / 3 else "")
    ew = "west" if cx < 1 / 3 else ("east" if cx > 2 / 3 else "")
    return "-".join(p for p in (ns, ew) if p) or "centre"


__all__ = [
    "EditInterpretation",
    "EditResult",
    "apply_edit",
    "describe_plan",
    "edit_plan",
    "interpret_edit",
    "program_from_plan",
    "summarize",
    "topology_from_plan",
]
