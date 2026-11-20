"""Where the swimming pool sits relative to the house, in one place.

    side       the pool touches a plot edge, beside the house (default)
    u_shape    the pool touches only the rear edge (away from the road); rooms on its
               other three sides, the open side faces the back garden
    centre     the pool touches no plot edge; rooms on all four sides (courtyard pool)
    two_block  the pool runs between a main block (road side: living, kitchen, master
               bedroom) and a guest block (other bedrooms + a lounge), reached across
               the pool deck

Everything here is plain geometry and rules; the solver, validator, room program and
generation fallback all read it, so they cannot disagree.

Coordinates are "road relative": depth d grows away from the road (0 = road edge),
across a runs along the road. That makes "front", "rear", "in front of the pool" the
same code for any road side.
"""

from dataclasses import dataclass, replace
from typing import Literal

from app.modules.ai.floorplan.pipeline.requirements import ReqRoom
from app.modules.ai.floorplan.rules import MIN_ROOM
from app.modules.ai.floorplan.units import fmt_length

Axis = Literal["front_back", "side_by_side"]
Layout = Literal["side", "u_shape", "centre", "two_block"]

RING_CM = 300  # rooms around a centre / U pool are at least this deep
BLOCK_CM = 330  # each block of a two-block villa is at least this deep
POOL_SIDE_CM = MIN_ROOM["pool"].short_side_cm  # water 3 m + walkway on both sides
STRIP_CM = 500  # depth of the pool zone between two blocks (target)
LINED_SHARE = 0.75  # each closed side of a centre / U pool is at least 75 % lined by rooms

FALLBACK: dict[str, tuple[str, ...]] = {
    "side": ("side",),
    "u_shape": ("u_shape", "side"),
    "centre": ("centre", "u_shape", "side"),
    "two_block": ("two_block", "u_shape", "side"),
}
NAMES = {
    "side": "pool beside the house",
    "u_shape": "U-shaped house around the pool",
    "centre": "pool in the middle of the house",
    "two_block": "pool between two blocks",
}
POOL_TOILET_ID = "toilet_pool"
LOUNGE_ID = "lounge_1"

# rooms that belong to the main (road side) block of a two-block villa
MAIN_TYPES = {
    "living",
    "family_hall",
    "dining",
    "kitchen",
    "foyer",
    "utility",
    "store",
    "maid_room",
    "stair",
    "study",
    "toilet",
}
OPEN_TYPES = {
    "garden",
    "lawn",
    "courtyard",
    "parking",
    "driveway",
    "dock",
    "balcony",
    "pool",
    "deck",
    "shaft",
}
BEDROOMS = ("master_bedroom", "bedroom")


def is_special(layout: str | None) -> bool:
    """True for the layouts that place the pool inside / between the house."""
    return layout in ("u_shape", "centre", "two_block")


# ------------------------------------------------------------------ road frame


def rear_side(road: str | None) -> str:
    return {"south": "north", "north": "south", "east": "west", "west": "east"}[road or "south"]


def plot_frame(width: int, depth: int, road: str | None) -> tuple[int, int]:
    """(across, deep): plot length along the road, and away from it."""
    return (width, depth) if (road or "south") in ("north", "south") else (depth, width)


def rect_frame(
    x: int, y: int, x2: int, y2: int, width: int, depth: int, road: str | None
) -> tuple[int, int, int, int]:
    """(d0, d1, a0, a1) of a rectangle: depth from the road edge and position along it."""
    road = road or "south"
    if road == "south":
        return depth - y2, depth - y, x, x2
    if road == "north":
        return y, y2, x, x2
    if road == "east":
        return width - x2, width - x, y, y2
    return x, x2, y, y2


# --------------------------------------------------------------------- fitting


@dataclass(frozen=True)
class Choice:
    layout: str
    axis: Axis | None = None


def _len(cm: int, unit: str) -> str:
    return fmt_length(cm, "ft" if unit == "ft" else "m")


def fits(
    layout: str, width: int, depth: int, road: str | None, bedrooms: int, unit: str = "ft"
) -> tuple[Choice | None, str]:
    """Can this layout work on the plot at all? (Choice, "") or (None, reason)."""
    across, deep = plot_frame(width, depth, road)
    if layout == "side":
        return Choice("side"), ""
    if layout == "centre":
        need = 2 * RING_CM + POOL_SIDE_CM
        if min(across, deep) < need:
            return None, (
                f"a pool in the middle needs rooms on all four sides, so the plot must be "
                f"at least {_len(need, unit)} each way"
            )
        return Choice("centre"), ""
    if layout == "u_shape":
        need_a, need_d = 2 * RING_CM + POOL_SIDE_CM, RING_CM + POOL_SIDE_CM
        if across < need_a or deep < need_d:
            return None, (
                f"a U-shaped house around the pool needs a plot at least "
                f"{_len(need_a, unit)} wide and {_len(need_d, unit)} deep"
            )
        return Choice("u_shape"), ""
    # two_block
    if bedrooms < 2:
        return None, "a two-block villa needs at least 2 bedrooms (one block for guests)"
    need = 2 * BLOCK_CM + POOL_SIDE_CM
    order: list[Axis] = (
        ["front_back", "side_by_side"]
        if deep >= across
        else [
            "side_by_side",
            "front_back",
        ]
    )
    for axis in order:
        span, other = (deep, across) if axis == "front_back" else (across, deep)
        if span >= need and other >= 2 * RING_CM:
            return Choice("two_block", axis), ""
    return None, (
        f"two blocks with a pool between them need the plot to be at least "
        f"{_len(need, unit)} in one direction"
    )


def layout_chain(
    requested: str | None,
    width: int,
    depth: int,
    road: str | None,
    bedrooms: int,
    unit: str = "ft",
) -> tuple[list[Choice], list[str]]:
    """Layouts to try in order (the request first, then simpler ones) and notes for
    any that were skipped because the plot is too small."""
    requested = requested or "side"
    chain: list[Choice] = []
    notes: list[str] = []
    for layout in FALLBACK[requested]:
        choice, why = fits(layout, width, depth, road, bedrooms, unit)
        if choice:
            chain.append(choice)
        elif not chain:  # only explain what was asked for but skipped
            notes.append(f"{NAMES[layout].capitalize()} is not possible here: {why}.")
    if notes and chain:
        notes[-1] += f" Using a {NAMES[chain[0].layout]} instead."
    return chain, notes


def pool_target_m2(choice: Choice, width: int, depth: int, road: str | None) -> float | None:
    """Pool + deck area for a pool inside the house (None = keep the usual size).

    Between two blocks the pool zone is a strip most of the way across the plot; a
    centre or U pool is a generous courtyard."""
    if choice.layout == "two_block":
        across, deep = plot_frame(width, depth, road)
        span = across if choice.axis == "front_back" else deep
        return 0.7 * span * STRIP_CM / 10_000
    if choice.layout in ("centre", "u_shape"):
        return max(36.0, 0.10 * width * depth / 10_000)
    return None


def fallback_note(tried: str, used: str) -> str:
    return (
        f"A {NAMES[tried]} did not fit with these rooms on this plot; used a {NAMES[used]} instead."
    )


# --------------------------------------------------------------- room program


def apply_layout(reqs: list[ReqRoom], choice: Choice) -> tuple[list[ReqRoom], list[str]]:
    """Add the rooms a layout needs and say which block each room is in.

    centre / two_block: a POOL TOILET (with shower) opening onto the deck.
    two_block: the main block keeps living, kitchen, dining and the master bedroom; the
    guest block gets the other bedrooms (with their baths), a common bath if needed and
    a LOUNGE as its hub. A person's own block choice (RoomRequest.block) always wins.
    """
    layout = choice.layout
    if not is_special(layout) or not any(r.type == "pool" for r in reqs):
        return reqs, []
    out = list(reqs)
    notes: list[str] = []
    if layout in ("centre", "two_block") and not any(r.id == POOL_TOILET_ID for r in out):
        out.append(ReqRoom(POOL_TOILET_ID, "toilet", "POOL TOILET", block="pool"))
        notes.append("Added a pool toilet with a shower next to the pool deck.")
    if layout != "two_block":
        return out, notes

    beds = [r for r in out if r.type in BEDROOMS]
    block: dict[str, str] = {}
    for r in beds:  # master in front, the rest behind, unless the person said otherwise
        block[r.id] = r.block or ("main" if r.type == "master_bedroom" else "guest")
    free = [r for r in beds if r.block is None]  # bedrooms the person did not place
    if free and all(b == "main" for b in block.values()):
        block[free[-1].id] = "guest"  # someone has to live in the guest block
    if free and all(b == "guest" for b in block.values()):
        block[free[0].id] = "main"
    for r in out:
        if r.attached_to in block:
            block[r.id] = block[r.attached_to]

    needs_bath = {"main": False, "guest": False}
    attached_to = {r.attached_to for r in out if r.type == "bath" and r.attached_to}
    for r in beds:
        if r.id not in attached_to:
            needs_bath[block[r.id]] = True
    commons = [r for r in out if r.type == "bath" and r.attached_to is None]
    for i, r in enumerate(commons):
        if r.block:
            block[r.id] = r.block
        elif needs_bath["guest"] and not any(block.get(c.id) == "guest" for c in commons[:i]):
            block[r.id] = "guest"
        else:
            block[r.id] = "main"
    if needs_bath["guest"] and not any(block.get(c.id) == "guest" for c in commons):
        n = len(commons) + 1
        out.append(ReqRoom(f"bath_c{n}", "bath", "BATH", block="guest"))
        block[f"bath_c{n}"] = "guest"
        notes.append("Added a bathroom in the guest block, so nobody crosses the pool for it.")

    main_beds = sum(1 for r in beds if block[r.id] == "main")
    result: list[ReqRoom] = []
    for r in out:
        if r.type in ("lobby", "passage") and r.block is None:
            if main_beds < 2:
                continue  # the main block's bedroom opens off the living room
            result.append(replace(r, block="main"))
        elif r.id in block:
            result.append(replace(r, block=block[r.id]))
        elif r.block:
            result.append(r)
        elif r.type in MAIN_TYPES:
            result.append(replace(r, block="main"))
        else:
            result.append(r)  # open areas belong to no block
    lounge = next((r for r in result if r.id == LOUNGE_ID), None)
    if lounge is None:
        result.append(ReqRoom(LOUNGE_ID, "family_hall", "LOUNGE", block="guest"))
    else:  # kept from an earlier two-block plan
        result[result.index(lounge)] = replace(lounge, block="guest")

    def beds_in(b: str) -> int:
        return sum(1 for r in result if r.block == b and r.type in BEDROOMS)

    def n_bed(n: int) -> str:
        return f"{n} bedroom{'s' if n != 1 else ''}"

    where = (
        "in front of and behind the pool"
        if choice.axis == "front_back"
        else "on either side of the pool"
    )
    main_beds_n = beds_in("main")
    notes.append(
        f"Two blocks {where}: the main block has the living room and kitchen"
        + (f" and {n_bed(main_beds_n)}" if main_beds_n else "")
        + f"; the guest block has {n_bed(beds_in('guest'))} and a lounge, "
        "reached across the pool deck."
    )
    return result, notes
