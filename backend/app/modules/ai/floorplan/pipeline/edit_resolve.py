"""Edits that re-solve the whole plan (see pipeline/resolve.py).

    add_rules          new layout rules: always a full re-solve with every rule
    resolve            "break the plan", "start over": a full re-solve
    remove_rule        drop a rule, then re-solve
    a layout op that did not fit the current layout (move, resize, add, remove): turned
                       into rules and room changes, then a full re-solve

Spatial requests are never answered "not supported": they become rules, and if the rules
cannot all hold the reply names the conflicting ones and offers two layouts that work.
"""

from collections.abc import Callable

from app.modules.ai.floorplan.pipeline.resolve import full_resolve
from app.modules.ai.floorplan.pipeline.rules_check import FRAME
from app.modules.ai.floorplan.rules import TYPICAL_ROOM_M2
from app.modules.ai.floorplan.schemas.common import DEFAULT_LABEL, ZONE_BY_TYPE
from app.modules.ai.floorplan.schemas.edit_ops import (
    AddRoom,
    AddRules,
    MoveRoom,
    RemoveRoom,
    RemoveRule,
    ResizeRoom,
)
from app.modules.ai.floorplan.schemas.plan import FloorPlan
from app.modules.ai.floorplan.schemas.program import ProgramRoom, RoomProgram
from app.modules.ai.floorplan.schemas.rules import (
    Place,
    SizeRule,
    Touches,
    describe_rule,
    resolve_rule,
    rule_rooms,
)

Progress = Callable[[str, str], None]


def _relative(compass: str, road: str) -> str:
    front, rear, left, right = FRAME[road]
    return {front: "front", rear: "rear", left: "left", right: "right"}[compass]


def ops_to_program(
    plan: FloorPlan, program: RoomProgram, ops: list
) -> tuple[RoomProgram, list[str]]:
    """The program with the ops applied as room changes and rules."""
    rooms = list(program.rooms)
    rules = list(program.rules)
    notes: list[str] = []
    road = plan.plot.road_side or "south"
    current = {r.id: r for r in plan.rooms}
    for op in ops:
        if isinstance(op, AddRules):
            for rl in op.rules:
                resolved = resolve_rule(rl, rooms)
                if resolved is None:
                    missing = [
                        ref for ref in rule_rooms(rl) if resolve_rule_ref(ref, rooms) is None
                    ]
                    notes.append(
                        f"Not applied: “{describe_rule(rl)}” names a room the plan does not have "
                        f"({', '.join(missing)}). Add the room first."
                    )
                else:
                    rules.append(resolved)
        elif isinstance(op, RemoveRule):
            if 1 <= op.index <= len(rules):
                gone = rules.pop(op.index - 1)
                notes.append(f"Dropped the rule “{describe_rule(gone)}”.")
        elif isinstance(op, MoveRoom):
            if op.anchor:
                for compass in op.anchor.split("-"):
                    rules.append(
                        Place(kind="place", room=op.id, side=_relative(compass, road), text="")
                    )
            if op.next_to:
                rules.append(Touches(kind="touches", room=op.id, others=[op.next_to]))
        elif isinstance(op, ResizeRoom) and op.id in current:
            r = current[op.id]
            w = op.width_cm or r.w
            h = op.height_cm or r.h
            if op.width_cm or op.height_cm:
                area = w * h / 10_000
                rules.append(
                    SizeRule(
                        kind="size", room=op.id, min_area_m2=area * 0.95, max_area_m2=area * 1.05
                    )
                )
            elif op.change == "smaller":
                rules.append(SizeRule(kind="size", room=op.id, max_area_m2=r.area_m2 * 0.88))
            else:
                rules.append(SizeRule(kind="size", room=op.id, min_area_m2=r.area_m2 * 1.12))
        elif isinstance(op, AddRoom):
            ids = {r.id for r in rooms}
            rid = next(f"{op.type}_{i}" for i in range(1, 99) if f"{op.type}_{i}" not in ids)
            rooms.append(
                ProgramRoom(
                    id=rid,
                    type=op.type,
                    label=(op.label or DEFAULT_LABEL[op.type]).upper()[:24],
                    target_area_m2=op.target_area_m2 or TYPICAL_ROOM_M2[op.type],
                    zone=ZONE_BY_TYPE[op.type],
                )
            )
            if op.next_to:
                rules.append(Touches(kind="touches", room=rid, others=[op.next_to], door=True))
        elif isinstance(op, RemoveRoom):
            rooms = [r for r in rooms if r.id != op.id]
            rules = [rl for rl in rules if op.id not in rule_rooms(rl)]
    return program.model_copy(update={"rooms": rooms, "rules": rules}), notes


def resolve_rule_ref(ref: str, rooms: list) -> str | None:
    from app.modules.ai.floorplan.schemas.rules import resolve_ref

    return resolve_ref(ref, rooms)


def resolve_edit(
    plan: FloorPlan,
    program: RoomProgram,
    ops: list,
    *,
    why: str = "",
    progress: Progress | None = None,
):
    """Apply ops as a full re-solve. Returns an edit_engine.EditResult."""
    from app.modules.ai.floorplan.pipeline.edit_engine import EditResult, summarize

    new_program, notes = ops_to_program(plan, program, ops)
    res = full_resolve(plan, new_program, progress=progress)
    names = {r.id: r.label for r in new_program.rooms}
    if res.ok:
        n = len(new_program.rules)
        head = why or "Re-planned the whole house"
        line = f"{head} in {res.seconds:.0f} s" + (
            f", keeping all {n} layout rule(s): "
            + "; ".join(describe_rule(r, names) for r in new_program.rules)
            + "."
            if n
            else "."
        )
        summary = [line, *notes, *summarize(plan, res.plan, [])[:4]]
        return EditResult(
            "ok",
            res.plan,
            new_program,
            summary=summary,
            ops=ops,
            moved=[r.id for r in res.plan.rooms],
            resolved=True,
        )
    if res.conflicts:
        message = "These rules cannot all hold on this plot: " + "; ".join(res.conflicts) + "."
    else:
        message = "The house could not be laid out again with these rooms on this plot."
        if res.reasons:
            message += " Main problems: " + "; ".join(res.reasons) + "."
    alternatives: list[str] = []
    if res.options:
        message += " Layouts that do work:"
        for k, opt in enumerate(res.options, 1):
            message += f" option {k}, {opt.label};"
            alternatives.append(f"use option {k} ({opt.label})")
        message = message.rstrip(";") + ". Say “use option 1” or “use option 2”."
    else:
        alternatives = [
            "make the plot larger or the setbacks smaller",
            "remove a room or make rooms smaller",
            "drop one of the rules",
        ]
    return EditResult(
        "impossible",
        plan,
        program,
        message=" ".join([message, *notes]).strip(),
        alternatives=alternatives,
        ops=ops,
        options=res.options,
    )
