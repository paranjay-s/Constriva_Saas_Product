"""Relaxation ladder (A1): when the full solve finds no plan, give up wishes one family at a
time, never the rooms, until a plan is found. A plan is always delivered.

    weighted     every wish becomes a weighted preference (solver soft mode): the plan keeps
                 the wishes it can, the most important first (layout.solver.WISH_WEIGHT)
    a shape      aspect-ratio and daylight wishes dropped (rooms may be up to 3:1)
    b core       low-weight adjacency wishes and front / rear / side wishes dropped
    c shrink     rooms shrunk toward their minimum sizes (85 %, then 70 % of their targets)
    d plot       other plot proportions when the person gave only an area: 1:1, 3:4, 2:3,
                 1:2 and their turned versions
    e below_min  rooms may go below the standard minimum sizes (80 % of the minimum side),
                 each one named in a note
    f fallback   a deterministic corridor layout by zone (layout/fallback.py), always made;
                 anything the checks still find is reported, not hidden

Each rung is cumulative. Every rung that runs is logged (`log`), and every wish or size that
was given up is written in plain words (`adjustments`) for the chat reply.
"""

import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from app.modules.ai.floorplan.pipeline.layout.engine import assemble, with_spare_garden
from app.modules.ai.floorplan.pipeline.layout.fallback import corridor_layout
from app.modules.ai.floorplan.pipeline.layout.solver import (
    fill_gaps,
    fill_holes_with_shafts,
    solve_layout,
)
from app.modules.ai.floorplan.pipeline.layout.topology import build_topology
from app.modules.ai.floorplan.pipeline.rules_check import FRAME, rule_problems
from app.modules.ai.floorplan.pipeline.validator import ValidationReport, validate
from app.modules.ai.floorplan.rules import MIN_ROOM
from app.modules.ai.floorplan.schemas.plan import FloorPlan, Meta, Plot, Room
from app.modules.ai.floorplan.schemas.program import RoomProgram
from app.modules.ai.floorplan.schemas.rules import (
    Daylight,
    DoorBetween,
    Place,
    SizeRule,
    Touches,
    ZoneRule,
)

logger = logging.getLogger("construtiva.ai.floorplan.relax")
Progress = Callable[[str, str], None]

STEPS = ("weighted", "shape", "core", "shrink", "plot", "below_min", "fallback")
STEP_LABEL = {
    "weighted": "every wish as a weighted preference",
    "shape": "a. aspect-ratio and daylight wishes dropped",
    "core": "b. low-weight adjacencies and sides dropped",
    "shrink": "c. rooms shrunk toward their minimum sizes",
    "plot": "d. other plot proportions",
    "below_min": "e. rooms below the standard minimums",
    "fallback": "f. simple corridor layout",
}
LOW_ADJACENCY = 6  # adjacency wishes below this weight (1-10) go at rung b
SHRINK = (0.85, 0.7)
RATIOS = ((1, 1), (3, 4), (4, 3), (2, 3), (3, 2), (1, 2), (2, 1))
BELOW_MIN_SCALE = 0.8
OUTDOOR = ("garden", "lawn", "pool", "deck", "parking", "driveway", "dock", "courtyard", "balcony")
RESTORE = (
    "Ask me to bring any of these back (for example “make the pool touch the garden”) "
    "and I will re-plan with it."
)


@dataclass
class RelaxResult:
    plan: FloorPlan
    program: RoomProgram
    step: str
    adjustments: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
    report: ValidationReport | None = None


def _name(label: str) -> str:
    return "the " + " ".join(label.split()).lower()


def _frame_side(room: Room, plot: Plot) -> str:
    """Where a room is, as front / rear / left / right / centre of the plot."""
    road = plot.road_side or "south"
    front, rear, left, right = FRAME[road]
    cx = (room.x + room.x2) / 2 / plot.width - 0.5
    cy = (room.y + room.y2) / 2 / plot.depth - 0.5
    offsets = {"south": cy, "north": -cy, "east": cx, "west": -cx}
    pos = {
        "front": offsets[front],
        "rear": -offsets[front],
        "left": offsets[left],
        "right": offsets[right],
    }
    side, value = max(pos.items(), key=lambda kv: kv[1])
    return side if value > 0.12 else "centre"


def _neighbour(plan: FloorPlan, rid: str) -> Room | None:
    from app.modules.ai.floorplan.pipeline.rules_check import shared_len

    me = next((r for r in plan.rooms if r.id == rid), None)
    if me is None:
        return None
    best = [
        (shared_len(me, o), o)
        for o in plan.rooms
        if o.id != rid and o.type != "shaft" and shared_len(me, o) > 0
    ]
    return max(best, key=lambda t: t[0])[1] if best else None


def describe_unmet(rule, plan: FloorPlan) -> list[str]:
    """The person's wish that was given up, and what the plan does instead."""
    rooms = {r.id: r for r in plan.rooms}

    def nm(rid: str) -> str:
        return _name(rooms[rid].label) if rid in rooms else rid.replace("_", " ")

    out = []
    if isinstance(rule, Touches):
        from app.modules.ai.floorplan.pipeline.rules_check import has_door, shared_len

        for o in rule.others:
            a, b = rooms.get(rule.room), rooms.get(o)
            if a is None or b is None:
                continue
            if shared_len(a, b) >= 90 and (not rule.door or has_door(plan, a.id, b.id)):
                continue
            n = _neighbour(plan, a.id)
            instead = f"; it is next to {_name(n.label)} instead" if n else ""
            what = "open onto" if rule.door else "touch"
            out.append(f"{nm(a.id).capitalize()} could not {what} {nm(b.id)}{instead}.")
    elif isinstance(rule, DoorBetween):
        out.append(f"There is no door between {nm(rule.a)} and {nm(rule.b)}.")
    elif isinstance(rule, Place) and rule.room in rooms:
        where = _frame_side(rooms[rule.room], plan.plot)
        at = "in the centre" if where == "centre" else f"at the {where}"
        want = "in the centre" if rule.side == "centre" else f"at the {rule.side}"
        out.append(f"{nm(rule.room).capitalize()} could not go {want}; it is {at} instead.")
    elif isinstance(rule, ZoneRule):
        out.append(f"{nm(rule.room).capitalize()} is not in the {rule.zone} part of the house.")
    elif isinstance(rule, SizeRule) and rule.room in rooms:
        r = rooms[rule.room]
        out.append(
            f"{nm(rule.room).capitalize()} could not keep the size you asked for; it is "
            f"{r.area_m2:.1f} m² ({r.w / 100:.1f} x {r.h / 100:.1f} m)."
        )
    elif isinstance(rule, Daylight):
        out.append(f"{nm(rule.room).capitalize()} has no outside wall, so no window.")
    return out


def _met_rules(plan: FloorPlan, program: RoomProgram, unmet: set[int]) -> tuple[list, list]:
    """Split the program's rules into those the plan meets and those it does not."""
    kept, dropped = [], []
    for i, rl in enumerate(program.rules):
        if i in unmet:
            dropped.append(rl)
            continue
        one = program.model_copy(update={"rules": [rl]})
        (dropped if rule_problems(plan, one) else kept).append(rl)
    return kept, dropped


def _scaled(program: RoomProgram, factor: float, floor: float = 1.0) -> RoomProgram:
    rooms = []
    for r in program.rooms:
        rule = MIN_ROOM[r.type]
        least = max(rule.area_m2, (rule.short_side_cm / 100) ** 2) * floor
        rooms.append(
            r.model_copy(update={"target_area_m2": round(max(least, r.target_area_m2 * factor), 2)})
        )
    return program.model_copy(update={"rooms": rooms})


def _plot_shapes(plot: Plot) -> list[tuple[str, Plot]]:
    area = plot.width * plot.depth
    out = []
    for rw, rd in RATIOS:
        w = round(math.sqrt(area * rw / rd) / 5) * 5
        d = round(area / w / 5) * 5
        if abs(w - plot.width) < 50 and abs(d - plot.depth) < 50:
            continue
        out.append((f"{rw}:{rd}", plot.model_copy(update={"width": w, "depth": d})))
    return out


def relax_layout(
    program: RoomProgram,
    plot: Plot,
    meta: Meta,
    plan_id: str,
    *,
    shape_assumed: bool = False,
    unit: str = "ft",
    time_limit_s: float = 6.0,
    progress: Progress | None = None,
) -> RelaxResult:
    started = time.monotonic()
    log: list[str] = []

    def tell(step: str) -> None:
        if progress:
            progress("layout", f"Adjusting the plan to fit: {STEP_LABEL[step]}")

    def attempt(step: str, prog: RoomProgram, plt: Plot, relaxed: set[str], **kw):
        prog = with_spare_garden(prog, plt)
        topo = build_topology(prog)
        info: dict = {}
        t0 = time.monotonic()
        rooms = solve_layout(
            prog, plt, topo, time_limit_s=time_limit_s, soft=True, info=info, **kw
        )
        took = time.monotonic() - t0
        if rooms is None:
            log.append(f"{step}: no layout ({info.get('status', '?')}, {took:.1f} s)")
            return None
        targets = {r.id: r.target_area_m2 for r in prog.rooms}
        rooms = fill_holes_with_shafts(fill_gaps(rooms, plt, targets), plt)
        kept_prog = prog.model_copy(
            update={"rules": [r for i, r in enumerate(prog.rules) if i not in info["unmet"]]}
        )
        plan = assemble(rooms, topo, plt, meta, plan_id, kept_prog)
        kept, dropped = _met_rules(plan, prog, set(info["unmet"]))
        final = prog.model_copy(update={"rules": kept})
        rep = validate(plan, final)
        _downgrade(rep, relaxed)
        if not rep.ok:
            log.append(f"{step}: layout found but {'; '.join(rep.feedback()[:2])} ({took:.1f} s)")
            return None
        log.append(f"{step}: plan found, {len(dropped)} wish(es) given up ({took:.1f} s)")
        return plan, final, dropped, rep

    def done(step: str, found, extra: list[str]) -> RelaxResult:
        plan, final, _, rep = found
        # every wish of the person's program the delivered plan does not meet, including
        # those a rung removed from the solve (some still hold by chance and are kept)
        kept, dropped = _met_rules(plan, base, set())
        final = final.model_copy(update={"rules": kept})
        adjustments = [line for rl in dropped for line in describe_unmet(rl, plan)]
        adjustments += extra
        logger.info(
            "relaxation ladder: %s after %.1f s (%s)", step, time.monotonic() - started, log
        )
        return RelaxResult(plan, final, step, adjustments, log, rep)

    base = program
    # weighted: every wish soft
    tell("weighted")
    found = attempt("weighted", base, plot, set())
    if found:
        return done("weighted", found, [])

    # a: shape and daylight
    tell("shape")
    no_shape = base.model_copy(
        update={
            "rules": [
                r
                for r in base.rules
                if not isinstance(r, Daylight)
                and not (isinstance(r, SizeRule) and r.max_aspect and not r.min_area_m2)
            ]
        }
    )
    shape_kw = {"aspect_floor": 3.0, "daylight": False}
    shape_note: list[str] = []
    found = attempt("shape", no_shape, plot, set(), **shape_kw)
    if found:
        return done("shape", found, shape_note)

    # b: low-weight adjacency wishes and sides
    tell("core")
    core = no_shape.model_copy(
        update={
            "rules": [r for r in no_shape.rules if not isinstance(r, Place | ZoneRule)],
            "adjacency": [a for a in no_shape.adjacency if a.weight >= LOW_ADJACENCY],
        }
    )
    core_note = shape_note
    found = attempt("core", core, plot, set(), **shape_kw)
    if found:
        return done("core", found, core_note)

    # c: shrink rooms
    tell("shrink")
    for factor in SHRINK:
        small = _scaled(core, factor)
        found = attempt(f"shrink {factor:.0%}", small, plot, set(), **shape_kw)
        if found:
            return done("shrink", found, core_note + [_shrink_note(core, found[1])])

    # d: other plot proportions (only when the shape was assumed)
    if shape_assumed:
        tell("plot")
        small = _scaled(core, SHRINK[0])
        for ratio, plt in _plot_shapes(plot):
            found = attempt(f"plot {ratio}", small, plt, set(), **shape_kw)
            if found:
                note = (
                    "You gave only the plot area, so its shape was assumed; it is planned as "
                    f"{_size(plt, unit)} ({ratio} width to depth) instead of {_size(plot, unit)}, "
                    "which fits the rooms better. Give the real width and depth to change it."
                )
                return done("plot", found, core_note + [note, _shrink_note(core, found[1])])

    # e: below the standard minimums
    tell("below_min")
    tiny = _scaled(core, SHRINK[-1], floor=BELOW_MIN_SCALE**2)
    found = attempt(
        "below_min", tiny, plot, {"MIN_AREA", "MIN_SIDE"}, min_side_scale=BELOW_MIN_SCALE,
        **shape_kw,
    )
    if found:
        small_notes = _below_min_notes(found[0])
        return done("below_min", found, core_note + [_shrink_note(core, found[1])] + small_notes)

    # f: the corridor layout, always made
    tell("fallback")
    return _fallback(core, plot, meta, plan_id, log, core_note, started)


def _downgrade(rep: ValidationReport, codes: set[str]) -> None:
    keep = []
    for issue in rep.errors:
        if issue.code in codes:
            rep.add(issue.code, issue.message, *issue.ids, warning=True)
        else:
            keep.append(issue)
    rep.errors = keep


def _shrink_note(before: RoomProgram, after: RoomProgram) -> str:
    a = sum(r.target_area_m2 for r in before.rooms if r.zone != "open")
    b = sum(r.target_area_m2 for r in after.rooms if r.zone != "open")
    pct = 1 - b / a if a else 0
    return f"The rooms were made about {pct:.0%} smaller than first planned so they fit."


def _below_min_notes(plan: FloorPlan) -> list[str]:
    out = []
    for r in plan.rooms:
        if r.type == "shaft" or r.type not in MIN_ROOM:
            continue
        rule = MIN_ROOM[r.type]
        short = min(r.w, r.h)
        if r.area_m2 + 1e-6 < rule.area_m2 or short < rule.short_side_cm:
            out.append(
                f"{_name(r.label).capitalize()} is {r.area_m2:.1f} m² and {short / 100:.2f} m "
                f"wide, below the usual minimum ({rule.area_m2:g} m², "
                f"{rule.short_side_cm / 100:g} m)."
            )
    return out


def _size(plot: Plot, unit: str) -> str:
    if unit == "ft":
        return f"{plot.width / 30.48:.0f} x {plot.depth / 30.48:.0f} ft"
    return f"{plot.width / 100:g} x {plot.depth / 100:g} m"


def _fallback(
    program: RoomProgram,
    plot: Plot,
    meta: Meta,
    plan_id: str,
    log: list[str],
    notes: list[str],
    started: float,
) -> RelaxResult:
    prog = with_spare_garden(program, plot)
    fb = corridor_layout(prog, plot)
    prog = fb.program
    targets = {r.id: r.target_area_m2 for r in prog.rooms}
    rooms = fill_holes_with_shafts(fill_gaps(fb.rooms, plot, targets), plot)
    # the delivered sizes become the program's targets (the corridor layout sets them)
    by_id = {r.id: r for r in rooms}
    prog = prog.model_copy(
        update={
            "rooms": [
                p.model_copy(update={"target_area_m2": round(by_id[p.id].area_m2, 2)})
                if p.id in by_id
                else p
                for p in prog.rooms
                if p.id in by_id
            ],
            "rules": [],
        }
    )
    plan = assemble(rooms, fb.topology, plot, meta, plan_id, prog)
    kept, dropped = _met_rules(plan, program, set())
    rep = validate(plan, prog)
    issues = [f"{i.code}: {i.message}" for i in rep.errors]
    _downgrade(rep, {i.code for i in rep.errors})
    adjustments = [line for rl in dropped for line in describe_unmet(rl, plan)]
    adjustments.append(
        "None of the layouts that keep your wishes fitted, so the rooms are arranged along "
        "a corridor (public rooms at the front, bedrooms at the back)."
    )
    adjustments += notes + fb.notes
    if issues:
        adjustments.append("Still to check on this plan: " + "; ".join(issues[:4]) + ".")
    log.append(f"fallback: corridor layout, {len(issues)} issue(s) reported")
    logger.info("relaxation ladder: fallback after %.1f s", time.monotonic() - started)
    final = prog.model_copy(update={"rules": kept})
    return RelaxResult(plan, final, "fallback", adjustments, log, rep)
