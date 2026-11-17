"""Surface areas for each application (plain Python, every step written down).

    floor / ceiling   room area
    all_walls         perimeter x height - doors - windows
    one_wall          that side x height - its openings (or a typed wall W x H)
    platform          kitchen counter runs along the walls (one wall, L, U, parallel, island).
                      The corner square is counted once, and a run never crosses a door
                      (door widths are taken off the side first).
    backsplash        length of the wall runs x backsplash height

Every value not given by the person or the plan comes from data/application_rules.json
and is listed as an assumption.
"""

from dataclasses import dataclass, field

from app.modules.ai.material_agent.data_files import application_rules
from app.modules.ai.material_agent.schemas import (
    ApplicationRequest,
    BreakdownLine,
    OpeningGeom,
    RoomGeom,
    SideGeom,
    TargetSpace,
)
from app.modules.ai.material_agent.units import fmt, round_half_up

LAYOUT_NAMES = {
    "one_wall": "one wall",
    "l_shape": "L-shape",
    "u_shape": "U-shape",
    "parallel": "parallel (galley)",
    "island": "island",
}
LAYOUT_OPTIONS = ["One wall", "L-shape", "U-shape", "Parallel", "Island"]


@dataclass
class AppArea:
    label: str
    area_sqft: float
    breakdown: list[BreakdownLine] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)


@dataclass
class NeedsInput:
    question: str
    options: list[str] = field(default_factory=list)
    missing: str = ""  # which field the answer fills: layout, room, space, side


def _line(label: str, formula: str, value: float) -> BreakdownLine:
    return BreakdownLine(label=label, formula=formula, value=round_half_up(value, 2))


def _opening_area(o: OpeningGeom) -> float:
    return o.width_ft * o.height_ft


def _doors_on(room: RoomGeom, side: int) -> list[OpeningGeom]:
    return [o for o in room.openings if o.kind == "door" and o.side == side]


def _usable(room: RoomGeom, side: SideGeom) -> float:
    return max(side.length_ft - sum(o.width_ft for o in _doors_on(room, side.index)), 0.0)


def _side_name(room: RoomGeom, s: SideGeom) -> str:
    return s.label or f"side {s.index + 1} ({fmt(s.length_ft)} ft)"


# ------------------------------------------------------------------ simple ones


def floor_area(room: RoomGeom, label: str = "Floor") -> AppArea:
    return AppArea(
        label=f"{room.name} floor" if label == "Floor" else label,
        area_sqft=room.area_sqft,
        breakdown=[_floor_line(room)],
    )


def _floor_line(room: RoomGeom) -> BreakdownLine:
    if (
        room.length_ft
        and room.width_ft
        and abs(room.length_ft * room.width_ft - room.area_sqft) < 0.5
    ):
        return _line("Floor area", f"{fmt(room.length_ft)} × {fmt(room.width_ft)}", room.area_sqft)
    return _line("Floor area", "from the plan outline", room.area_sqft)


def ceiling_area(room: RoomGeom) -> AppArea:
    a = floor_area(room)
    return AppArea(
        label=f"{room.name} ceiling",
        area_sqft=a.area_sqft,
        breakdown=[
            _line("Ceiling area (flat, same as floor)", a.breakdown[0].formula, a.area_sqft)
        ],
        assumptions=["Flat ceiling; coves, drops and beams are not included."],
    )


def all_walls_area(room: RoomGeom) -> AppArea:
    perimeter = sum(s.length_ft for s in room.sides)
    gross = perimeter * room.height_ft
    lines = [
        _line(
            "Wall area (all walls)",
            f"perimeter {fmt(perimeter)} × height {fmt(room.height_ft)}",
            gross,
        )
    ]
    net = gross
    for o in room.openings:
        net -= _opening_area(o)
        lines.append(
            _line(f"minus {o.kind}", f"{fmt(o.width_ft)} × {fmt(o.height_ft)}", -_opening_area(o))
        )
    return AppArea(label=f"{room.name} walls", area_sqft=max(net, 0.0), breakdown=lines)


def one_wall_area(room: RoomGeom, side: int | None) -> AppArea | NeedsInput:
    if not room.sides:
        return NeedsInput("How wide is the wall?", missing="space")
    if side is None or not 0 <= side < len(room.sides):
        options = [_side_name(room, s) for s in room.sides]
        return NeedsInput(f"Which wall of the {room.name.lower()}?", options, missing="side")
    s = room.sides[side]
    gross = s.length_ft * room.height_ft
    lines = [_line("Wall", f"{fmt(s.length_ft)} × {fmt(room.height_ft)}", gross)]
    net = gross
    for o in room.openings:
        if o.side == side:
            net -= _opening_area(o)
            lines.append(
                _line(
                    f"minus {o.kind}", f"{fmt(o.width_ft)} × {fmt(o.height_ft)}", -_opening_area(o)
                )
            )
    return AppArea(
        label=f"{room.name}, {_side_name(room, s)}", area_sqft=max(net, 0.0), breakdown=lines
    )


# ---------------------------------------------------------------- platform


def _choose_runs(room: RoomGeom, layout: str, depth: float) -> list[SideGeom] | None:
    """The sides the counter runs along, longest usable first (None if none fit)."""
    sides = room.sides
    n = len(sides)
    if n == 0:
        return None
    ok = [s for s in sides if _usable(room, s) > depth]
    if layout == "one_wall":
        return [max(ok, key=lambda s: _usable(room, s))] if ok else None
    if layout == "l_shape" and n >= 2:
        best: list[SideGeom] | None = None
        for i in range(n):
            pair = [sides[i], sides[(i + 1) % n]]
            if all(s in ok for s in pair):
                pair.sort(key=lambda s: -_usable(room, s))
                if best is None or sum(_usable(room, s) for s in pair) > sum(
                    _usable(room, s) for s in best
                ):
                    best = pair
        return best
    if layout == "u_shape" and n >= 3:
        best = None
        for i in range(n):
            trio = [sides[i], sides[(i - 1) % n], sides[(i + 1) % n]]  # middle first
            if all(s in ok for s in trio):
                total = sum(_usable(room, s) for s in trio)
                if best is None or total > sum(_usable(room, s) for s in best):
                    best = trio
        return best
    if layout == "parallel" and n == 4:
        best = None
        for i in range(2):
            pair = [sides[i], sides[i + 2]]
            if all(s in ok for s in pair):
                total = sum(_usable(room, s) for s in pair)
                if best is None or total > sum(_usable(room, s) for s in best):
                    best = pair
        return best
    return None


def _defaults_note(given: float | None, default: float, what: str) -> list[str]:
    return [] if given else [f"{what} {fmt(default)} ft (standard)."]


def platform_area(room: RoomGeom, req: ApplicationRequest) -> AppArea | NeedsInput:
    rules = application_rules()
    if req.layout is None:
        return NeedsInput(
            f"What is the layout of the {room.name.lower()} platform?",
            LAYOUT_OPTIONS,
            missing="layout",
        )
    depth = req.depth_ft or float(rules["platform_depth_ft"])
    assumptions = _defaults_note(req.depth_ft, depth, "Platform depth")
    name = LAYOUT_NAMES[req.layout]
    label = f"{room.name} platform ({name})"
    if req.layout == "island":
        ln, wd = float(rules["island_length_ft"]), float(rules["island_width_ft"])
        area = ln * wd
        return AppArea(
            label=label,
            area_sqft=area,
            breakdown=[_line("Island top", f"{fmt(ln)} × {fmt(wd)}", area)],
            assumptions=[
                f"Island size {fmt(ln)} × {fmt(wd)} ft (standard); tell me the real size."
            ],
        )
    runs = _choose_runs(room, req.layout, depth)
    if not runs:
        return NeedsInput(
            f"A {name} platform does not fit the {room.name.lower()} walls "
            f"(doors or short walls). Which layout should I use?",
            [
                o
                for o in LAYOUT_OPTIONS
                if o.lower().replace("-", "_").replace(" ", "_") != req.layout
            ],
            missing="layout",
        )
    lines: list[BreakdownLine] = []
    total = 0.0
    for i, s in enumerate(runs):
        usable = _usable(room, s)
        door_note = " minus door" if usable < s.length_ft else ""
        corner = i > 0 and req.layout in ("l_shape", "u_shape")
        run_len = usable - depth if corner else usable
        area = run_len * depth
        total += area
        length_txt = fmt(usable)
        if corner:
            formula = f"({length_txt} − {fmt(depth)}) × {fmt(depth)}"
            what = f"Run {i + 1} along {_side_name(room, s)}{door_note}, corner counted once"
        else:
            formula = f"{length_txt} × {fmt(depth)}"
            what = f"Run {i + 1} along {_side_name(room, s)}{door_note}"
        lines.append(_line(what, formula, area))
    if any(_doors_on(room, s.index) for s in runs):
        assumptions.append("The platform stops at doors (door widths taken off those walls).")
    return AppArea(label=label, area_sqft=total, breakdown=lines, assumptions=assumptions)


def backsplash_area(room: RoomGeom, req: ApplicationRequest) -> AppArea | NeedsInput:
    rules = application_rules()
    if req.layout is None:
        return NeedsInput(
            f"What is the layout of the {room.name.lower()} platform (the backsplash follows it)?",
            LAYOUT_OPTIONS,
            missing="layout",
        )
    if req.layout == "island":
        return NeedsInput(
            "An island has no wall behind it. Which wall layout should the backsplash follow?",
            [o for o in LAYOUT_OPTIONS if o != "Island"],
            missing="layout",
        )
    height = req.height_ft or float(rules["backsplash_height_ft"])
    depth = req.depth_ft or float(rules["platform_depth_ft"])
    runs = _choose_runs(room, req.layout, depth)
    if not runs:
        return NeedsInput(
            f"A {LAYOUT_NAMES[req.layout]} platform does not fit this room. Which layout?",
            LAYOUT_OPTIONS,
            missing="layout",
        )
    lines = []
    total = 0.0
    for s in runs:
        usable = _usable(room, s)
        area = usable * height
        total += area
        lines.append(
            _line(f"Backsplash on {_side_name(room, s)}", f"{fmt(usable)} × {fmt(height)}", area)
        )
    assumptions = _defaults_note(req.height_ft, height, "Backsplash height")
    assumptions.append("Windows above the platform are not taken off.")
    return AppArea(
        label=f"{room.name} backsplash ({LAYOUT_NAMES[req.layout]})",
        area_sqft=total,
        breakdown=lines,
        assumptions=assumptions,
    )


# ------------------------------------------------------------------ dispatch


def application_area(target: TargetSpace, req: ApplicationRequest) -> AppArea | NeedsInput:
    if target.wall is not None:
        wall = target.wall
        if req.application in ("one_wall", "all_walls"):
            gross = wall.width_ft * wall.height_ft
            lines = [_line(wall.label, f"{fmt(wall.width_ft)} × {fmt(wall.height_ft)}", gross)]
            net = gross
            for o in wall.openings:
                net -= _opening_area(o)
                lines.append(
                    _line(
                        f"minus {o.kind}",
                        f"{fmt(o.width_ft)} × {fmt(o.height_ft)}",
                        -_opening_area(o),
                    )
                )
            return AppArea(label=wall.label, area_sqft=max(net, 0.0), breakdown=lines)
        if req.application == "backsplash":
            h = req.height_ft or float(application_rules()["backsplash_height_ft"])
            area = wall.width_ft * h
            return AppArea(
                label=f"{wall.label} backsplash",
                area_sqft=area,
                breakdown=[_line("Backsplash", f"{fmt(wall.width_ft)} × {fmt(h)}", area)],
                assumptions=_defaults_note(req.height_ft, h, "Backsplash height"),
            )
        return NeedsInput(
            "That needs the room size, not one wall. What is the room length and width?",
            missing="space",
        )
    room = target.room
    if room is None:
        return NeedsInput("What are the room dimensions?", missing="space")
    match req.application:
        case "floor":
            return floor_area(room)
        case "ceiling":
            return ceiling_area(room)
        case "all_walls":
            return all_walls_area(room)
        case "one_wall":
            return one_wall_area(room, req.side)
        case "platform":
            return platform_area(room, req)
        case "backsplash":
            return backsplash_area(room, req)
    raise ValueError(req.application)


def rect_room(
    name: str,
    length_ft: float,
    width_ft: float,
    height_ft: float,
    *,
    kind: str = "",
    doors: int = 0,
    windows: int = 0,
) -> RoomGeom:
    """A rectangle room from typed dimensions (door/window positions unknown)."""
    rules = application_rules()
    sides = [
        SideGeom(index=0, length_ft=length_ft),
        SideGeom(index=1, length_ft=width_ft),
        SideGeom(index=2, length_ft=length_ft),
        SideGeom(index=3, length_ft=width_ft),
    ]
    openings = [
        OpeningGeom(
            kind="door",
            width_ft=float(rules["door_width_ft"]),
            height_ft=float(rules["door_height_ft"]),
        )
        for _ in range(doors)
    ] + [
        OpeningGeom(
            kind="window",
            width_ft=float(rules["window_width_ft"]),
            height_ft=float(rules["window_height_ft"]),
        )
        for _ in range(windows)
    ]
    return RoomGeom(
        name=name,
        kind=kind,
        area_sqft=length_ft * width_ft,
        height_ft=height_ft,
        sides=sides,
        openings=openings,
        length_ft=length_ft,
        width_ft=width_ft,
    )
