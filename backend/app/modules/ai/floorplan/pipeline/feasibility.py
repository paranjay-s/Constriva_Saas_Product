"""Feasibility check (code): do the requested rooms fit the plot at all?

Sum of minimum room areas (rules.MIN_ROOM) plus CIRCULATION_FACTOR for walls and
circulation must fit in the plot, and the plot must be wide and deep enough for one
room plus walls. If not, nothing is generated: the user gets the reason and options.
"""

from dataclasses import dataclass, field

from app.modules.ai.floorplan.pipeline.requirements import describe, expand_rooms
from app.modules.ai.floorplan.rules import (
    AREA_FLEXIBLE_TYPES,
    CIRCULATION_FACTOR,
    MIN_ROOM,
    WALL_EXTERIOR_CM,
)
from app.modules.ai.floorplan.schemas.brief import Brief
from app.modules.ai.floorplan.units import CM_PER_FT

OPTIONAL_TYPES = (
    "pool",
    "deck",
    "courtyard",
    "parking",
    "garden",
    "maid_room",
    "study",
    "store",
    "balcony",
    "dress",
    "majlis",
    "prayer",
    "puja",
    "bar",
    "gym",
    "driver_room",
    "lift",
    "lawn",
    "driveway",
    "dock",
)
MIN_PLOT_SIDE_CM = 300 + 2 * WALL_EXTERIOR_CM


@dataclass
class FeasibilityResult:
    ok: bool
    required_m2: float
    available_m2: float
    message: str = ""
    options: list[str] = field(default_factory=list)


def required_area_m2(brief: Brief) -> float:
    rooms, _ = expand_rooms(brief)
    base = sum(MIN_ROOM[r.type].area_m2 for r in rooms if r.type not in AREA_FLEXIBLE_TYPES)
    base += sum(MIN_ROOM[r.type].area_m2 for r in rooms if r.type in ("courtyard", "parking"))
    return round(base * (1 + CIRCULATION_FACTOR), 1)


def _area_text(m2: float, unit: str) -> str:
    if unit == "ft":
        return f"{m2 * 10.7639:,.0f} sq ft ({m2:,.0f} m2)"
    return f"{m2:,.0f} m2"


def check_feasibility(brief: Brief) -> FeasibilityResult:
    unit = brief.plot.input_unit
    w, d = brief.plot.width_cm, brief.plot.depth_cm
    if w is None or d is None:
        return FeasibilityResult(
            False, 0, 0, "The plot size is missing.", ["Enter the plot width and depth."]
        )
    available = round(w * d / 10_000, 1)
    required = required_area_m2(brief)

    if min(w, d) < MIN_PLOT_SIDE_CM:
        side = (
            f"{MIN_PLOT_SIDE_CM / CM_PER_FT:.0f} ft"
            if unit == "ft"
            else f"{MIN_PLOT_SIDE_CM / 100:.1f} m"
        )
        return FeasibilityResult(
            False,
            required,
            available,
            f"The plot is too narrow: each side must be at least {side} "
            "to fit a room and its walls.",
            ["Use a wider plot."],
        )
    if required <= available:
        from app.modules.ai.floorplan.pipeline.generate import plot_from_brief
        from app.modules.ai.floorplan.schemas.common import is_open

        rooms, _ = expand_rooms(brief)
        inside = sum(
            MIN_ROOM[r.type].area_m2
            for r in rooms
            if r.type not in AREA_FLEXIBLE_TYPES and not is_open(r.type)
        ) * (1 + CIRCULATION_FACTOR)
        x0, y0, x1, y1 = plot_from_brief(brief).buildable()
        buildable = round(max(0, x1 - x0) * max(0, y1 - y0) / 10_000, 1)
        if inside <= buildable:
            return FeasibilityResult(True, required, available)
        return FeasibilityResult(
            False,
            round(inside, 1),
            buildable,
            f"The rooms need about {_area_text(inside, unit)} of building, but inside the "
            f"setbacks the plot leaves only {_area_text(buildable, unit)}.",
            [
                "Use smaller setbacks (FLOORPLAN_SETBACK_* settings) if the plot's rules allow.",
                "Remove a room, or use a larger plot.",
            ],
        )

    options: list[str] = []
    beds = sum(r.count for r in brief.rooms if r.type in ("bedroom", "master_bedroom"))
    for n in range(beds - 1, 0, -1):
        trial = _with_bedrooms(brief, n)
        if required_area_m2(trial) <= available:
            options.append(f"Reduce to {n} bedroom{'s' if n != 1 else ''}.")
            break
    for t in OPTIONAL_TYPES:
        if any(r.type == t for r in brief.rooms):
            trial = brief.model_copy(update={"rooms": [r for r in brief.rooms if r.type != t]})
            if required_area_m2(trial) <= available:
                options.append(f"Remove the {t.replace('_', ' ')}.")
    options.append(f"Use a larger plot of at least {_area_text(required, unit)}.")
    message = (
        f"{describe(brief).capitalize()} and the other requested rooms need about "
        f"{_area_text(required, unit)} including walls and circulation; "
        f"the plot is {_area_text(available, unit)}."
    )
    return FeasibilityResult(False, required, available, message, options)


def _with_bedrooms(brief: Brief, n: int) -> Brief:
    rooms, left = [], n
    for r in sorted(brief.rooms, key=lambda r: r.type != "master_bedroom"):
        if r.type in ("bedroom", "master_bedroom"):
            if left <= 0:
                continue
            take = min(r.count, left)
            rooms.append(r.model_copy(update={"count": take}))
            left -= take
        else:
            rooms.append(r)
    baths = brief.bathrooms
    if baths is not None:
        baths = min(baths, max(1, n))
    return brief.model_copy(update={"rooms": rooms, "bedrooms": n, "bathrooms": baths})
