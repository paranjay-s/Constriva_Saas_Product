"""General layout solver (OR-Tools CP-SAT) for programs no template handles.

Rooms are axis-aligned rectangles on the planning grid.

Hard constraints
  - inside the plot, no overlap (AddNoOverlap2D)
  - minimum side and area per room type; area within a band around the target
  - aspect ratio limit
  - every room shares a wall with its topology parent, long enough for its door
  - the entrance (root) room touches the road edge; parking touches the road edge
  - locked rooms keep their exact position and size (used by the edit engine)
Objective (maximise)
  covered area - missing exterior wall for habitable rooms - unmet adjacency wishes
  - zoning distance (public rooms near the road, private rooms away from it)
"""

import math

from ortools.sat.python import cp_model

from app.modules.ai.floorplan.pipeline.layout.grid import Grid
from app.modules.ai.floorplan.pipeline.layout.topology import (
    ENTRANCE_DOOR_CM,
    Topology,
    door_span_needed,
)
from app.modules.ai.floorplan.pipeline.pool_layouts import (
    LINED_SHARE,
    RING_CM,
    is_special,
)
from app.modules.ai.floorplan.rules import (
    AREA_FLEXIBLE_TYPES,
    CIRCULATION_MAX_FACTOR,
    MIN_ROOM,
    OPEN_AREA_CAP,
    OPENING_END_CLEARANCE_CM,
)
from app.modules.ai.floorplan.schemas.common import DEFAULT_LABEL, is_open
from app.modules.ai.floorplan.schemas.plan import Plot, Room
from app.modules.ai.floorplan.schemas.program import RoomProgram
from app.modules.ai.floorplan.schemas.rules import Daylight, DoorBetween, Place, SizeRule, Touches

AREA_BAND = 0.18
FLEX_TYPES = AREA_FLEXIBLE_TYPES
CIRCULATION = {"lobby", "passage"}
OPEN_GROW = FLEX_TYPES - CIRCULATION  # courtyard, garden, parking, balcony, shaft
HABITABLE = {
    "master_bedroom",
    "bedroom",
    "living",
    "family_hall",
    "dining",
    "kitchen",
    "study",
    "maid_room",
    "majlis",
    "driver_room",
    "gym",
    "bar",
}
SMALL = {"bath", "toilet", "store", "dress", "utility", "foyer"}

SLIVER_CM = 60  # gaps this thin are absorbed by a neighbour rather than left as a duct
W_AREA = 10
W_DEV = 5  # per grid cell away from a room's target area
W_FRONT_OPEN = 15_000
W_EXTERIOR = 20_000
W_ADJ = 6_000
W_ZONE = 2


def _aspect(t: str) -> float | None:
    if t in ("lobby", "passage"):
        return None
    if t == "pool":
        return 2.5
    if t == "deck":
        return 3.0
    if t in ("garden", "courtyard", "parking", "balcony"):
        return 4.0
    if t in SMALL:
        return 2.6
    if t in HABITABLE:
        return 1.8
    return 2.0


class _Box:
    def __init__(self, m: cp_model.CpModel, rid: str, grid: Grid) -> None:
        self.x = m.NewIntVar(0, grid.nx, f"x_{rid}")
        self.y = m.NewIntVar(0, grid.ny, f"y_{rid}")
        self.w = m.NewIntVar(1, grid.nx, f"w_{rid}")
        self.h = m.NewIntVar(1, grid.ny, f"h_{rid}")
        self.xe = m.NewIntVar(0, grid.nx, f"xe_{rid}")
        self.ye = m.NewIntVar(0, grid.ny, f"ye_{rid}")
        m.Add(self.xe == self.x + self.w)
        m.Add(self.ye == self.y + self.h)
        self.ix = m.NewIntervalVar(self.x, self.w, self.xe, f"ix_{rid}")
        self.iy = m.NewIntervalVar(self.y, self.h, self.ye, f"iy_{rid}")
        self.area = m.NewIntVar(1, grid.nx * grid.ny, f"a_{rid}")
        m.AddMultiplicationEquality(self.area, [self.w, self.h])


def _snap_coarse(m: cp_model.CpModel, b: "_Box", grid: Grid, k: int, rid: str) -> None:
    """Edges on multiples of k grid units, except edges lying on the plot boundary."""
    for var, limit, tag in (
        (b.x, grid.nx, "x"),
        (b.y, grid.ny, "y"),
        (b.xe, grid.nx, "xe"),
        (b.ye, grid.ny, "ye"),
    ):
        q = m.NewIntVar(0, limit // k + 1, f"c{tag}_{rid}")
        on_edge = m.NewBoolVar(f"edge{tag}_{rid}")
        m.Add(var == limit).OnlyEnforceIf(on_edge)
        m.Add(var == k * q).OnlyEnforceIf(on_edge.Not())


def _share_wall(m: cp_model.CpModel, a: _Box, b: _Box, lx: int, ly: int, tag: str) -> list:
    """Booleans, one per side; each true one forces a shared wall of the given length."""
    sides = []
    for name in ("E", "W", "S", "N"):
        bvar = m.NewBoolVar(f"adj_{tag}_{name}")
        if name == "E":  # b right of a
            m.Add(a.xe == b.x).OnlyEnforceIf(bvar)
        elif name == "W":
            m.Add(b.xe == a.x).OnlyEnforceIf(bvar)
        elif name == "S":  # b below a
            m.Add(a.ye == b.y).OnlyEnforceIf(bvar)
        else:
            m.Add(b.ye == a.y).OnlyEnforceIf(bvar)
        if name in ("E", "W"):  # overlap along y >= ly
            m.Add(b.y + ly <= a.ye).OnlyEnforceIf(bvar)
            m.Add(a.y + ly <= b.ye).OnlyEnforceIf(bvar)
        else:
            m.Add(b.x + lx <= a.xe).OnlyEnforceIf(bvar)
            m.Add(a.x + lx <= b.xe).OnlyEnforceIf(bvar)
        sides.append(bvar)
    return sides


def _buildable_units(plot: Plot, grid: Grid) -> tuple[int, int, int, int]:
    """The plot inside the setbacks, in grid units (rounded inwards)."""
    x0, y0, x1, y1 = plot.buildable()
    return (
        math.ceil(x0 / grid.gx - 1e-9),
        math.ceil(y0 / grid.gy - 1e-9),
        math.floor(x1 / grid.gx + 1e-9),
        math.floor(y1 / grid.gy + 1e-9),
    )


def _touch_edge(
    m: cp_model.CpModel,
    b: _Box,
    side: str,
    grid: Grid,
    length_cm: float,
    tag: str,
    bounds: tuple[int, int, int, int] | None = None,
):
    """A boolean that, when true, puts the box on that edge of `bounds` (grid units;
    default the plot) with at least `length_cm` of its side along it."""
    x0, y0, x1, y1 = bounds or (0, 0, grid.nx, grid.ny)
    bvar = m.NewBoolVar(f"edge_{tag}_{side}")
    if side == "west":
        m.Add(b.x == x0).OnlyEnforceIf(bvar)
        m.Add(b.h >= math.ceil(length_cm / grid.gy)).OnlyEnforceIf(bvar)
    elif side == "east":
        m.Add(b.xe == x1).OnlyEnforceIf(bvar)
        m.Add(b.h >= math.ceil(length_cm / grid.gy)).OnlyEnforceIf(bvar)
    elif side == "north":
        m.Add(b.y == y0).OnlyEnforceIf(bvar)
        m.Add(b.w >= math.ceil(length_cm / grid.gx)).OnlyEnforceIf(bvar)
    else:
        m.Add(b.ye == y1).OnlyEnforceIf(bvar)
        m.Add(b.w >= math.ceil(length_cm / grid.gx)).OnlyEnforceIf(bvar)
    return bvar


def solve_layout(
    program: RoomProgram,
    plot: Plot,
    topo: Topology,
    *,
    fixed: dict[str, Room] | None = None,
    time_limit_s: float = 8.0,
    seed: int = 0,
    workers: int = 8,
    exact_tiling: bool = False,
    coarse: int = 1,
    anchors: dict[str, list[str]] | None = None,
    adjoin: list[tuple[str, str]] | None = None,
    sizes: dict[str, tuple[tuple[int, int] | None, tuple[int, int] | None, bool]] | None = None,
    area_bounds: dict[str, tuple[float, float]] | None = None,
) -> list[Room] | None:
    """Solve a layout. With exact_tiling the rooms must cover the whole plot (no gaps).

    `coarse` > 1 puts free room edges on every coarse-th grid line (plot edges always
    allowed). The search gets much faster while staying on the shared planning grid.

    Edits add hard wishes: `anchors` (room must touch these plot edges), `adjoin` (pairs
    that must share a wall of at least 1 m) and `sizes` (allowed width / depth ranges in
    cm, None = free; the third value allows the room either way round).
    `area_bounds` (m2) replace the usual band around the target for the rooms listed
    (neighbours that make or take space).
    """
    fixed = fixed or {}
    size_rules: dict[str, list[SizeRule]] = {}
    for rl in program.rules:
        if isinstance(rl, SizeRule):
            size_rules.setdefault(rl.room, []).append(rl)
    grid = Grid.for_plot(plot.width, plot.depth)
    cell = grid.gx * grid.gy
    road = plot.road_side or "south"
    m = cp_model.CpModel()
    boxes: dict[str, _Box] = {}

    for r in program.rooms:
        b = _Box(m, r.id, grid)
        boxes[r.id] = b
        if r.id in fixed:
            f = fixed[r.id]
            m.Add(b.x == grid.x_units(f.x))
            m.Add(b.y == grid.y_units(f.y))
            m.Add(b.xe == grid.x_units(f.x2))
            m.Add(b.ye == grid.y_units(f.y2))
            continue
        if coarse > 1:
            _snap_coarse(m, b, grid, coarse, r.id)
        rule = MIN_ROOM[r.type]
        side = max(rule.short_side_cm, 120 if r.type in ("lobby", "passage") else 0)
        m.Add(b.w >= max(1, math.ceil(side / grid.gx)))
        m.Add(b.h >= max(1, math.ceil(side / grid.gy)))
        target = r.target_area_m2 * 10_000
        lo = max(rule.area_m2 * 10_000, target * (1 - AREA_BAND))
        if r.type in CIRCULATION:
            hi = target * CIRCULATION_MAX_FACTOR
        elif r.type in OPEN_AREA_CAP:
            hi = target * OPEN_AREA_CAP[r.type]
        elif r.type in FLEX_TYPES:
            hi = grid.nx * grid.ny * cell
        else:
            hi = target * (1 + AREA_BAND)
        if area_bounds and r.id in area_bounds:
            lo = max(rule.area_m2, area_bounds[r.id][0]) * 10_000
            hi = area_bounds[r.id][1] * 10_000
        for sr in size_rules.get(r.id, []):
            if sr.min_area_m2:
                lo = max(rule.area_m2 * 10_000, sr.min_area_m2 * 10_000)
                hi = max(hi, lo)
            if sr.max_area_m2:
                hi = sr.max_area_m2 * 10_000
                lo = min(lo, hi)
        m.Add(b.area >= math.ceil(lo / cell))
        m.Add(b.area <= max(math.ceil(lo / cell), math.floor(hi / cell)))
        k = _aspect(r.type)
        if r.type == "pool" and program.pool_layout == "two_block":
            k = 5.0  # the pool zone is a long strip between the two blocks
        if k:
            # compare in cm: w*gx <= k*h*gy  (scaled to integers by 100)
            m.Add(100 * b.w * round(grid.gx * 10) <= round(k * 100) * b.h * round(grid.gy * 10))
            m.Add(100 * b.h * round(grid.gy * 10) <= round(k * 100) * b.w * round(grid.gx * 10))

    m.AddNoOverlap2D([b.ix for b in boxes.values()], [b.iy for b in boxes.values()])

    # setbacks: enclosed rooms stay inside the buildable box; open areas may use the strips
    bounds = _buildable_units(plot, grid)
    for r in program.rooms:
        if r.id in fixed or is_open(r.type):
            continue
        b = boxes[r.id]
        m.Add(b.x >= bounds[0])
        m.Add(b.y >= bounds[1])
        m.Add(b.xe <= bounds[2])
        m.Add(b.ye <= bounds[3])

    # topology: shared walls for doors
    for child, par in topo.parent.items():
        if par is None or child not in boxes or par not in boxes:
            continue
        ctype = next(r.type for r in program.rooms if r.id == child)
        need = door_span_needed(ctype)
        lx, ly = math.ceil(need / grid.gx), math.ceil(need / grid.gy)
        m.AddBoolOr(_share_wall(m, boxes[child], boxes[par], lx, ly, f"{child}_{par}"))

    # entrance and parking on the road edge
    entrance_len = ENTRANCE_DOOR_CM + 2 * OPENING_END_CLEARANCE_CM + 10
    if topo.root not in fixed:
        m.Add(
            _touch_edge(m, boxes[topo.root], road, grid, entrance_len, "root", bounds) == 1
        )
    for r in program.rooms:
        if r.type == "parking" and r.id not in fixed:
            m.Add(_touch_edge(m, boxes[r.id], road, grid, 250, r.id) == 1)

    for rid, sides in (anchors or {}).items():
        for side in sides:
            m.Add(_touch_edge(m, boxes[rid], side, grid, 120, f"anchor_{rid}") == 1)
    for a, b in adjoin or []:
        lx, ly = math.ceil(100 / grid.gx), math.ceil(100 / grid.gy)
        m.AddBoolOr(_share_wall(m, boxes[a], boxes[b], lx, ly, f"must_{a}_{b}"))
    for rid, (sw, sh, turnable) in (sizes or {}).items():
        if rid in fixed:
            continue
        b = boxes[rid]
        turn = m.NewBoolVar(f"turn_{rid}")
        if not turnable:
            m.Add(turn == 0)
        straight = ((b.w, sw, grid.gx), (b.h, sh, grid.gy))
        turned = ((b.w, sh, grid.gx), (b.h, sw, grid.gy))
        for pairs, flag in ((straight, turn.Not()), (turned, turn)):
            for var, rng, g in pairs:
                if rng is None:
                    continue
                m.Add(var >= max(1, math.floor(rng[0] / g))).OnlyEnforceIf(flag)
                m.Add(var <= math.ceil(rng[1] / g)).OnlyEnforceIf(flag)

    objective = []
    _apply_rules(m, program, boxes, grid, road, bounds, fixed, size_rules, objective)

    if is_special(program.pool_layout):
        _pool_layout_rules(m, program, boxes, grid, road)
    else:
        # a pool beside the house always touches the plot edge (garden side by preference)
        for r in program.rooms:
            if r.type == "pool" and r.id not in fixed:
                m.AddBoolOr(
                    [
                        _touch_edge(m, boxes[r.id], s, grid, 300, f"pool_{r.id}")
                        for s in ("north", "south", "east", "west")
                    ]
                )

    total_area = sum(b.area for b in boxes.values())
    if exact_tiling:
        m.Add(total_area == grid.nx * grid.ny)
    else:
        objective.append(W_AREA * total_area)

    # Rooms reach their target before open space grows: below target, each cell costs
    # W_AREA + W_DEV; above target it gains only W_AREA - W_DEV (open areas gain W_AREA).
    for r in program.rooms:
        if r.type in FLEX_TYPES or r.id in fixed:
            continue
        t_cells = round(r.target_area_m2 * 10_000 / cell)
        dev = m.NewIntVar(0, grid.nx * grid.ny, f"dev_{r.id}")
        m.Add(dev >= boxes[r.id].area - t_cells)
        m.Add(dev >= t_cells - boxes[r.id].area)
        objective.append(-W_DEV * dev)

    for r in program.rooms:
        if r.type == "garden" and r.id not in fixed:
            on_road = _touch_edge(m, boxes[r.id], road, grid, 200, f"front_{r.id}")
            objective.append(W_FRONT_OPEN * on_road)

    for r in program.rooms:
        if r.type in HABITABLE or r.type in ("garden", "deck"):
            edge_bounds = None if is_open(r.type) else bounds
            edges = [
                _touch_edge(m, boxes[r.id], s, grid, 120, r.id, edge_bounds)
                for s in ("west", "east", "north", "south")
            ]
            miss = m.NewBoolVar(f"noext_{r.id}")
            m.AddBoolOr([*edges, miss])
            objective.append(-W_EXTERIOR * miss)

    for adj in program.adjacency:
        if adj.a in boxes and adj.b in boxes:
            sides = _share_wall(
                m,
                boxes[adj.a],
                boxes[adj.b],
                math.ceil(100 / grid.gx),
                math.ceil(100 / grid.gy),
                f"wish_{adj.a}_{adj.b}",
            )
            miss = m.NewBoolVar(f"nowish_{adj.a}_{adj.b}")
            m.AddBoolOr([*sides, miss])
            objective.append(-W_ADJ * adj.weight * miss)

    for r in program.rooms:
        b = boxes[r.id]
        front = {"south": grid.ny - b.ye, "north": b.y, "east": grid.nx - b.xe, "west": b.x}[road]
        if r.zone == "public" or r.type in ("garden", "parking"):
            objective.append(-W_ZONE * front)
        elif r.zone == "private" or r.type == "pool":  # pool away from the road
            objective.append(W_ZONE * front)

    m.Maximize(sum(objective))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = workers
    solver.parameters.random_seed = seed
    status = solver.Solve(m)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    out = []
    for r in program.rooms:
        b = boxes[r.id]
        x0, x1 = grid.x_cm(solver.Value(b.x)), grid.x_cm(solver.Value(b.xe))
        y0, y1 = grid.y_cm(solver.Value(b.y)), grid.y_cm(solver.Value(b.ye))
        out.append(
            Room(
                id=r.id,
                type=r.type,
                label=r.label or DEFAULT_LABEL[r.type],
                x=x0,
                y=y0,
                w=x1 - x0,
                h=y1 - y0,
                locked=r.id in fixed,
            )
        )
    return out


W_PLACE = 40  # per grid unit a placed room sits away from its edge


def _apply_rules(
    m: cp_model.CpModel,
    program: RoomProgram,
    boxes: dict[str, "_Box"],
    grid: Grid,
    road: str,
    bounds: tuple[int, int, int, int],
    fixed: dict[str, Room],
    size_rules: dict[str, list[SizeRule]],
    objective: list,
) -> None:
    """The program's layout rules as hard constraints (schemas/rules.py)."""
    types = {r.id: r.type for r in program.rooms}
    one_m = (math.ceil(100 / grid.gx), math.ceil(100 / grid.gy))
    compass = dict(zip(("front", "rear", "left", "right"), _FRAME_SIDES[road], strict=True))

    def joined(a: str, b: str, door: bool, tag: str) -> None:
        if a not in boxes or b not in boxes or (a in fixed and b in fixed):
            return
        if door:
            inner = a if not is_open(types[a]) else b
            need = max(door_span_needed(types[inner]), 100)
            lx, ly = math.ceil(need / grid.gx), math.ceil(need / grid.gy)
        else:
            lx, ly = one_m
        m.AddBoolOr(_share_wall(m, boxes[a], boxes[b], lx, ly, tag))

    for i, rl in enumerate(program.rules):
        if isinstance(rl, Touches):
            for o in rl.others:
                joined(rl.room, o, rl.door, f"rule{i}_{rl.room}_{o}")
        elif isinstance(rl, DoorBetween):
            joined(rl.a, rl.b, True, f"rule{i}_{rl.a}_{rl.b}")
        elif isinstance(rl, Place) and rl.room in boxes and rl.room not in fixed:
            b = boxes[rl.room]
            sx, sy = b.x + b.xe, b.y + b.ye  # twice the centre
            if rl.side == "centre":
                m.Add(3 * sx >= 2 * grid.nx)
                m.Add(3 * sx <= 4 * grid.nx)
                m.Add(3 * sy >= 2 * grid.ny)
                m.Add(3 * sy <= 4 * grid.ny)
                continue
            side = compass[rl.side]
            if side == "south":
                m.Add(sy >= grid.ny + 1)  # centre strictly in that half
                objective.append(-W_PLACE * (grid.ny - b.ye))
            elif side == "north":
                m.Add(sy <= grid.ny - 1)
                objective.append(-W_PLACE * b.y)
            elif side == "east":
                m.Add(sx >= grid.nx + 1)
                objective.append(-W_PLACE * (grid.nx - b.xe))
            else:
                m.Add(sx <= grid.nx - 1)
                objective.append(-W_PLACE * b.x)
        elif isinstance(rl, Daylight) and rl.room in boxes and rl.room not in fixed:
            b = boxes[rl.room]
            edge_bounds = None if is_open(types[rl.room]) else bounds
            lits = [
                _touch_edge(m, b, s, grid, 120, f"rule{i}_day", edge_bounds)
                for s in ("west", "east", "north", "south")
            ]
            for o in program.rooms:
                if is_open(o.type) and o.id != rl.room:
                    lits += _share_wall(m, b, boxes[o.id], *one_m, f"rule{i}_day_{o.id}")
            m.AddBoolOr(lits)
    for rid, rules in size_rules.items():
        if rid not in boxes or rid in fixed:
            continue
        b = boxes[rid]
        for sr in rules:
            if sr.min_width_cm:
                m.Add(b.w >= math.ceil(sr.min_width_cm / grid.gx))
                m.Add(b.h >= math.ceil(sr.min_width_cm / grid.gy))
            if sr.max_width_cm:
                narrow = m.NewBoolVar(f"maxw_{rid}")
                m.Add(b.w <= math.floor(sr.max_width_cm / grid.gx)).OnlyEnforceIf(narrow)
                m.Add(b.h <= math.floor(sr.max_width_cm / grid.gy)).OnlyEnforceIf(narrow.Not())
            if sr.max_aspect:
                k = round(sr.max_aspect * 100)
                gx, gy = round(grid.gx * 10), round(grid.gy * 10)
                m.Add(100 * b.w * gx <= k * b.h * gy)
                m.Add(100 * b.h * gy <= k * b.w * gx)


# _share_wall(a, b) returns one boolean per side of a where b sits: E, W, S, N
_SIDE_INDEX = {"east": 0, "west": 1, "south": 2, "north": 3}
_FRAME_SIDES = {  # road side -> (front, rear, left, right) as compass sides
    "south": ("south", "north", "west", "east"),
    "north": ("north", "south", "east", "west"),
    "east": ("east", "west", "south", "north"),
    "west": ("west", "east", "north", "south"),
}


def _frame(b: _Box, grid: Grid, road: str):
    """Road-relative edges (d0, d1, a0, a1) of a box, in grid units, as linear terms."""
    if road == "south":
        return grid.ny - b.ye, grid.ny - b.y, b.x, b.xe
    if road == "north":
        return b.y, b.ye, b.x, b.xe
    if road == "east":
        return grid.nx - b.xe, grid.nx - b.x, b.y, b.ye
    return b.x, b.xe, b.y, b.ye


def _pool_layout_rules(
    m: cp_model.CpModel,
    program: RoomProgram,
    boxes: dict[str, "_Box"],
    grid: Grid,
    road: str,
) -> None:
    """Hard rules for a pool inside the house (see pipeline/pool_layouts.py)."""
    pool = next((r for r in program.rooms if r.type == "pool"), None)
    if pool is None:
        return
    p = boxes[pool.id]
    layout = program.pool_layout
    deep_n, across_n = (grid.ny, grid.nx) if road in ("north", "south") else (grid.nx, grid.ny)
    g_d, g_a = (grid.gy, grid.gx) if road in ("north", "south") else (grid.gx, grid.gy)
    pd0, pd1, pa0, pa1 = _frame(p, grid, road)
    front, rear, left, right = _FRAME_SIDES[road]
    enclosed = [r for r in program.rooms if r.zone != "open"]

    def rooms_on(sides: tuple[str, ...]) -> None:
        """Rooms (not open space) line most of each named side of the pool: the wall
        each room shares with that side adds up to at least LINED_SHARE of its length."""
        pct = round(LINED_SHARE * 100)
        for side in sides:
            horizontal = side in ("north", "south")  # the side runs east-west
            side_len = p.w if horizontal else p.h
            shares = []
            for r in enclosed:
                b = boxes[r.id]
                on = m.NewBoolVar(f"lined_{side}_{r.id}")
                ov = m.NewIntVar(0, max(grid.nx, grid.ny), f"lined_len_{side}_{r.id}")
                if side == "east":
                    m.Add(b.x == p.xe).OnlyEnforceIf(on)
                elif side == "west":
                    m.Add(b.xe == p.x).OnlyEnforceIf(on)
                elif side == "south":
                    m.Add(b.y == p.ye).OnlyEnforceIf(on)
                else:
                    m.Add(b.ye == p.y).OnlyEnforceIf(on)
                lo_r, hi_r, lo_p, hi_p = (
                    (b.x, b.xe, p.x, p.xe) if horizontal else (b.y, b.ye, p.y, p.ye)
                )
                m.Add(ov <= hi_r - lo_p).OnlyEnforceIf(on)  # overlap of the two spans
                m.Add(ov <= hi_p - lo_r).OnlyEnforceIf(on)
                m.Add(ov <= hi_r - lo_r).OnlyEnforceIf(on)
                m.Add(ov <= hi_p - lo_p).OnlyEnforceIf(on)
                m.Add(ov == 0).OnlyEnforceIf(on.Not())
                shares.append(ov)
            m.Add(100 * sum(shares) >= pct * side_len)

    kd, ka = math.ceil(RING_CM / g_d), math.ceil(RING_CM / g_a)
    if layout == "centre":  # rooms all round: no plot edge, a room on every side
        m.Add(pd0 >= kd)
        m.Add(pd1 <= deep_n - kd)
        m.Add(pa0 >= ka)
        m.Add(pa1 <= across_n - ka)
        rooms_on((front, rear, left, right))
    elif layout == "u_shape":  # open only to the rear garden
        m.Add(pd1 == deep_n)
        m.Add(pd0 >= kd)
        m.Add(pa0 >= ka)
        m.Add(pa1 <= across_n - ka)
        rooms_on((front, left, right))
    elif layout == "two_block":
        main = [boxes[r.id] for r in enclosed if r.block == "main"]
        guest = [boxes[r.id] for r in enclosed if r.block == "guest"]
        if program.pool_axis == "side_by_side":  # blocks left and right of the pool
            m.Add(pd1 - pd0 >= math.ceil(0.6 * deep_n))
            main_left = m.NewBoolVar("main_left_of_pool")
            for b in main:
                _, _, a0, a1 = _frame(b, grid, road)
                m.Add(a1 <= pa0).OnlyEnforceIf(main_left)
                m.Add(a0 >= pa1).OnlyEnforceIf(main_left.Not())
            for b in guest:
                _, _, a0, a1 = _frame(b, grid, road)
                m.Add(a0 >= pa1).OnlyEnforceIf(main_left)
                m.Add(a1 <= pa0).OnlyEnforceIf(main_left.Not())
        else:  # main block on the road side, guest block behind the pool
            m.Add(pa1 - pa0 >= math.ceil(0.6 * across_n))
            for b in main:
                _, d1, _, _ = _frame(b, grid, road)
                m.Add(d1 <= pd0)
            for b in guest:
                d0, _, _, _ = _frame(b, grid, road)
                m.Add(d0 >= pd1)


def fill_gaps(
    rooms: list[Room], plot: Plot, targets: dict[str, float], keep: set[str] | None = None
) -> list[Room]:
    """Grow rooms into empty neighbouring space so the plot has no holes.

    Open areas grow first (the garden freely, parking/courtyard up to OPEN_AREA_CAP),
    circulation up to its cap, other rooms up to +20 % of their target area. Growing only
    into empty space never removes a shared wall, so the topology still holds. Locked
    rooms and rooms in `keep` (given an exact size by an edit) never change.
    """
    rooms = [r.model_copy() for r in rooms]
    keep = keep or set()

    def rank(r: Room) -> int:
        return 0 if r.type in OPEN_GROW else (1 if r.type in CIRCULATION else 2)

    order = sorted(range(len(rooms)), key=lambda i: (rank(rooms[i]), rooms[i].id))
    # Two rounds: other rooms take the gaps first; a room given an exact size only takes
    # a thin sliver nobody else could (so "2 ft wider" stays 2 ft, not 3).
    for allow_keep in (False, True):
        _grow_into_gaps(rooms, order, plot, targets, keep, allow_keep)
    return rooms


def _grow_into_gaps(
    rooms: list[Room],
    order: list[int],
    plot: Plot,
    targets: dict[str, float],
    keep: set[str],
    allow_keep: bool,
) -> None:
    changed = True
    while changed:
        changed = False
        for i in order:
            r = rooms[i]
            if r.locked or (r.id in keep and not allow_keep):
                continue
            for side in ("east", "west", "south", "north"):
                d = _free_distance(r, side, rooms, plot)
                if d <= 0 or (r.id in keep and d > SLIVER_CM):
                    continue  # a room given a size only swallows thin slivers
                grown = _grow(r, side, d)
                target = targets.get(r.id, 0)
                if r.type in CIRCULATION:
                    cap = target * CIRCULATION_MAX_FACTOR
                elif r.type in OPEN_AREA_CAP:
                    cap = target * OPEN_AREA_CAP[r.type]
                elif r.type in OPEN_GROW:
                    cap = float("inf")
                else:  # thin slivers may push a room to the validator's +25 % limit
                    cap = target * (1.24 if d <= 60 else 1.2)
                if grown.area_m2 > cap:
                    continue
                rooms[i] = r = grown
                changed = True


def _free_distance(r: Room, side: str, rooms: list[Room], plot: Plot) -> int:
    """Distance from a room side to the next room (overlapping its span) or plot edge;
    for an enclosed room on a plot with setbacks, to the setback line."""
    if not r.is_open and r.type != "shaft" and plot.has_setbacks:
        bx0, by0, bx1, by1 = plot.buildable()
        edge = {"east": bx1 - r.x2, "west": r.x - bx0, "south": by1 - r.y2, "north": r.y - by0}
        cap = max(0, edge[side])
        return min(cap, _free_distance(r.model_copy(update={"type": "garden"}), side, rooms, plot))
    if side == "east":
        limit = plot.width - r.x2
        hits = [
            o.x - r.x2 for o in rooms if o.id != r.id and o.x >= r.x2 and o.y < r.y2 and o.y2 > r.y
        ]
    elif side == "west":
        limit = r.x
        hits = [
            r.x - o.x2 for o in rooms if o.id != r.id and o.x2 <= r.x and o.y < r.y2 and o.y2 > r.y
        ]
    elif side == "south":
        limit = plot.depth - r.y2
        hits = [
            o.y - r.y2 for o in rooms if o.id != r.id and o.y >= r.y2 and o.x < r.x2 and o.x2 > r.x
        ]
    else:
        limit = r.y
        hits = [
            r.y - o.y2 for o in rooms if o.id != r.id and o.y2 <= r.y and o.x < r.x2 and o.x2 > r.x
        ]
    return min([limit, *hits])


def _grow(r: Room, side: str, d: int) -> Room:
    if side == "east":
        return r.model_copy(update={"w": r.w + d})
    if side == "west":
        return r.model_copy(update={"x": r.x - d, "w": r.w + d})
    if side == "south":
        return r.model_copy(update={"h": r.h + d})
    return r.model_copy(update={"y": r.y - d, "h": r.h + d})


def fill_holes_with_shafts(rooms: list[Room], plot: Plot) -> list[Room]:
    """Turn any space no room covers into open-to-sky shafts (labelled OPEN).

    The uncovered area is cut along every room edge into a coarse grid of cells, and
    neighbouring empty cells are merged into maximal rectangles.
    """
    bx0, by0, bx1, by1 = plot.buildable()
    extra_x = (bx0, bx1) if plot.has_setbacks else ()
    extra_y = (by0, by1) if plot.has_setbacks else ()
    xs = sorted({0, plot.width, *extra_x, *(v for r in rooms for v in (r.x, r.x2))})
    ys = sorted({0, plot.depth, *extra_y, *(v for r in rooms for v in (r.y, r.y2))})

    def covered(x0: int, y0: int) -> bool:
        return any(r.x <= x0 < r.x2 and r.y <= y0 < r.y2 for r in rooms)

    empty = [[not covered(xs[i], ys[j]) for i in range(len(xs) - 1)] for j in range(len(ys) - 1)]
    shafts: list[Room] = []
    taken = {r.id for r in rooms}
    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            if not empty[j][i]:
                continue
            i2 = i
            while i2 + 1 < len(xs) - 1 and empty[j][i2 + 1]:
                i2 += 1
            j2 = j
            while j2 + 1 < len(ys) - 1 and all(empty[j2 + 1][k] for k in range(i, i2 + 1)):
                j2 += 1
            for jj in range(j, j2 + 1):
                for ii in range(i, i2 + 1):
                    empty[jj][ii] = False
            n = 1
            while f"shaft_{n}" in taken:
                n += 1
            taken.add(f"shaft_{n}")
            shafts.append(
                Room(
                    id=f"shaft_{n}",
                    type="shaft",
                    label="DUCT" if min(xs[i2 + 1] - xs[i], ys[j2 + 1] - ys[j]) < 60 else "OPEN",
                    x=xs[i],
                    y=ys[j],
                    w=xs[i2 + 1] - xs[i],
                    h=ys[j2 + 1] - ys[j],
                )
            )
    joined = join_outdoor(rooms, shafts)
    if plot.has_setbacks:
        # space in the setback strips that no garden or pool takes stays unbuilt: the
        # building model draws it as paving, it is not a shaft inside the house
        joined = [
            s
            for s in joined
            if s.part_of or (bx0 <= s.x and s.x2 <= bx1 and by0 <= s.y and s.y2 <= by1)
        ]
    return rooms + joined


OUTDOOR_TYPES = ("garden", "lawn", "pool", "deck", "courtyard", "parking", "driveway", "dock")
JOIN_PRIORITY = {
    "garden": 0,
    "lawn": 0,
    "pool": 1,
    "deck": 2,
    "courtyard": 3,
    "parking": 4,
    "driveway": 4,
    "dock": 5,
}
JOIN_MIN_EDGE_CM = 30


def _shared_edge(a: Room, b: Room) -> int:
    """Length of the wall two rectangles share (0 if they only touch at a corner)."""
    if a.x2 == b.x or b.x2 == a.x:
        return max(0, min(a.y2, b.y2) - max(a.y, b.y))
    if a.y2 == b.y or b.y2 == a.y:
        return max(0, min(a.x2, b.x2) - max(a.x, b.x))
    return 0


def join_outdoor(rooms: list[Room], shafts: list[Room]) -> list[Room]:
    """Leftover space touching the garden, pool, deck... is drawn as part of that area.

    The shaft keeps its own id and type (so the program and validator are unchanged) and
    gets `part_of` = the outdoor area it joins and that area's label. Shafts touching an
    already joined shaft join the same area, so a chain of gaps reads as one space.
    """
    owner: dict[str, Room] = {}  # shaft id -> outdoor room it joins
    outdoor = [r for r in rooms if r.type in OUTDOOR_TYPES]
    changed = True
    while changed:
        changed = False
        for s in shafts:
            if s.id in owner:
                continue
            best: tuple[int, int, Room] | None = None
            for o in outdoor:
                edge = _shared_edge(s, o)
                if edge >= JOIN_MIN_EDGE_CM:
                    key = (JOIN_PRIORITY[o.type], -edge, o)
                    if best is None or key[:2] < best[:2]:
                        best = key
            for t in shafts:
                if t.id in owner and _shared_edge(s, t) >= JOIN_MIN_EDGE_CM:
                    o = owner[t.id]
                    key = (JOIN_PRIORITY[o.type], -_shared_edge(s, t), o)
                    if best is None or key[:2] < best[:2]:
                        best = key
            if best is not None:
                owner[s.id] = best[2]
                changed = True
    return [
        s.model_copy(update={"part_of": owner[s.id].id, "label": owner[s.id].label})
        if s.id in owner
        else s
        for s in shafts
    ]
