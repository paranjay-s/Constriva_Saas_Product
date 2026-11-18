"""Edit tools that do not re-plan the layout: turn / mirror the whole house, doors,
windows, room use and display units.

    plan, program, note = apply_tool(plan, program, op)

Whole-plan transforms (facing, rotate, mirror) are exact: every room, door, window and
piece of furniture is moved with the same transform, so the layout the person already
approved (including all earlier edits) is kept; only its orientation changes. The other
tools touch one element and raise EditError with a plain reason when it cannot be done.
Every result is checked by the validator in edit_engine.apply_edit.
"""

from collections.abc import Callable

from app.modules.ai.floorplan.geometry import (
    exterior_intervals,
    shared_wall_interval,
    span_interval,
    wall_line,
    window_span,
)
from app.modules.ai.floorplan.pipeline.layout.fixtures import place_fixtures
from app.modules.ai.floorplan.pipeline.layout.openings import (
    CLEAR,
    _door_spans_on_line,
    _subtract,
)
from app.modules.ai.floorplan.pipeline.layout.topology import ENTRANCE_DOOR_CM, door_width
from app.modules.ai.floorplan.pipeline.validator import validate
from app.modules.ai.floorplan.rules import DOOR_MIN_WIDTH_CM
from app.modules.ai.floorplan.schemas.common import DEFAULT_LABEL, ZONE_BY_TYPE
from app.modules.ai.floorplan.schemas.edit_ops import (
    AddDoor,
    ChangeRoomType,
    MirrorPlan,
    RemoveDoor,
    RemoveWindow,
    RotatePlan,
    SetDoorWidth,
    SetFacing,
    SetUnits,
    SetWindowWidth,
)
from app.modules.ai.floorplan.schemas.plan import Door, Fixture, FloorPlan, Room, Window
from app.modules.ai.floorplan.schemas.program import RoomProgram
from app.modules.ai.floorplan.units import fmt_length


class ToolError(Exception):
    """The tool cannot do this; the message says why, alternatives say what to try."""

    def __init__(self, message: str, alternatives: list[str] | None = None) -> None:
        super().__init__(message)
        self.alternatives = alternatives or []


SIDES = ("north", "east", "south", "west")  # clockwise order
MAX_WINDOW_CM = 240
MAX_DOOR_CM = 240
UNIT_NAMES = {"ft": "feet and inches", "m": "metres", "cm": "centimetres"}

Result = tuple[FloorPlan, RoomProgram, str]


# ============================================================ facing / rotate / mirror

Kind = int | str  # 90 / 180 / 270 (clockwise) or "left_right" / "top_bottom"


def side_map(kind: Kind) -> dict[str, str]:
    if kind in ("left_right", "top_bottom"):
        swap = ("east", "west") if kind == "left_right" else ("north", "south")
        return {s: (swap[1] if s == swap[0] else swap[0] if s == swap[1] else s) for s in SIDES}
    steps = int(kind) // 90
    return {s: SIDES[(i + steps) % 4] for i, s in enumerate(SIDES)}


def _point_fn(kind: Kind, w: int, d: int) -> tuple[Callable[[int, int], tuple[int, int]], int, int]:
    """Point transform in plot coordinates (x east, y south) and the new plot size."""
    if kind == 90:
        return (lambda x, y: (d - y, x)), d, w
    if kind == 180:
        return (lambda x, y: (w - x, d - y)), w, d
    if kind == 270:
        return (lambda x, y: (y, w - x)), d, w
    if kind == "left_right":
        return (lambda x, y: (w - x, y)), w, d
    return (lambda x, y: (x, d - y)), w, d


def _rotation_fn(kind: Kind) -> Callable[[int], int]:
    if kind == "left_right":
        return lambda r: (-r) % 360
    if kind == "top_bottom":
        return lambda r: (180 - r) % 360
    return lambda r: (r + int(kind)) % 360


def facing(plan: FloorPlan) -> str | None:
    """The side the house faces: the road side, else the wall of the main entrance."""
    if plan.plot.road_side:
        return plan.plot.road_side
    for d in plan.doors:
        if d.from_room is None:
            return d.wall
    return None


def transform_plan(plan: FloorPlan, kind: Kind) -> FloorPlan:
    """The same plan turned clockwise by 90/180/270 degrees or mirrored. Exact: integer
    coordinates, every opening and fixture stays where it was relative to its room."""
    pt, new_w, new_d = _point_fn(kind, plan.plot.width, plan.plot.depth)
    sides = side_map(kind)
    rot = _rotation_fn(kind)

    rooms: dict[str, Room] = {}
    for r in plan.rooms:
        (ax, ay), (bx, by) = pt(r.x, r.y), pt(r.x2, r.y2)
        rooms[r.id] = r.model_copy(
            update={"x": min(ax, bx), "y": min(ay, by), "w": abs(bx - ax), "h": abs(by - ay)}
        )

    def moved_opening(room_id: str, wall: str, offset: int, width: int):
        (sx, sy), _ = wall_line(plan.room(room_id), wall)
        horizontal = wall in ("north", "south")
        p0 = (sx + offset, sy) if horizontal else (sx, sy + offset)
        p1 = (p0[0] + width, p0[1]) if horizontal else (p0[0], p0[1] + width)
        q0, q1 = pt(*p0), pt(*p1)
        new_wall = sides[wall]
        new_room = rooms[room_id]
        along = 0 if new_wall in ("north", "south") else 1
        start = min(q0[along], q1[along])
        base = new_room.x if along == 0 else new_room.y
        return new_wall, int(start - base), p0, p1, q0, q1

    doors = []
    for d in plan.doors:
        wall, offset, p0, p1, q0, q1 = moved_opening(d.to_room, d.wall, d.offset, d.width)
        swing = d.swing
        if swing != "none":
            into, side = swing.split("-")
            hinge = pt(*(p0 if side == "left" else p1))
            new_start = min(q0, q1)
            swing = f"{into}-{'left' if hinge == new_start else 'right'}"
        doors.append(d.model_copy(update={"wall": wall, "offset": offset, "swing": swing}))

    windows = []
    for w in plan.windows:
        wall, offset, *_ = moved_opening(w.room, w.wall, w.offset, w.width)
        windows.append(w.model_copy(update={"wall": wall, "offset": offset}))

    fixtures = []
    for f in plan.fixtures:
        old_room = plan.room(f.room)
        cx, cy = pt(old_room.x + f.x, old_room.y + f.y)
        new_room = rooms[f.room]
        fixtures.append(
            f.model_copy(
                update={"x": cx - new_room.x, "y": cy - new_room.y, "rotation": rot(f.rotation)}
            )
        )

    road = plan.plot.road_side
    plot = plan.plot.model_copy(
        update={"width": new_w, "depth": new_d, "road_side": sides[road] if road else None}
    )
    data = plan.model_copy(
        update={
            "plot": plot,
            "rooms": [rooms[r.id] for r in plan.rooms],
            "doors": doors,
            "windows": windows,
            "fixtures": fixtures,
        }
    ).model_dump(by_alias=True)
    return FloorPlan.model_validate(data)


def transform_program(program: RoomProgram, kind: Kind) -> RoomProgram:
    if not program.entrance_side:
        return program
    return program.model_copy(update={"entrance_side": side_map(kind)[program.entrance_side]})


def _turn(plan: FloorPlan, program: RoomProgram, kind: Kind, what: str) -> Result:
    new = transform_plan(plan, kind)
    before, after = facing(plan), facing(new)
    note = what
    if after and after != before:
        note += f" The house now faces {after} (main entrance on the {after} side)."
    unit = new.meta.unit_display
    note += (
        f" Plot: {fmt_length(new.plot.width, unit)} east-west x "
        f"{fmt_length(new.plot.depth, unit)} north-south. Every room, door, window and "
        "piece of furniture moved with it, so the layout and room sizes are unchanged."
    )
    return new, transform_program(program, kind), note


def set_facing(plan: FloorPlan, program: RoomProgram, op: SetFacing) -> Result:
    current = facing(plan)
    if current is None:
        raise ToolError(
            "This plan has no road side or main entrance yet, so its facing is not known.",
            ["Turn it instead: 'rotate the plan 90 degrees clockwise'."],
        )
    if current == op.side:
        raise ToolError(f"The house already faces {op.side}.")
    steps = (SIDES.index(op.side) - SIDES.index(current)) % 4
    return _turn(
        plan,
        program,
        steps * 90,
        f"Turned the house from {current}-facing to {op.side}-facing.",
    )


def rotate(plan: FloorPlan, program: RoomProgram, op: RotatePlan) -> Result:
    return _turn(plan, program, op.degrees, f"Rotated the plan {op.degrees} degrees clockwise.")


def mirror(plan: FloorPlan, program: RoomProgram, op: MirrorPlan) -> Result:
    words = (
        "left to right (east and west swapped)"
        if op.axis == "left_right"
        else ("top to bottom (north and south swapped)")
    )
    return _turn(plan, program, op.axis, f"Mirrored the plan {words}.")


# ===================================================================== doors


def _door(plan: FloorPlan, door_id: str) -> Door:
    door = next((d for d in plan.doors if d.id == door_id), None)
    if door is None:
        raise ToolError(f"There is no door {door_id}.")
    return door


def _room(plan: FloorPlan, room_id: str) -> Room:
    try:
        return plan.room(room_id)
    except KeyError:
        raise ToolError(f"There is no room {room_id}.") from None


def _wall_start(room: Room, wall: str) -> int:
    return room.x if wall in ("north", "south") else room.y


def _taken_on_line(plan: FloorPlan, room: Room, wall: str, skip: str | None = None):
    """Door and window spans already on the line of this wall (except `skip`)."""
    horizontal = wall in ("north", "south")
    (x1, y1), _ = wall_line(room, wall)
    coord = y1 if horizontal else x1
    without = plan
    if skip:
        without = plan.model_copy(
            update={
                "doors": [d for d in plan.doors if d.id != skip],
                "windows": [w for w in plan.windows if w.id != skip],
            }
        )
    taken = _door_spans_on_line(without, horizontal, coord)
    for w in without.windows:
        span = window_span(without, w)
        if span.horizontal == horizontal:
            line = span.start[1] if horizontal else span.start[0]
            if abs(line - coord) <= 0.5:
                taken.append(span_interval(span))
    return taken


def _host_intervals(plan: FloorPlan, room: Room, wall: str, other: Room | None):
    if other is None:
        return exterior_intervals(plan, room, wall)
    iv = shared_wall_interval(room, wall, other)
    return [iv] if iv else []


def _check(plan: FloorPlan, program: RoomProgram, codes_to_explain: dict[str, str]) -> None:
    rep = validate(plan, program)
    for code, text in codes_to_explain.items():
        if code in rep.codes():
            ids = sorted({i for issue in rep.errors if issue.code == code for i in issue.ids})
            names = ", ".join(plan.room(i).label for i in ids if i in {r.id for r in plan.rooms})
            raise ToolError(text.format(names=names or "a room"))


def add_door(plan: FloorPlan, program: RoomProgram, op: AddDoor) -> Result:
    unit = plan.meta.unit_display
    room = _room(plan, op.room)
    outside = op.to.strip().lower() in ("outside", "exterior", "none", "")
    other = None if outside else _room(plan, op.to)
    if other is not None and other.id == room.id:
        raise ToolError("A door needs two different rooms.")
    for d in plan.doors:
        pair = {d.to_room, d.from_room}
        if other is not None and pair == {room.id, other.id}:
            raise ToolError(
                f"{room.label} and {other.label} already have a door between them ({d.id}).",
                [
                    f"Move it ('move the door between {room.label} and {other.label} to the ... "
                    "wall') or make it wider."
                ],
            )
    width = op.width or (ENTRANCE_DOOR_CM if outside else door_width(room.type))
    walls = [op.wall] if op.wall else list(SIDES)
    best = None
    for wall in walls:
        for iv in _host_intervals(plan, room, wall, other):
            for lo, hi in _subtract(iv, _taken_on_line(plan, room, wall), margin=20):
                room_len = hi - lo - 2 * CLEAR
                if room_len >= DOOR_MIN_WIDTH_CM and (best is None or room_len > best[0]):
                    best = (room_len, wall, lo, hi)
    where = "outside" if other is None else other.label
    if best is None:
        if op.wall:
            raise ToolError(
                f"The {op.wall} wall of {room.label} has no free stretch next to {where} "
                "for a door.",
                ["Leave the wall out and I will use the best wall that touches it."],
            )
        raise ToolError(
            f"{room.label} does not share a wall with {where} that has space for a door.",
            [f"Move {room.label} next to {where} first."],
        )
    room_len, wall, lo, hi = best
    used_width = int(min(width, room_len))
    offset = round((lo + hi - used_width) / 2) - _wall_start(room, wall)
    used = {o.id for o in (*plan.rooms, *plan.doors, *plan.windows, *plan.fixtures)}
    n = 1
    while f"d{n}" in used:
        n += 1
    door = Door(
        id=f"d{n}",
        from_room=None if other is None else other.id,
        to_room=room.id,
        wall=wall,
        offset=int(offset),
        width=used_width,
        swing="out-left" if room.is_open else "in-left",
    )
    new = _with(plan, doors=[*plan.doors, door])
    new = _refit_fixtures(new, room.id)
    note = (
        f"Added a {fmt_length(used_width, unit)} door from {where} into {room.label} "
        f"on its {wall} wall."
    )
    if width - used_width >= 3:
        note += f" ({fmt_length(width, unit)} did not fit; this is the widest that does.)"
    return new, program, note


def remove_door(plan: FloorPlan, program: RoomProgram, op: RemoveDoor) -> Result:
    door = _door(plan, op.id)
    new = _with(plan, doors=[d for d in plan.doors if d.id != door.id])
    _check(
        new,
        program,
        {
            "UNREACHABLE": "Without that door {names} would have no way in. Add another door "
            "first, then remove this one.",
        },
    )
    to = plan.room(door.to_room).label
    frm = plan.room(door.from_room).label if door.from_room else "outside"
    if door.from_room is None and not any(d.from_room is None for d in new.doors):
        raise ToolError("That is the only entrance to the house; it cannot be removed.")
    return _refit_fixtures(new, door.to_room), program, f"Removed the door between {frm} and {to}."


def set_door_width(plan: FloorPlan, program: RoomProgram, op: SetDoorWidth) -> Result:
    unit = plan.meta.unit_display
    door = _door(plan, op.id)
    if op.width < DOOR_MIN_WIDTH_CM:
        raise ToolError(
            f"A door narrower than {fmt_length(DOOR_MIN_WIDTH_CM, unit)} is not practical "
            "(furniture and people need to pass).",
            [f"Use at least {fmt_length(DOOR_MIN_WIDTH_CM, unit)}."],
        )
    room = plan.room(door.to_room)
    other = plan.room(door.from_room) if door.from_room else None
    start = _wall_start(room, door.wall)
    centre = start + door.offset + door.width / 2
    slot = None
    for iv in _host_intervals(plan, room, door.wall, other):
        for lo, hi in _subtract(iv, _taken_on_line(plan, room, door.wall, skip=door.id), margin=20):
            if lo <= centre <= hi:
                slot = (lo + CLEAR, hi - CLEAR)
    if slot is None:
        raise ToolError("The wall around that door has no free space.")
    width = int(min(op.width, MAX_DOOR_CM, slot[1] - slot[0]))
    if width <= door.width and op.width > door.width:
        raise ToolError(
            f"That door is already as wide as its wall allows ({fmt_length(door.width, unit)}).",
            [f"Make {room.label} longer on that side first."],
        )
    lo = min(max(centre - width / 2, slot[0]), slot[1] - width)
    swing = door.swing
    if (
        width >= 110
        and room.type in ("living", "dining", "family_hall")
        and other
        and (other.type in ("living", "dining", "family_hall"))
    ):
        swing = "none"  # a wide opening between public rooms
    doors = [
        d.model_copy(update={"width": width, "offset": int(round(lo - start)), "swing": swing})
        if d.id == door.id
        else d
        for d in plan.doors
    ]
    new = _refit_fixtures(_with(plan, doors=doors), room.id)
    note = (
        f"Door {door.id} ({room.label}) is now {fmt_length(width, unit)} wide "
        f"(was {fmt_length(door.width, unit)})."
    )
    if op.width - width >= 3:  # a cm or two short is rounding, not a limit
        note += " That is the widest that fits there."
    return new, program, note


# =================================================================== windows


def _window(plan: FloorPlan, window_id: str) -> Window:
    w = next((w for w in plan.windows if w.id == window_id), None)
    if w is None:
        raise ToolError(f"There is no window {window_id}.")
    return w


def remove_window(plan: FloorPlan, program: RoomProgram, op: RemoveWindow) -> Result:
    win = _window(plan, op.id)
    room = plan.room(win.room)
    new = _with(plan, windows=[w for w in plan.windows if w.id != win.id])
    note = f"Removed the window on the {win.wall} wall of {room.label}."
    habitable = room.type in (
        "bedroom",
        "master_bedroom",
        "living",
        "family_hall",
        "dining",
        "kitchen",
        "study",
        "maid_room",
    )
    if habitable and not any(w.room == room.id for w in new.windows):
        note += (
            f" {room.label} now has no window: it needs daylight and fresh air, and most "
            "building rules ask for a window in a habitable room."
        )
    return new, program, note


def set_window_width(plan: FloorPlan, program: RoomProgram, op: SetWindowWidth) -> Result:
    unit = plan.meta.unit_display
    win = _window(plan, op.id)
    room = plan.room(win.room)
    lo_w, hi_w = span_interval(window_span(plan, win))
    centre = (lo_w + hi_w) / 2
    slot = None
    for iv in exterior_intervals(plan, room, win.wall):
        for lo, hi in _subtract(iv, _taken_on_line(plan, room, win.wall, skip=win.id), margin=20):
            if lo <= centre <= hi:
                slot = (lo + CLEAR, hi - CLEAR)
    if slot is None:
        raise ToolError("The wall around that window has no free space.")
    least = 50
    if op.width < least:
        raise ToolError(f"A window narrower than {fmt_length(least, unit)} gives almost no light.")
    width = int(min(op.width, MAX_WINDOW_CM, slot[1] - slot[0]))
    lo = min(max(centre - width / 2, slot[0]), slot[1] - width)
    start = _wall_start(room, win.wall)
    windows = [
        w.model_copy(update={"width": width, "offset": int(round(lo - start))})
        if w.id == win.id
        else w
        for w in plan.windows
    ]
    note = (
        f"The {win.wall} window of {room.label} is now {fmt_length(width, unit)} wide "
        f"(was {fmt_length(win.width, unit)})."
    )
    if op.width - width >= 3:  # a cm or two short is rounding, not a limit
        note += " That is the widest that fits on that wall."
    return _with(plan, windows=windows), program, note


# ================================================================ room use, units


def change_room_type(plan: FloorPlan, program: RoomProgram, op: ChangeRoomType) -> Result:
    room = _room(plan, op.id)
    if room.type == op.type and not op.label:
        raise ToolError(f"{room.label} is already a {op.type.replace('_', ' ')}.")
    if room.is_open != Room(id="x", type=op.type, label="x", x=0, y=0, w=1, h=1).is_open:
        raise ToolError(
            "An open-air space (garden, courtyard, pool, deck) and a closed room are built "
            "differently, so one cannot simply become the other.",
            [f"Remove {room.label} and add the new room instead."],
        )
    label = (op.label or "").strip().upper()
    if not label:
        base = DEFAULT_LABEL.get(op.type, op.type.replace("_", " ").upper())
        same = [r for r in plan.rooms if r.type == op.type and r.id != room.id]
        label = f"{base} {len(same) + 1}" if same else base
    rooms = [
        r.model_copy(update={"type": op.type, "label": label}) if r.id == room.id else r
        for r in plan.rooms
    ]
    prog_rooms = [
        p.model_copy(update={"type": op.type, "label": label, "zone": ZONE_BY_TYPE[op.type]})
        if p.id == room.id
        else p
        for p in program.rooms
    ]
    new = _refit_fixtures(_with(plan, rooms=rooms), room.id)
    _check(
        new,
        program.model_copy(update={"rooms": prog_rooms}),
        {
            code: "{names} is too small to be used as a "
            + op.type.replace("_", " ")
            + ". Make it bigger first."
            for code in ("MIN_AREA", "MIN_SIDE")
        },
    )
    return (
        new,
        program.model_copy(update={"rooms": prog_rooms}),
        f"{room.label} is now used as {label} (same size and place; furniture refitted).",
    )


def set_units(plan: FloorPlan, program: RoomProgram, op: SetUnits) -> Result:
    if plan.meta.unit_display == op.unit:
        raise ToolError(f"Sizes are already shown in {UNIT_NAMES[op.unit]}.")
    meta = plan.meta.model_copy(update={"unit_display": op.unit})
    return (
        _with(plan, meta=meta),
        program,
        f"Sizes on the drawing are now shown in {UNIT_NAMES[op.unit]}.",
    )


# ================================================================== dispatch

TOOLS = {
    SetFacing: set_facing,
    RotatePlan: rotate,
    MirrorPlan: mirror,
    AddDoor: add_door,
    RemoveDoor: remove_door,
    SetDoorWidth: set_door_width,
    RemoveWindow: remove_window,
    SetWindowWidth: set_window_width,
    ChangeRoomType: change_room_type,
    SetUnits: set_units,
}
TOOL_OPS = tuple(TOOLS)


def apply_tool(plan: FloorPlan, program: RoomProgram, op) -> Result:
    return TOOLS[type(op)](plan, program, op)


# =================================================================== helpers


def _with(plan: FloorPlan, **update) -> FloorPlan:
    return FloorPlan.model_validate(plan.model_copy(update=update).model_dump(by_alias=True))


def _refit_fixtures(plan: FloorPlan, room_id: str) -> FloorPlan:
    """Re-place the furniture of one room (after its use or its doors changed)."""
    fresh = [f for f in place_fixtures(plan) if f.room == room_id]
    keep = [f for f in plan.fixtures if f.room != room_id]
    used = {o.id for o in (*plan.rooms, *plan.doors, *plan.windows, *keep)}
    out: list[Fixture] = list(keep)
    n = 1
    for f in fresh:
        while f"f{n}" in used:
            n += 1
        used.add(f"f{n}")
        out.append(f.model_copy(update={"id": f"f{n}"}))
    return _with(plan, fixtures=out)
