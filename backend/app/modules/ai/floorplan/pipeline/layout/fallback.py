"""Last rung of the relaxation ladder: a deterministic corridor layout that always succeeds.

No search: the plan is cut into strips and slices, so every room gets a rectangle.

    road (front)
    +--------------------------------------------+
    |  front open areas (parking, front garden)  |   front strip, full plot width
    +--------------------+----+------------------+
    | foyer / public     |    | public           |
    |--------------------| c  |------------------|   house block inside the setbacks:
    | service            | o  | service          |   a 1.2 m corridor from the front of
    |--------------------| r  |------------------|   the block to its rear, rooms on both
    | bedroom  | bath    | r  | bedroom | dress  |   sides (one side on narrow plots),
    |          | dress   |    |         | bath   |   public near the road, private behind
    +--------------------+----+------------------+
    |  rear open areas (pool, rear garden)       |   rear strip
    +--------------------------------------------+

Each room opens onto the corridor (its door parent); attached rooms (bath, dress) sit in a
column on the far side of their bedroom and open into it; the corridor (or the foyer at its
front) is the entrance. Slices are scaled so each side of the corridor fills the block;
thin leftovers are absorbed by neighbours or become open shafts (layout.solver.fill_gaps).
The caller validates the result and reports anything that is not right as a note.
"""

from dataclasses import dataclass, field

from app.modules.ai.floorplan.pipeline.layout.grid import Grid
from app.modules.ai.floorplan.pipeline.layout.topology import Topology
from app.modules.ai.floorplan.rules import MIN_ROOM
from app.modules.ai.floorplan.schemas.common import DEFAULT_LABEL, is_open
from app.modules.ai.floorplan.schemas.plan import Plot, Room
from app.modules.ai.floorplan.schemas.program import ProgramRoom, RoomProgram
from app.modules.ai.floorplan.schemas.rules import Place

CORRIDOR_CM = 120
SINGLE_BAND_BELOW_CM = 750  # narrower house blocks get one row of rooms beside the corridor
MIN_SLICE_CM = 200  # a room narrower than this along the corridor uses only part of its slice
FRONT_OPEN = ("parking", "driveway", "dock")
REAR_OPEN = ("pool", "deck")
ZONE_ORDER = {"circulation": 0, "public": 1, "open": 2, "service": 3, "private": 4}


@dataclass
class Fallback:
    rooms: list[Room]
    topology: Topology
    program: RoomProgram  # the program with the corridor added, if it was not there
    notes: list[str] = field(default_factory=list)


def _side_wish(program: RoomProgram, rid: str) -> str | None:
    for rl in program.rules:
        if isinstance(rl, Place) and rl.room == rid and rl.side in ("front", "rear"):
            return rl.side
    return None


def corridor_layout(program: RoomProgram, plot: Plot) -> Fallback:
    road = plot.road_side or "south"
    across, deep = (plot.width, plot.depth) if road in ("north", "south") else (
        plot.depth,
        plot.width,
    )
    sb = plot.setbacks
    # canonical frame: u across (0 = the left as seen from the road), v from the rear (0)
    # to the road (deep); setbacks in that frame
    u0, u1 = sb.left, across - sb.right
    v0, v1 = sb.rear, deep - sb.front
    if u1 - u0 < 400 or v1 - v0 < 400:  # absurd setbacks: use the whole plot
        u0, u1, v0, v1 = 0, across, 0, deep

    rooms = list(program.rooms)
    notes: list[str] = []
    # ---------------------------------------------------------------- open strips
    front_open, rear_open = [], []
    gardens = [r for r in rooms if r.type in ("garden", "lawn")]
    for r in rooms:
        if r.type in FRONT_OPEN:
            front_open.append(r)
        elif r.type in REAR_OPEN:
            rear_open.append(r)
        elif r.type in ("garden", "lawn", "balcony"):
            wish = _side_wish(program, r.id)
            if wish == "front" or (wish is None and r is gardens[0] and len(gardens) > 1):
                front_open.append(r)
            else:
                rear_open.append(r)
    inner = [r for r in rooms if r not in front_open and r not in rear_open]

    def strip_depth(items: list[ProgramRoom], limit: int) -> int:
        if not items:
            return 0
        need = sum(r.target_area_m2 for r in items) * 10_000 / across
        least = max(MIN_ROOM[r.type].short_side_cm for r in items)
        return int(min(max(need, least, 300), limit))

    enclosed_m2 = sum(r.target_area_m2 for r in inner)
    block_need = enclosed_m2 * 10_000 / max(1, u1 - u0)
    room_for_strips = max(0, deep - min(block_need, v1 - v0))
    front_d = strip_depth(front_open, int(room_for_strips * 0.5) if rear_open else room_for_strips)
    rear_d = strip_depth(rear_open, max(0, room_for_strips - front_d))
    if front_open and front_d < 250:  # not even a car fits: open areas go to the rear
        rear_open += front_open
        front_open, front_d = [], 0
        rear_d = strip_depth(rear_open, room_for_strips)
    bv0 = max(v0, rear_d)
    bv1 = min(v1, deep - front_d)
    if bv1 - bv0 < 300:
        bv0, bv1 = v0, v1
        front_d = rear_d = 0
        notes.append("The outdoor areas could not get their own strips; they are drawn smaller.")

    placed: list[tuple[str, int, int, int, int]] = []  # id, u, v, du, dv (canonical frame)

    def lay_strip(items: list[ProgramRoom], va: int, vb: int) -> None:
        if not items or vb - va <= 0:
            return
        total = sum(max(r.target_area_m2, 1.0) for r in items)
        u = 0
        for k, r in enumerate(items):
            du = across - u if k == len(items) - 1 else round(across * r.target_area_m2 / total)
            placed.append((r.id, u, va, du, vb - va))
            u += du

    lay_strip(front_open, deep - front_d, deep)
    lay_strip(rear_open, 0, rear_d)
    if not front_d:
        # nothing was left in front: open areas that could not get a strip go to the rear
        pass

    # ---------------------------------------------------------------- house block
    width = u1 - u0
    depth = bv1 - bv0
    corridor = next((r for r in inner if r.type in ("passage", "lobby")), None)
    added = None
    if corridor is None:
        ids = {r.id for r in rooms}
        cid = next(f"passage_{i}" for i in range(1, 99) if f"passage_{i}" not in ids)
        added = ProgramRoom(
            id=cid,
            type="passage",
            label="PASSAGE",
            target_area_m2=round(CORRIDOR_CM * depth / 10_000, 2),
            zone="circulation",
        )
        corridor = added
    single = width < SINGLE_BAND_BELOW_CM
    if single:
        cu = u0  # corridor along the left side
        bands = [(u0 + CORRIDOR_CM, u1)]
    else:
        cu = u0 + (width - CORRIDOR_CM) // 2
        bands = [(u0, cu), (cu + CORRIDOR_CM, u1)]
    placed.append((corridor.id, cu, bv0, CORRIDOR_CM, depth))

    attached: dict[str, list[ProgramRoom]] = {}
    for r in inner:
        if r.attached_to and r is not corridor:
            attached.setdefault(r.attached_to, []).append(r)
    units = [
        r
        for r in inner
        if r is not corridor and not (r.attached_to and any(o.id == r.attached_to for o in inner))
    ]
    units.sort(key=lambda r: (ZONE_ORDER.get(r.zone, 2), r.type != "foyer", -r.target_area_m2))

    # assign units to bands, front to rear, keeping the bands' depths even
    band_units: list[list[ProgramRoom]] = [[] for _ in bands]
    load = [0.0] * len(bands)
    for r in units:
        area = r.target_area_m2 + sum(a.target_area_m2 for a in attached.get(r.id, []))
        k = min(range(len(bands)), key=lambda i: load[i] / max(1, bands[i][1] - bands[i][0]))
        band_units[k].append(r)
        load[k] += area

    scale_used = []
    for (ba, bb), items in zip(bands, band_units, strict=True):
        if not items:
            continue
        bw = bb - ba
        near_corridor_left = ba > cu  # the band right of the corridor touches it on its left
        heights = []
        for r in items:
            area = r.target_area_m2 + sum(a.target_area_m2 for a in attached.get(r.id, []))
            least = max(MIN_ROOM[r.type].short_side_cm, MIN_SLICE_CM)
            heights.append(max(area * 10_000 / bw, least))
        total = sum(heights)
        scale = depth / total if total else 1.0
        scale_used.append(scale)
        v = bv1  # front of the block first
        for k, (r, hgt) in enumerate(zip(items, heights, strict=True)):
            dv = v - bv0 if k == len(items) - 1 else max(MIN_SLICE_CM, round(hgt * scale))
            dv = min(dv, v - bv0)
            if dv <= 0:
                break
            va = v - dv
            att = attached.get(r.id, [])
            area = r.target_area_m2 + sum(a.target_area_m2 for a in att)
            # a small room on a wide band takes only the part of the slice it needs
            used = bw if area * 10_000 / dv >= 0.75 * bw else max(
                MIN_ROOM[r.type].short_side_cm, round(area * 10_000 / dv)
            )
            if att:
                col = min(
                    max(150, round(sum(a.target_area_m2 for a in att) * 10_000 / dv)),
                    round(used * 0.45),
                )
                main_w = used - col
            else:
                col, main_w = 0, used
            if near_corridor_left:
                mu = ba
                cu0 = ba + main_w
            else:
                mu = bb - main_w
                cu0 = mu - col
            placed.append((r.id, mu, va, main_w, dv))
            if att:
                tot = sum(a.target_area_m2 for a in att)
                w0 = va
                for j, a in enumerate(att):
                    last = j == len(att) - 1
                    dvy = (va + dv) - w0 if last else round(dv * a.target_area_m2 / tot)
                    placed.append((a.id, cu0, w0, col, dvy))
                    w0 += dvy
            v = va

    if scale_used and min(scale_used) < 0.95:
        notes.append(
            f"The rooms were made about {1 - min(scale_used):.0%} smaller to fit the "
            "simple corridor layout."
        )

    # ---------------------------------------------------------------- to the plot frame
    grid = Grid.for_plot(plot.width, plot.depth)
    by_id = {r.id: r for r in [*rooms, *([added] if added else [])]}
    out: list[Room] = []
    for rid, u, v, du, dv in placed:
        if du <= 0 or dv <= 0:
            continue
        x0, y0, x1, y1 = _to_plot(road, plot, u, v, u + du, v + dv)
        x0, x1 = grid.snap_x(x0), grid.snap_x(x1)
        y0, y1 = grid.snap_y(y0), grid.snap_y(y1)
        if x1 - x0 <= 0 or y1 - y0 <= 0:
            continue
        r = by_id[rid]
        out.append(
            Room(
                id=rid,
                type=r.type,
                label=r.label or DEFAULT_LABEL[r.type],
                x=x0,
                y=y0,
                w=x1 - x0,
                h=y1 - y0,
            )
        )

    root = next((r.id for r in inner if r.type == "foyer"), corridor.id)
    parent: dict[str, str | None] = {}
    for r in [*rooms, *([added] if added else [])]:
        if r.id == root:
            parent[r.id] = None
        elif r.id == corridor.id:
            parent[r.id] = root
        elif is_open(r.type) and r.type != "courtyard":
            parent[r.id] = None
        elif r.attached_to and r.attached_to in by_id:
            parent[r.id] = r.attached_to
        else:
            parent[r.id] = corridor.id
    new_program = program
    if added is not None:
        new_program = program.model_copy(update={"rooms": [*program.rooms, added]})
    return Fallback(out, Topology(root=root, parent=parent), new_program, notes)


def _to_plot(road: str, plot: Plot, ua: int, va: int, ub: int, vb: int):
    """Canonical (u across, v from the rear) rectangle -> plot cm (x east, y south)."""
    if road == "south":  # front at y = depth
        pts = [(ua, va), (ub, vb)]
    elif road == "north":  # front at y = 0
        pts = [(plot.width - ua, plot.depth - va), (plot.width - ub, plot.depth - vb)]
    elif road == "east":  # front at x = width
        pts = [(va, plot.depth - ua), (vb, plot.depth - ub)]
    else:  # west: front at x = 0
        pts = [(plot.width - va, ua), (plot.width - vb, ub)]
    (xa, ya), (xb, yb) = pts
    return min(xa, xb), min(ya, yb), max(xa, xb), max(ya, yb)
