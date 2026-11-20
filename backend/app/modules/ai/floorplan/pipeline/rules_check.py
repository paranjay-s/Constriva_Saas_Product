"""Layout rules on a finished plan: add the doors they ask for, and check every rule.

`add_rule_doors` runs after the solver (doors are placed by code, never by the LLM).
`rule_problems` returns one message per broken rule; the validator turns them into
RULE errors, so no plan that breaks a rule is delivered as valid.
"""

from app.modules.ai.floorplan.pipeline.layout.topology import door_width
from app.modules.ai.floorplan.schemas.edit_ops import AddDoor
from app.modules.ai.floorplan.schemas.plan import FloorPlan, Room
from app.modules.ai.floorplan.schemas.program import RoomProgram
from app.modules.ai.floorplan.schemas.rules import (
    Daylight,
    DoorBetween,
    Place,
    SizeRule,
    Touches,
    describe_rule,
)

OUTDOOR_DOOR_CM = 150  # a door onto a pool, deck or garden: a sliding door this wide
MIN_SHARED_CM = 90
FRAME = {  # road side -> compass side of front, rear, left, right
    "south": ("south", "north", "west", "east"),
    "north": ("north", "south", "east", "west"),
    "east": ("east", "west", "south", "north"),
    "west": ("west", "east", "north", "south"),
}


def shared_len(a: Room, b: Room) -> int:
    if a.x2 == b.x or b.x2 == a.x:
        return max(0, min(a.y2, b.y2) - max(a.y, b.y))
    if a.y2 == b.y or b.y2 == a.y:
        return max(0, min(a.x2, b.x2) - max(a.x, b.x))
    return 0


def has_door(plan: FloorPlan, a: str, b: str) -> bool:
    return any({d.to_room, d.from_room} == {a, b} for d in plan.doors)


def door_pairs(program: RoomProgram) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for rl in program.rules:
        if isinstance(rl, Touches) and rl.door:
            pairs += [(rl.room, o) for o in rl.others]
        elif isinstance(rl, DoorBetween):
            pairs.append((rl.a, rl.b))
    return pairs


def add_rule_doors(plan: FloorPlan, program: RoomProgram) -> FloorPlan:
    """A door for every pair a rule joins with a door, when the pair has none yet. The
    door hangs in the enclosed room's wall; onto an outdoor area it is 1.5 m wide."""
    from app.modules.ai.floorplan.pipeline.plan_tools import ToolError, add_door

    rooms = {r.id: r for r in plan.rooms}
    for a, b in door_pairs(program):
        if a not in rooms or b not in rooms or has_door(plan, a, b):
            continue
        ra, rb = rooms[a], rooms[b]
        inner, other = (ra, rb) if not ra.is_open else (rb, ra)
        width = OUTDOOR_DOOR_CM if other.is_open else door_width(inner.type)
        try:
            plan, _, _ = add_door(
                plan,
                program,
                AddDoor(op="add_door", room=inner.id, to=other.id, width=width),
            )
        except ToolError:
            continue  # the rule check below reports the missing door
    return plan


def rule_problems(plan: FloorPlan, program: RoomProgram) -> list[tuple[str, list[str]]]:
    """(message, room ids) for every rule the plan breaks."""
    rooms = {r.id: r for r in plan.rooms}
    names = {r.id: r.label for r in plan.rooms}
    road = plan.plot.road_side or "south"
    out: list[tuple[str, list[str]]] = []

    def bad(rule, why: str, *ids: str) -> None:
        out.append((f"{describe_rule(rule, names)}: {why}", list(ids)))

    for rl in program.rules:
        if isinstance(rl, Touches | DoorBetween):
            pairs = (
                [(rl.room, o) for o in rl.others]
                if isinstance(rl, Touches)
                else [(rl.a, rl.b)]
            )
            needs_door = isinstance(rl, DoorBetween) or rl.door
            for a, b in pairs:
                if a not in rooms or b not in rooms:
                    bad(rl, "a room it names is missing", a, b)
                elif shared_len(rooms[a], rooms[b]) < MIN_SHARED_CM:
                    bad(rl, f"{names[a]} and {names[b]} do not share a wall", a, b)
                elif needs_door and not has_door(plan, a, b):
                    bad(rl, f"no door between {names[a]} and {names[b]}", a, b)
        elif isinstance(rl, Place) and rl.room in rooms:
            r = rooms[rl.room]
            cx, cy = r.x + r.w / 2, r.y + r.h / 2
            W, D = plan.plot.width, plan.plot.depth
            if rl.side == "centre":
                ok = W / 3 <= cx <= 2 * W / 3 and D / 3 <= cy <= 2 * D / 3
            else:
                side = dict(zip(("front", "rear", "left", "right"), FRAME[road], strict=True))[
                    rl.side
                ]
                ok = {
                    "south": cy > D / 2,
                    "north": cy < D / 2,
                    "east": cx > W / 2,
                    "west": cx < W / 2,
                }[side]
            if not ok:
                bad(rl, f"{names[r.id]} is not at the {rl.side}", r.id)
        elif isinstance(rl, SizeRule) and rl.room in rooms:
            r = rooms[rl.room]
            short, long_ = min(r.w, r.h), max(r.w, r.h)
            if rl.min_area_m2 and r.area_m2 < rl.min_area_m2 * 0.97:
                bad(rl, f"it is {r.area_m2:.1f} m²", r.id)
            if rl.max_area_m2 and r.area_m2 > rl.max_area_m2 * 1.03:
                bad(rl, f"it is {r.area_m2:.1f} m²", r.id)
            if rl.min_width_cm and short < rl.min_width_cm - 15:
                bad(rl, f"it is {short / 100:.2f} m wide", r.id)
            if rl.max_width_cm and short > rl.max_width_cm + 15:
                bad(rl, f"it is {short / 100:.2f} m wide", r.id)
            if rl.max_aspect and long_ / short > rl.max_aspect * 1.05:
                bad(rl, f"its sides are {long_ / short:.1f} to 1", r.id)
        elif isinstance(rl, Daylight) and rl.room in rooms:
            r = rooms[rl.room]
            x0, y0, x1, y1 = plan.plot.buildable()
            on_edge = r.x <= x0 or r.y <= y0 or r.x2 >= x1 or r.y2 >= y1
            onto_open = any(
                o.is_open and shared_len(r, o) >= 100 for o in plan.rooms if o.id != r.id
            )
            if not (on_edge or onto_open):
                bad(rl, f"{names[r.id]} has no outside wall", r.id)
    return out
