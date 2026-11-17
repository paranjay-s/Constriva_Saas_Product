"""Layout templates: fast, gap-free layouts for common house types.

Template "compact_rows" (1-6 bedroom single-family houses):

    back  | R1 private : bedroom suites (+ attached bath/dress), study, maid, common baths
          | R2 lobby   : full-width corridor, every R1 and R3 room opens onto it
          | R3 public  : kitchen(+utility) | dining | family hall | living
    front | R4 front   : garden / parking ... | foyer (under living)      [road side]

Rows are sized from the program's target areas, so the plan is a guillotine tiling of
the plot (no gaps, no overlaps) and every parent/child pair shares a wall by
construction. The layout is built facing a south road and rotated for other sides.
A template returns None when the program does not suit it; the solver handles those.
"""

from dataclasses import dataclass, field

from app.modules.ai.floorplan.pipeline.layout.grid import Grid
from app.modules.ai.floorplan.rules import MIN_ROOM
from app.modules.ai.floorplan.schemas.common import DEFAULT_LABEL
from app.modules.ai.floorplan.schemas.plan import Plot, Room
from app.modules.ai.floorplan.schemas.program import ProgramRoom, RoomProgram

LOBBY_DEPTH_CM = 130
SIDE_COLUMN_MIN_CM = 150
FRONT_ROW_MIN_CM = 150

BIG_PRIVATE = ("master_bedroom", "bedroom", "study", "maid_room")
SMALL_PRIVATE = ("bath", "toilet", "dress", "store")
SUPPORTED = (
    set(BIG_PRIVATE)
    | set(SMALL_PRIVATE)
    | {
        "living",
        "family_hall",
        "dining",
        "kitchen",
        "utility",
        "lobby",
        "passage",
        "foyer",
        "garden",
        "parking",
    }
)


@dataclass
class _Cell:
    id: str
    type: str
    label: str
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class TemplateResult:
    name: str
    rooms: list[Room]
    parent: dict[str, str | None]
    root: str
    added: list[ProgramRoom] = field(default_factory=list)


def compact_rows(program: RoomProgram, plot: Plot) -> TemplateResult | None:
    rooms = program.rooms
    if any(r.type not in SUPPORTED for r in rooms):
        return None
    by_type: dict[str, list[ProgramRoom]] = {}
    for r in rooms:
        by_type.setdefault(r.type, []).append(r)
    hubs = by_type.get("living", []) + by_type.get("family_hall", [])
    if not hubs or len(by_type.get("kitchen", [])) > 1 or len(by_type.get("foyer", [])) > 1:
        return None

    road = plot.road_side or "south"
    wl, dl = (plot.width, plot.depth) if road in ("south", "north") else (plot.depth, plot.width)
    a = {r.id: r.target_area_m2 * 10_000 for r in rooms}  # cm2
    parent: dict[str, str | None] = {}
    added: list[ProgramRoom] = []
    cells: list[_Cell] = []

    # A utility stacked behind the kitchen gets kitchen-width x a slice of the public row.
    # If that slice would be too shallow, the utility moves to the back row instead.
    r3_types = ("kitchen", "utility", "dining", "living", "family_hall")
    r3_est = sum(a[r.id] for r in rooms if r.type in r3_types) / wl
    kit_area = sum(a[r.id] for r in by_type.get("kitchen", []))
    util_area = sum(a[r.id] for r in by_type.get("utility", []))
    utility_in_r1 = bool(util_area) and (
        not kit_area
        or r3_est * util_area / (kit_area + util_area) < MIN_ROOM["utility"].short_side_cm
    )

    # ---------------------------------------------------------------- R1 private
    big = [r for r in rooms if r.type in BIG_PRIVATE]
    bigs_ids = {r.id for r in big}
    attached: dict[str, list[ProgramRoom]] = {r.id: [] for r in big}
    common: list[ProgramRoom] = []
    bedrooms = [r for r in big if r.type in ("master_bedroom", "bedroom")]
    for r in rooms:
        if r.type not in SMALL_PRIVATE and not (r.type == "utility" and utility_in_r1):
            continue
        owner = r.attached_to if r.attached_to in bigs_ids else None
        if owner is None and r.type == "dress" and bedrooms:
            owner = bedrooms[0].id
        if owner:
            attached[owner].append(r)
        else:
            common.append(r)

    lobby = (by_type.get("lobby") or by_type.get("passage") or [None])[0]
    lobby_id = lobby.id if lobby else _unique_id("lobby_1", a)

    r1_area = (
        sum(a[r.id] for r in big)
        + sum(a[r.id] for r in common)
        + sum(a[x.id] for xs in attached.values() for x in xs)
    )
    h1 = r1_area / wl if big or common else 0.0  # refined below so every column fits

    # Distribute common small rooms into suite side columns (front slot, on the lobby).
    suites = [r for r in big if attached[r.id]] or ([big[0]] if big and common else [])
    front_slot: dict[str, list[ProgramRoom]] = {s.id: [] for s in suites}
    for i, r in enumerate(common):
        if suites:
            front_slot[suites[i % len(suites)].id].append(r)
    loose = common if not suites else []

    small_area_of = {
        b.id: sum(a[s.id] for s in attached[b.id] + front_slot.get(b.id, [])) for b in big
    }
    loose_area = sum(a[s.id] for s in loose)

    def column_widths(h: float) -> list[tuple[float, float]]:
        """(room width, side column width) per big room, plus the loose column, at depth h."""
        cols = []
        for b in big:
            bed_w = max(MIN_ROOM[b.type].short_side_cm, a[b.id] / h)
            sa = small_area_of[b.id]
            cols.append((bed_w, max(SIDE_COLUMN_MIN_CM, sa / h) if sa else 0.0))
        if loose:
            cols.append((0.0, max(SIDE_COLUMN_MIN_CM, loose_area / h)))
        return cols

    if big or loose:
        # Deepen the back row until the columns (with their minimum widths) fit the plot
        # width. Total width only shrinks as depth grows, so a binary search works.
        lo, hi = max(h1, 250.0), dl * 0.55
        if sum(sum(c) for c in column_widths(hi)) > wl:
            return None
        if sum(sum(c) for c in column_widths(lo)) > wl:
            for _ in range(40):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if sum(sum(c) for c in column_widths(mid)) > wl else (lo, mid)
            h1 = hi
        else:
            h1 = lo
    cols = column_widths(h1)
    stretch = wl / sum(sum(c) for c in cols) if cols else 1.0  # fill the width exactly
    cols = [(bw * stretch, sw * stretch) for bw, sw in cols]

    x = 0.0
    for idx, b in enumerate(big):
        smalls_back = sorted(attached[b.id], key=lambda r: (r.type != "bath", r.type != "toilet"))
        smalls = smalls_back + front_slot.get(b.id, [])
        bed_w, side_w = cols[idx]
        col_w = bed_w + side_w
        side_first = idx % 2 == 1  # mirror alternate suites so baths cluster
        sx0 = x if side_first else x + bed_w
        bx0 = x + side_w if side_first else x
        cells.append(_cell(b, bx0, 0, bx0 + bed_w, h1))
        parent[b.id] = lobby_id
        if smalls:
            front = front_slot.get(b.id, [])
            stack_cells, extra = _stack(smalls_back, front, sx0, sx0 + side_w, 0, h1, a, b.type, a)
            cells.extend(stack_cells)
            for s in smalls_back:
                parent[s.id] = b.id
            for s in front:
                parent[s.id] = lobby_id
            if extra:
                added.append(extra)
                parent[extra.id] = b.id
        x += col_w
    if loose:
        w = cols[-1][1]
        stack_cells, extra = _stack([], loose, x, x + w, 0, h1, a, None, a)
        cells.extend(stack_cells)
        for s in loose:
            parent[s.id] = lobby_id
        if extra:
            added.append(extra)
            parent[extra.id] = lobby_id
        x += w
    r1_cells = list(cells)

    # ---------------------------------------------------------------- R3 public
    kitchen = (by_type.get("kitchen") or [None])[0]
    utility = [] if utility_in_r1 else by_type.get("utility", [])
    dining = (by_type.get("dining") or [None])[0]
    living = (by_type.get("living") or by_type.get("family_hall"))[0]
    others = [h for h in hubs if h.id != living.id]
    order: list[list[ProgramRoom]] = []
    if kitchen:
        order.append([kitchen, *utility])
    elif utility:
        order.append(list(utility))
    if dining:
        order.append([dining])
    order.extend([[h] for h in others])
    order.append([living])
    r3_area = sum(a[r.id] for col in order for r in col)

    # ---------------------------------------------------------------- R4 front
    foyer = (by_type.get("foyer") or [None])[0]
    front_open = by_type.get("garden", []) + by_type.get("parking", [])

    has_r1 = bool(r1_cells)
    lobby_h = 0.0
    if has_r1:
        lobby_h = max(120.0, min(180.0, a[lobby.id] / wl)) if lobby else LOBBY_DEPTH_CM
    h3 = r3_area / wl
    if front_open:  # the open front row can give up depth, so honour minimum room sides
        h3 = max(h3, *(MIN_ROOM[r.type].short_side_cm for col in order for r in col))
    h4 = sum(a[r.id] for r in front_open) / wl if front_open else 0.0
    foyer_h = 0.0  # set once the living room width is known
    rest = dl - h1 - lobby_h
    # Fit depths: open front rooms absorb the difference; otherwise scale R1/R3.
    if front_open:
        h4 = max(FRONT_ROW_MIN_CM, rest - h3)
        if rest - h4 < h3 * 0.8:
            return None
        h3 = rest - h4
    else:
        scale = (dl - lobby_h) / (h1 + h3) if (h1 + h3) else 1.0
        h1, h3 = h1 * scale, h3 * scale
        # rescale R1 cells vertically
        for c in r1_cells:
            c.y0, c.y1 = c.y0 * scale, c.y1 * scale

    y_lobby0, y_lobby1 = h1, h1 + lobby_h
    y3_0 = y_lobby1
    y3_1 = y3_0 + h3 if front_open else dl

    if has_r1:
        if not lobby:
            added.append(
                ProgramRoom(
                    id=lobby_id,
                    type="lobby",
                    label="LOBBY",
                    target_area_m2=wl * lobby_h / 10_000,
                    zone="circulation",
                )
            )
        cells.append(
            _Cell(lobby_id, "lobby", lobby.label if lobby else "LOBBY", 0, y_lobby0, wl, y_lobby1)
        )
        parent[lobby_id] = living.id

    # R3 columns
    x = 0.0
    col_bounds: list[tuple[list[ProgramRoom], float, float]] = []
    for col in order:
        w = sum(a[r.id] for r in col) / r3_area * wl
        col_bounds.append((col, x, x + w))
        x += w
    col_bounds[-1] = (col_bounds[-1][0], col_bounds[-1][1], wl)
    liv_x0, liv_x1 = col_bounds[-1][1], wl

    foyer_cell = None
    if foyer and not front_open:
        foyer_h = max(FRONT_ROW_MIN_CM, a[foyer.id] / (liv_x1 - liv_x0))
        foyer_cell = _cell(foyer, liv_x0, dl - foyer_h, liv_x1, dl)

    for col, cx0, cx1 in col_bounds:
        bottom = y3_1
        if foyer_cell and col[0].id == living.id:
            bottom = dl - foyer_h
        col_area = sum(a[r.id] for r in col)
        yy = y3_0
        # kitchen at the front of its column, utility behind it (towards the lobby)
        stack = list(reversed(col)) if len(col) > 1 else col
        for k, r in enumerate(stack):
            hh = (bottom - y3_0) * a[r.id] / col_area
            y_end = bottom if k == len(stack) - 1 else yy + hh
            cells.append(_cell(r, cx0, yy, cx1, y_end))
            yy = y_end
    if kitchen:
        parent[kitchen.id] = dining.id if dining else (others[0].id if others else living.id)
    for u in utility:
        parent[u.id] = kitchen.id if kitchen else (lobby_id if has_r1 else living.id)
    if dining:
        parent[dining.id] = others[0].id if others else living.id
    for h in others:
        parent[h.id] = living.id

    if foyer_cell:
        cells.append(foyer_cell)
    elif front_open or foyer:
        # R4 row: open rooms left, foyer at the east end under the living room
        x = 0.0
        fw = 0.0
        if foyer:
            fw = min(liv_x1 - liv_x0, max(SIDE_COLUMN_MIN_CM, a[foyer.id] / max(h4, 1)))
        span = wl - fw
        open_area = sum(a[r.id] for r in front_open)
        for i, r in enumerate(front_open):
            w = span * a[r.id] / open_area
            x1 = span if i == len(front_open) - 1 else x + w
            cells.append(_cell(r, x, y3_1, x1, dl))
            parent[r.id] = None
            x = x1
        if foyer:
            cells.append(_cell(foyer, wl - fw, y3_1, wl, dl))
    if foyer:
        parent[foyer.id] = None
        parent[living.id] = foyer.id
        root = foyer.id
    else:
        parent[living.id] = None
        root = living.id

    grid = Grid.for_plot(plot.width, plot.depth)
    out = [_to_room(c, road, wl, dl, grid) for c in cells]
    if any(r.w <= 0 or r.h <= 0 for r in out):
        return None
    return TemplateResult("compact_rows", out, parent, root, added)


def _unique_id(base: str, taken: dict) -> str:
    stem, n = base.rsplit("_", 1)[0], 1
    while f"{stem}_{n}" in taken:
        n += 1
    return f"{stem}_{n}"


def _cell(r: ProgramRoom, x0: float, y0: float, x1: float, y1: float) -> _Cell:
    return _Cell(r.id, r.type, r.label, x0, y0, x1, y1)


def _stack(back, front, x0, x1, y0, y1, a, owner_type, taken):
    """Stack small rooms in a column: `back` rooms at the back (y0), `front` rooms last
    (they touch the lobby). If the rooms are much smaller than the column, the gap
    between them becomes a DRESS (in a suite) or STORE so the column stays a tiling.
    """
    smalls = back + front
    width = x1 - x0
    full = y1 - y0
    total = sum(a[s.id] for s in smalls)
    natural = {s.id: a[s.id] / width for s in smalls}
    leftover = full - sum(natural.values())
    filler_type = "dress" if owner_type in ("master_bedroom", "bedroom") else "store"
    filler_min = MIN_ROOM[filler_type]
    if (
        total / width >= full * 0.82
        or leftover < max(filler_min.short_side_cm, 120)
        or width * leftover / 10_000 < filler_min.area_m2
    ):  # too small for a useful filler room: stretch the rooms to fill the column
        heights = {s.id: full * a[s.id] / total for s in smalls}
        leftover = 0.0
    else:
        heights = dict(natural)
    extra = None
    order: list = list(back)
    if leftover > 1:
        has_dress = any(s.type == "dress" for s in smalls)
        etype = (
            "dress" if owner_type in ("master_bedroom", "bedroom") and not has_dress else "store"
        )
        eid = _unique_id(f"{etype}_1", taken)
        taken[eid] = 1
        zone = "private" if etype == "dress" else "service"
        pr = ProgramRoom(
            id=eid,
            type=etype,
            label=DEFAULT_LABEL[etype],
            target_area_m2=round(width * leftover / 10_000, 2),
            zone=zone,
        )
        extra = pr
        order.append(pr)
        heights[eid] = leftover
    order.extend(front)
    cells: list[_Cell] = []
    yy = y0
    for i, r in enumerate(order):
        end = y1 if i == len(order) - 1 else yy + heights[r.id]
        cells.append(_cell(r, x0, yy, x1, end))
        yy = end
    return cells, extra


def _to_room(c: _Cell, road: str, wl: float, dl: float, grid: Grid) -> Room:
    x0, y0, x1, y1 = c.x0, c.y0, c.x1, c.y1
    if road == "north":
        x0, x1, y0, y1 = wl - x1, wl - x0, dl - y1, dl - y0
    elif road == "east":
        x0, x1, y0, y1 = y0, y1, wl - c.x1, wl - c.x0
    elif road == "west":
        x0, x1, y0, y1 = dl - y1, dl - y0, c.x0, c.x1
    sx0, sx1 = grid.snap_x(x0), grid.snap_x(x1)
    sy0, sy1 = grid.snap_y(y0), grid.snap_y(y1)
    return Room(id=c.id, type=c.type, label=c.label, x=sx0, y=sy0, w=sx1 - sx0, h=sy1 - sy0)
