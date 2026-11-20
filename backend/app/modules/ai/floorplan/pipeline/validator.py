"""Plan validator. A plan with any error is never shown to the user.

Errors (plan rejected):
  OUTSIDE_PLOT, OVERLAP, MIN_AREA, MIN_SIDE, DOOR_NOT_ON_SHARED_WALL, DOOR_TOO_WIDE,
  DOOR_TOO_NARROW, WINDOW_NOT_EXTERIOR, NO_ENTRANCE, UNREACHABLE, ATTACHED_BATH,
  FIXTURE_OUTSIDE_ROOM, PROGRAM_MISSING_ROOM, PROGRAM_TYPE_MISMATCH, AREA_MISMATCH,
  TOTAL_AREA_MISMATCH
Warnings (plan allowed):
  WET_NOT_CLUSTERED, PLOT_GAPS, EXTRA_ROOM, LARGE_SHAFTS

Messages are short and exact so they can be fed back to the layout step on retry.
"""

from dataclasses import dataclass, field
from itertools import combinations
from typing import Literal

import networkx as nx
from shapely.geometry import box
from shapely.ops import unary_union

from app.modules.ai.floorplan.geometry import (
    door_span,
    exterior_intervals,
    interval_within,
    room_box,
    shared_wall_interval,
    span_interval,
    wall_length,
    window_span,
)
from app.modules.ai.floorplan.pipeline.pool_layouts import (
    LINED_SHARE,
    is_special,
    rect_frame,
)
from app.modules.ai.floorplan.pipeline.pool_layouts import (
    NAMES as POOL_LAYOUT_NAMES,
)
from app.modules.ai.floorplan.render.symbols import footprint
from app.modules.ai.floorplan.rules import (
    AREA_FLEXIBLE_TYPES,
    DOOR_MIN_WIDTH_CM,
    MIN_PLOT_COVERAGE,
    MIN_ROOM,
    OPEN_AREA_CAP,
    OPENING_END_CLEARANCE_CM,
    OVERLAP_EPS_CM2,
    ROOM_AREA_TOLERANCE,
    SHAFT_WARN_M2,
    TOTAL_AREA_TOLERANCE,
)
from app.modules.ai.floorplan.schemas.common import WET_TYPES
from app.modules.ai.floorplan.schemas.plan import Door, FloorPlan, Room
from app.modules.ai.floorplan.schemas.program import RoomProgram

OUTSIDE = "__outside__"


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    ids: tuple[str, ...] = ()
    severity: Literal["error", "warning"] = "error"


@dataclass
class ValidationReport:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def codes(self) -> set[str]:
        return {i.code for i in self.errors}

    def feedback(self) -> list[str]:
        """Error lines for the layout retry loop."""
        return [f"{i.code}: {i.message}" for i in self.errors]

    def add(self, code: str, message: str, *ids: str, warning: bool = False) -> None:
        if warning:
            self.warnings.append(Issue(code, message, ids, "warning"))
        else:
            self.errors.append(Issue(code, message, ids, "error"))


def validate(plan: FloorPlan, program: RoomProgram | None = None) -> ValidationReport:
    rep = ValidationReport()
    _check_bounds(plan, rep)
    _check_overlaps(plan, rep)
    _check_min_sizes(plan, rep)
    _check_doors(plan, rep)
    _check_windows(plan, rep)
    _check_reachability(plan, rep)
    _check_fixtures(plan, rep)
    if program is not None:
        _check_program(plan, program, rep)
        _check_pool_layout(plan, program, rep)
        if program.rules:
            from app.modules.ai.floorplan.pipeline.rules_check import rule_problems

            for message, ids in rule_problems(plan, program):
                rep.add("RULE", message, *ids)
    _check_wet_cluster(plan, rep)
    _check_shafts(plan, rep)
    _check_coverage(plan, rep)
    _check_setbacks(plan, rep)
    return rep


def _check_setbacks(plan: FloorPlan, rep: ValidationReport) -> None:
    """Enclosed rooms inside the setback line; built-up area near its target."""
    if not plan.plot.has_setbacks:
        return
    x0, y0, x1, y1 = plan.plot.buildable()
    for r in plan.rooms:
        if r.is_open or r.type == "shaft":
            continue
        if r.x < x0 or r.y < y0 or r.x2 > x1 or r.y2 > y1:
            rep.add("SETBACK", f"{r.id} crosses the setback line", r.id)
    target = plan.plot.built_up_m2
    if target:
        built = plan.built_area_m2
        if built < 0.85 * target:
            rep.add(
                "BUILT_UP_LOW",
                f"rooms cover {built:.0f} m2 of the {target:.0f} m2 built-up target",
                warning=True,
            )


# ---------------------------------------------------------------------- geometry


def _check_bounds(plan: FloorPlan, rep: ValidationReport) -> None:
    for r in plan.rooms:
        if r.x2 > plan.plot.width or r.y2 > plan.plot.depth:
            rep.add(
                "OUTSIDE_PLOT",
                f"{r.id} ({r.x},{r.y} {r.w}x{r.h}) extends beyond plot "
                f"{plan.plot.width}x{plan.plot.depth}",
                r.id,
            )


def _check_overlaps(plan: FloorPlan, rep: ValidationReport) -> None:
    for a, b in combinations(plan.rooms, 2):
        area = room_box(a).intersection(room_box(b)).area
        if area > OVERLAP_EPS_CM2:
            rep.add("OVERLAP", f"{a.id} and {b.id} overlap by {area / 10_000:.2f} m2", a.id, b.id)


def _check_min_sizes(plan: FloorPlan, rep: ValidationReport) -> None:
    for r in plan.rooms:
        rule = MIN_ROOM[r.type]
        if r.area_m2 + 1e-9 < rule.area_m2:
            rep.add(
                "MIN_AREA",
                f"{r.id} is {r.area_m2:.2f} m2, minimum for {r.type} is {rule.area_m2} m2",
                r.id,
            )
        if min(r.w, r.h) < rule.short_side_cm:
            rep.add(
                "MIN_SIDE",
                f"{r.id} short side is {min(r.w, r.h)} cm, minimum for {r.type} is "
                f"{rule.short_side_cm} cm",
                r.id,
            )


# ------------------------------------------------------------------------ doors


def _door_host_interval(plan: FloorPlan, door: Door) -> list[tuple[float, float]]:
    """Wall intervals where this door may legally sit."""
    to = plan.room(door.to_room)
    if door.from_room is None:
        return exterior_intervals(plan, to, door.wall)
    frm = plan.room(door.from_room)
    iv = shared_wall_interval(to, door.wall, frm)
    return [iv] if iv else []


def _check_doors(plan: FloorPlan, rep: ValidationReport) -> None:
    for d in plan.doors:
        to = plan.room(d.to_room)
        if d.width < DOOR_MIN_WIDTH_CM:
            rep.add(
                "DOOR_TOO_NARROW",
                f"door {d.id} is {d.width} cm, minimum {DOOR_MIN_WIDTH_CM} cm",
                d.id,
            )
        if d.offset + d.width > wall_length(to, d.wall):
            rep.add(
                "DOOR_TOO_WIDE",
                f"door {d.id} (offset {d.offset} + width {d.width}) runs past the {d.wall} wall "
                f"of {to.id} ({wall_length(to, d.wall)} cm)",
                d.id,
            )
            continue
        hosts = _door_host_interval(plan, d)
        other = d.from_room or "outside"
        if not hosts:
            rep.add(
                "DOOR_NOT_ON_SHARED_WALL",
                f"door {d.id}: the {d.wall} wall of {to.id} does not touch {other}",
                d.id,
            )
            continue
        span = span_interval(door_span(plan, d))
        if not any(interval_within(span, h, OPENING_END_CLEARANCE_CM) for h in hosts):
            longest = max(h[1] - h[0] for h in hosts)
            code = (
                "DOOR_TOO_WIDE"
                if d.width + 2 * OPENING_END_CLEARANCE_CM > longest
                else ("DOOR_NOT_ON_SHARED_WALL")
            )
            rep.add(
                code,
                f"door {d.id} ({d.width} cm at offset {d.offset}) does not fit the "
                f"{longest:.0f} cm wall shared by {to.id} and {other}",
                d.id,
            )


def _check_windows(plan: FloorPlan, rep: ValidationReport) -> None:
    for w in plan.windows:
        room = plan.room(w.room)
        if w.offset + w.width > wall_length(room, w.wall):
            rep.add(
                "WINDOW_NOT_EXTERIOR",
                f"window {w.id} runs past the {w.wall} wall of {room.id}",
                w.id,
            )
            continue
        span = span_interval(window_span(plan, w))
        hosts = exterior_intervals(plan, room, w.wall)
        if not any(interval_within(span, h, OPENING_END_CLEARANCE_CM) for h in hosts):
            rep.add(
                "WINDOW_NOT_EXTERIOR",
                f"window {w.id} on the {w.wall} wall of {room.id} is not on an external wall",
                w.id,
            )


# ------------------------------------------------------------------ circulation


def _touches_plot_edge(plan: FloorPlan, r: Room) -> bool:
    return r.x == 0 or r.y == 0 or r.x2 == plan.plot.width or r.y2 == plan.plot.depth


def door_graph(plan: FloorPlan) -> nx.Graph:
    """Rooms (plus OUTSIDE) connected by doors. Open areas on the plot edge reach OUTSIDE."""
    g = nx.Graph()
    g.add_node(OUTSIDE)
    g.add_nodes_from(r.id for r in plan.rooms)
    for d in plan.doors:
        g.add_edge(d.from_room or OUTSIDE, d.to_room)
    for r in plan.rooms:
        if r.is_open and _touches_plot_edge(plan, r):
            g.add_edge(OUTSIDE, r.id)
    # open areas next to each other are walkable (garden -> pool, deck -> garden)
    opens = [r for r in plan.rooms if r.is_open and r.type != "shaft"]
    for a, b in combinations(opens, 2):
        if any(
            (iv := shared_wall_interval(a, s, b)) and iv[1] - iv[0] >= 90
            for s in ("north", "south", "east", "west")
        ):
            g.add_edge(a.id, b.id)
    return g


def _check_reachability(plan: FloorPlan, rep: ValidationReport) -> None:
    if not plan.rooms:
        return
    reachable = nx.node_connected_component(door_graph(plan), OUTSIDE)
    # The building has an entrance if at least one enclosed room is reachable from outside.
    if not any(n != OUTSIDE and not plan.room(n).is_open for n in reachable):
        rep.add("NO_ENTRANCE", "no door leads into the building from outside or an open area")
    for r in plan.rooms:
        if r.id not in reachable and r.type != "shaft":  # shafts are open-to-sky voids
            rep.add(
                "UNREACHABLE", f"{r.id} cannot be reached through doors from the entrance", r.id
            )


def _check_pool_layout(plan: FloorPlan, program: RoomProgram, rep: ValidationReport) -> None:
    """The pool really sits where the program asked (middle, U, between two blocks)."""
    layout = program.pool_layout
    pool = next((r for r in plan.rooms if r.type == "pool"), None)
    if not is_special(layout) or pool is None:
        return
    W, D, road = plan.plot.width, plan.plot.depth, plan.plot.road_side
    rear = {"south": "north", "north": "south", "east": "west", "west": "east"}[road or "south"]
    edges = {
        s
        for s, hit in (
            ("west", pool.x == 0),
            ("east", pool.x2 == W),
            ("north", pool.y == 0),
            ("south", pool.y2 == D),
        )
        if hit
    }
    enclosed = [r for r in plan.rooms if not r.is_open]

    def has_room(side: str) -> bool:
        """Rooms line at least LINED_SHARE of this side (5 % tolerance for rounding)."""
        lined = sum(iv[1] - iv[0] for r in enclosed if (iv := shared_wall_interval(pool, side, r)))
        length = pool.w if side in ("north", "south") else pool.h
        return lined >= (LINED_SHARE - 0.05) * length

    name = POOL_LAYOUT_NAMES[layout]
    sides = ("north", "south", "east", "west")
    if layout == "centre":
        if edges:
            rep.add("POOL_LAYOUT", f"{name}: the pool touches the plot edge", pool.id)
        missing = [s for s in sides if not has_room(s)]
    elif layout == "u_shape":
        if edges != {rear}:
            rep.add("POOL_LAYOUT", f"{name}: the pool must touch only the rear edge", pool.id)
        missing = [s for s in sides if s != rear and not has_room(s)]
    else:  # two_block: every main room on one side of the pool, every guest room across
        by_id = {r.id: r for r in plan.rooms}
        blocks = {p.id: p.block for p in program.rooms if p.block in ("main", "guest")}
        pd0, pd1, pa0, pa1 = rect_frame(pool.x, pool.y, pool.x2, pool.y2, W, D, road)
        frames = {
            rid: rect_frame(by_id[rid].x, by_id[rid].y, by_id[rid].x2, by_id[rid].y2, W, D, road)
            for rid in blocks
            if rid in by_id and not by_id[rid].is_open
        }
        if program.pool_axis == "side_by_side":
            ok = any(
                all(
                    (f[3] <= pa0) == (blocks[rid] == main_side)
                    and (f[2] >= pa1) == (blocks[rid] != main_side)
                    for rid, f in frames.items()
                )
                for main_side in ("main", "guest")
            )
        else:
            ok = all(
                f[1] <= pd0 if blocks[rid] == "main" else f[0] >= pd1 for rid, f in frames.items()
            )
        if not ok:
            rep.add("POOL_LAYOUT", f"{name}: a room is on the wrong side of the pool", pool.id)
        missing = []
    if missing:
        rep.add(
            "POOL_LAYOUT",
            f"{name}: the pool's {', '.join(missing)} side is not lined by rooms",
            pool.id,
        )


def _check_fixtures(plan: FloorPlan, rep: ValidationReport) -> None:
    for f in plan.fixtures:
        room = plan.room(f.room)
        fw, fd = footprint(f.symbol, f.rotation)
        fp = box(f.x - fw / 2, f.y - fd / 2, f.x + fw / 2, f.y + fd / 2)
        if not box(0, 0, room.w, room.h).buffer(0.5).contains(fp):
            rep.add(
                "FIXTURE_OUTSIDE_ROOM", f"fixture {f.id} ({f.symbol}) sticks out of {room.id}", f.id
            )


# ---------------------------------------------------------------------- program


def _has_direct_door(plan: FloorPlan, a: str, b: str) -> bool:
    return any({d.from_room, d.to_room} == {a, b} for d in plan.doors)


def _check_program(plan: FloorPlan, program: RoomProgram, rep: ValidationReport) -> None:
    by_id = {r.id: r for r in plan.rooms}
    for pr in program.rooms:
        room = by_id.get(pr.id)
        if room is None:
            rep.add(
                "PROGRAM_MISSING_ROOM", f"{pr.id} ({pr.type}) from the program is missing", pr.id
            )
            continue
        if room.type != pr.type:
            rep.add(
                "PROGRAM_TYPE_MISMATCH", f"{pr.id} is a {room.type}, program says {pr.type}", pr.id
            )
        lo, hi = (
            pr.target_area_m2 * (1 - ROOM_AREA_TOLERANCE),
            pr.target_area_m2 * (1 + ROOM_AREA_TOLERANCE),
        )
        flexible = pr.type in AREA_FLEXIBLE_TYPES  # absorbs leftover space: minimum only
        if pr.type in OPEN_AREA_CAP:  # parking/courtyard: may grow, but not take the plot
            flexible, hi = False, pr.target_area_m2 * OPEN_AREA_CAP[pr.type] * 1.05
        if room.area_m2 < lo or (not flexible and room.area_m2 > hi):
            allowed = f"at least {lo:.1f}" if flexible else f"{lo:.1f}-{hi:.1f}"
            rep.add(
                "AREA_MISMATCH",
                f"{pr.id} is {room.area_m2:.1f} m2, target {pr.target_area_m2:.1f} m2 "
                f"(allowed {allowed})",
                pr.id,
            )
        if (
            pr.attached_to
            and pr.attached_to in by_id
            and not _has_direct_door(plan, pr.id, pr.attached_to)
        ):
            rep.add(
                "ATTACHED_BATH",
                f"{pr.id} must open directly into {pr.attached_to} but has no door between them",
                pr.id,
                pr.attached_to,
            )
    program_ids = {p.id for p in program.rooms}
    for r in plan.rooms:
        if r.id not in program_ids and r.type not in ("lobby", "passage", "foyer", "shaft"):
            rep.add("EXTRA_ROOM", f"{r.id} is not in the program", r.id, warning=True)

    fixed_size = [p for p in program.rooms if p.type not in AREA_FLEXIBLE_TYPES]
    target = sum(p.target_area_m2 for p in fixed_size)
    actual = sum(by_id[p.id].area_m2 for p in fixed_size if p.id in by_id)
    if target and abs(actual - target) / target > TOTAL_AREA_TOLERANCE:
        # rooms sized up to a built-up target that the plot cannot quite hold: each room is
        # still above its minimum, so a smaller house is a coverage warning, not a failure
        short_of_target = actual < target and plan.plot.built_up_m2 is not None
        rep.add(
            "TOTAL_AREA_MISMATCH",
            f"program rooms total {actual:.1f} m2, target {target:.1f} m2 "
            f"(+/-{TOTAL_AREA_TOLERANCE:.0%})",
            warning=short_of_target,
        )


# --------------------------------------------------------------------- warnings


def _check_wet_cluster(plan: FloorPlan, rep: ValidationReport) -> None:
    wet = [r for r in plan.rooms if r.type in WET_TYPES]
    if len(wet) < 2:
        return
    for r in wet:
        near = any(o.id != r.id and room_box(r).buffer(1).intersects(room_box(o)) for o in wet)
        if not near:
            rep.add(
                "WET_NOT_CLUSTERED",
                f"{r.id} does not share a wall with another wet room (plumbing runs longer)",
                r.id,
                warning=True,
            )


def _check_shafts(plan: FloorPlan, rep: ValidationReport) -> None:
    # shafts joined to the garden/pool read as part of it, not as leftover holes
    shafts = [r for r in plan.rooms if r.type == "shaft" and not r.part_of]
    total = sum(r.area_m2 for r in shafts)
    if total > SHAFT_WARN_M2:
        rep.add(
            "LARGE_SHAFTS",
            f"{len(shafts)} leftover open shaft(s) total {total:.1f} m2",
            *(r.id for r in shafts),
            warning=True,
        )


def _check_coverage(plan: FloorPlan, rep: ValidationReport) -> None:
    if plan.plot.has_setbacks:
        return  # the setback strips are exterior paving, not unused plot (see _check_setbacks)
    plot_area = plan.plot.width * plan.plot.depth
    covered = (
        unary_union([room_box(r) for r in plan.rooms])
        .intersection(box(0, 0, plan.plot.width, plan.plot.depth))
        .area
        if plan.rooms
        else 0
    )
    if covered / plot_area < MIN_PLOT_COVERAGE:
        rep.add(
            "PLOT_GAPS",
            f"rooms cover {covered / plot_area:.0%} of the plot; "
            f"{(plot_area - covered) / 10_000:.1f} m2 unused",
            warning=True,
        )
