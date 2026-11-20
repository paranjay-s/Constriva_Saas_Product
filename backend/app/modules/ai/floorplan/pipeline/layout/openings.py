"""Place doors and windows on a room layout (code, never the LLM).

Doors follow the circulation topology: each room gets one door on the wall it shares
with its parent, plus an entrance door on the road side of the root room. Windows go
on external walls (plot edge or open area), clear of corners and of doors on the
same wall line.
"""

from app.modules.ai.floorplan.geometry import (
    Interval,
    door_span,
    exterior_intervals,
    shared_wall_interval,
    wall_line,
)
from app.modules.ai.floorplan.pipeline.layout.topology import (
    ENTRANCE_DOOR_CM,
    Topology,
    door_width,
)
from app.modules.ai.floorplan.rules import DOOR_MIN_WIDTH_CM, OPENING_END_CLEARANCE_CM
from app.modules.ai.floorplan.schemas.plan import Door, FloorPlan, Room, Window

SIDES = ("north", "south", "east", "west")
PUBLIC_OPEN_PAIRS = {"living", "dining", "family_hall"}
CLEAR = OPENING_END_CLEARANCE_CM + 3

# room type -> (preferred window width cm, max number of windows)
WINDOW_SPEC: dict[str, tuple[int, int]] = {
    "master_bedroom": (150, 2),
    "bedroom": (150, 2),
    "living": (180, 2),
    "family_hall": (180, 2),
    "dining": (140, 1),
    "kitchen": (120, 1),
    "study": (120, 1),
    "maid_room": (90, 1),
    "driver_room": (90, 1),
    "majlis": (180, 2),
    "bar": (120, 1),
    "gym": (150, 2),
    "prayer": (90, 1),
    "puja": (60, 1),
    "bath": (60, 1),
    "toilet": (60, 1),
    "utility": (60, 1),
    "lobby": (90, 1),
    "passage": (90, 1),
    "foyer": (90, 1),
}


def _wall_start(room: Room, wall: str) -> int:
    (x1, y1), _ = wall_line(room, wall)
    return x1 if wall in ("north", "south") else y1


def place_doors(plan: FloorPlan, topo: Topology, road_side: str | None) -> list[Door]:
    rooms = {r.id: r for r in plan.rooms}
    doors: list[Door] = []

    root = rooms[topo.root]
    entrance = _entrance(plan, root, road_side or "south")
    if entrance:
        doors.append(entrance)

    for child_id, parent_id in topo.parent.items():
        if parent_id is None or child_id not in rooms or parent_id not in rooms:
            continue
        child, par = rooms[child_id], rooms[parent_id]
        best: tuple[float, str, Interval] | None = None
        for wall in SIDES:
            iv = shared_wall_interval(child, wall, par)
            if iv and (best is None or iv[1] - iv[0] > best[0]):
                best = (iv[1] - iv[0], wall, iv)
        if best is None:
            continue  # validator reports UNREACHABLE
        length, wall, iv = best
        open_pair = child.type in PUBLIC_OPEN_PAIRS and par.type in PUBLIC_OPEN_PAIRS
        width = min(150, int(length - 2 * CLEAR)) if open_pair else door_width(child.type)
        width = min(width, int(length - 2 * CLEAR))
        if width < DOOR_MIN_WIDTH_CM:
            continue
        offset = int(iv[0] + CLEAR) - _wall_start(child, wall)
        if child.is_open:
            swing = "out-left"  # door to a courtyard opens into the house side
        elif open_pair and width >= 110:
            swing = "none"
        else:
            swing = "in-left"
        doors.append(
            Door(
                id=f"d{len(doors) + 1}",
                from_room=par.id,
                to_room=child.id,
                wall=wall,
                offset=offset,
                width=width,
                swing=swing,
            )
        )
    return doors


def _entrance(plan: FloorPlan, root: Room, road_side: str) -> Door | None:
    order = [road_side] + [s for s in SIDES if s != road_side]
    for wall in order:
        ivs = exterior_intervals(plan, root, wall)
        if not ivs:
            continue
        iv = max(ivs, key=lambda i: i[1] - i[0])
        length = iv[1] - iv[0]
        width = min(ENTRANCE_DOOR_CM, int(length - 2 * CLEAR))
        if width < DOOR_MIN_WIDTH_CM:
            continue
        offset = int(iv[0] + (length - width) / 2) - _wall_start(root, wall)
        return Door(
            id="d1",
            from_room=None,
            to_room=root.id,
            wall=wall,
            offset=offset,
            width=width,
            swing="in-left",
        )
    return None


def _door_spans_on_line(plan: FloorPlan, horizontal: bool, coord: float) -> list[Interval]:
    out = []
    for d in plan.doors:
        sp = door_span(plan, d)
        if sp.horizontal != horizontal:
            continue
        line = sp.start[1] if horizontal else sp.start[0]
        if abs(line - coord) > 0.5:
            continue
        i = 0 if horizontal else 1
        out.append((min(sp.start[i], sp.end[i]), max(sp.start[i], sp.end[i])))
    return out


def _subtract(iv: Interval, cuts: list[Interval], margin: float) -> list[Interval]:
    pieces = [iv]
    for a, b in cuts:
        a, b = a - margin, b + margin
        nxt = []
        for lo, hi in pieces:
            if b <= lo or a >= hi:
                nxt.append((lo, hi))
                continue
            if a > lo:
                nxt.append((lo, a))
            if b < hi:
                nxt.append((b, hi))
        pieces = nxt
    return pieces


def place_windows(plan: FloorPlan) -> list[Window]:
    windows: list[Window] = []
    for room in plan.rooms:
        spec = WINDOW_SPEC.get(room.type)
        if spec is None or room.is_open:
            continue
        pref, count = spec
        candidates: list[tuple[float, str, Interval]] = []
        for wall in SIDES:
            horizontal = wall in ("north", "south")
            (x1, y1), _ = wall_line(room, wall)
            coord = y1 if horizontal else x1
            doors_here = _door_spans_on_line(plan, horizontal, coord)
            for iv in exterior_intervals(plan, room, wall):
                for piece in _subtract(iv, doors_here, margin=20):
                    candidates.append((piece[1] - piece[0], wall, piece))
        candidates.sort(key=lambda c: (-c[0], c[1]))
        used_walls: set[str] = set()
        for length, wall, (lo, _hi) in candidates:
            if len(used_walls) >= count or wall in used_walls:
                continue
            width = int(min(pref, length - 2 * (CLEAR + 5)))
            if width < 50:
                continue
            offset = int(lo + (length - width) / 2) - _wall_start(room, wall)
            windows.append(
                Window(
                    id=f"w{len(windows) + 1}", room=room.id, wall=wall, offset=offset, width=width
                )
            )
            used_walls.add(wall)
    return windows
