"""Read-only answers about a plan, computed by code (never by the LLM):

    report(plan, "areas")     plot, built-up, approx. carpet and open areas, ground coverage
    report(plan, "schedule")  room schedule: name, size, area
    report(plan, "openings")  doors and windows per room, rooms without daylight
    report(plan, "orientation")  which way the house and each room face, sun on the windows
    report(plan, "help")      what can be asked / changed

The sun notes assume a site north of the tropics (low sun from the south, hot afternoon
sun from the west) and are to be verified with the architecture firm.
"""

from typing import Literal

from app.modules.ai.floorplan.pipeline.plan_tools import facing
from app.modules.ai.floorplan.rules import WALL_EXTERIOR_CM, WALL_INTERIOR_CM
from app.modules.ai.floorplan.schemas.plan import FloorPlan, Room
from app.modules.ai.floorplan.units import fmt_area, fmt_length, fmt_size

InfoTopic = Literal["areas", "schedule", "openings", "orientation", "help"]

HABITABLE = (
    "bedroom",
    "master_bedroom",
    "living",
    "family_hall",
    "dining",
    "kitchen",
    "study",
    "maid_room",
)


def zone_of(r: Room, plan: FloorPlan) -> str:
    """One of 9 zones: north-west ... centre (thirds of the plot in each direction)."""
    cx, cy = (r.x + r.w / 2) / plan.plot.width, (r.y + r.h / 2) / plan.plot.depth
    ns = "north" if cy < 1 / 3 else ("south" if cy > 2 / 3 else "")
    ew = "west" if cx < 1 / 3 else ("east" if cx > 2 / 3 else "")
    return "-".join(p for p in (ns, ew) if p) or "centre"


def _rooms(plan: FloorPlan) -> list[Room]:
    return [r for r in plan.rooms if r.type != "shaft"]


def _carpet_m2(r: Room) -> float:
    """Clear floor inside the walls: room sizes are measured on wall centre lines, so half
    of each wall's thickness comes off every side (exterior and interior averaged)."""
    t = (WALL_EXTERIOR_CM + WALL_INTERIOR_CM) / 2
    return max(0.0, (r.w - t) * (r.h - t) / 10_000)


def areas(plan: FloorPlan) -> list[str]:
    unit = plan.meta.unit_display
    rooms = _rooms(plan)
    enclosed = [r for r in rooms if not r.is_open]
    open_ = [r for r in rooms if r.is_open]
    built = sum(r.area_m2 for r in enclosed)
    carpet = sum(_carpet_m2(r) for r in enclosed)
    plot = plan.plot.width * plan.plot.depth / 10_000
    lines = [
        "**Area statement**",
        f"- Plot: {fmt_size(plan.plot.width, plan.plot.depth, unit)} = {fmt_area(plot, unit)}",
        f"- Built-up (covered) area: {fmt_area(built, unit)}",
        f"- Approx. carpet area (inside the walls): {fmt_area(carpet, unit)}",
        f"- Open areas ({len(open_)}): {fmt_area(sum(r.area_m2 for r in open_), unit)}",
        f"- Ground coverage: {built / plot * 100:.0f}% of the plot",
    ]
    face = facing(plan)
    if face:
        lines.append(f"- Facing: {face} (main entrance on the {face} side)")
    lines.append(
        "Built-up is measured to the wall centre lines; carpet area deducts the walls "
        "(to be confirmed against the local building rules)."
    )
    return lines


def schedule(plan: FloorPlan) -> list[str]:
    unit = plan.meta.unit_display
    lines = ["**Room schedule**"]
    for r in sorted(_rooms(plan), key=lambda r: (r.is_open, -r.area_m2)):
        lines.append(
            f"- {r.label}: {fmt_size(r.w, r.h, unit)}, {fmt_area(r.area_m2, unit)} "
            f"({zone_of(r, plan)})"
        )
    return lines


def openings(plan: FloorPlan) -> list[str]:
    unit = plan.meta.unit_display
    names = {r.id: r.label for r in plan.rooms}
    lines = ["**Doors**"]
    for d in plan.doors:
        frm = names[d.from_room] if d.from_room else "OUTSIDE"
        kind = "opening" if d.swing == "none" else "door"
        lines.append(
            f"- {d.id}: {frm} -> {names[d.to_room]}, {fmt_length(d.width, unit)} {kind} "
            f"({d.wall} wall)"
        )
    lines.append("**Windows**")
    for r in _rooms(plan):
        wins = [w for w in plan.windows if w.room == r.id]
        if wins:
            lines.append(
                f"- {r.label}: "
                + ", ".join(f"{w.id} {fmt_length(w.width, unit)} {w.wall}" for w in wins)
            )
    dark = [
        r.label
        for r in _rooms(plan)
        if r.type in HABITABLE and not any(w.room == r.id for w in plan.windows)
    ]
    if dark:
        lines.append(
            "No window (needs daylight and air): "
            + ", ".join(dark)
            + ". Say 'add a window to ...' or move the room to an outside wall."
        )
    return lines


SUN_NOTE = {
    "north": "steady, glare-free daylight",
    "east": "morning sun",
    "south": "sun most of the day",
    "west": "hot afternoon sun",
}


def orientation(plan: FloorPlan) -> list[str]:
    face = facing(plan)
    lines = ["**Orientation**"]
    if face:
        lines.append(f"- The house faces {face} (road and main entrance on the {face} side).")
    for r in _rooms(plan):
        if r.is_open and r.type not in ("garden", "courtyard", "pool", "deck"):
            continue
        walls = sorted({w.wall for w in plan.windows if w.room == r.id})
        light = "; ".join(f"{w} window: {SUN_NOTE[w]}" for w in walls) or "no window"
        lines.append(f"- {r.label}: {zone_of(r, plan)} part of the plot ({light})")
    hot = [
        r.label
        for r in _rooms(plan)
        if r.type in ("bedroom", "master_bedroom")
        and {w.wall for w in plan.windows if w.room == r.id} == {"west"}
    ]
    if hot:
        lines.append(
            "Bedrooms lit only from the west get the afternoon heat: "
            + ", ".join(hot)
            + ". Shading, or a window on another wall, helps."
        )
    lines.append(
        "Sun notes assume a site north of the tropics (to be verified with the architecture "
        "firm). To change the direction, say e.g. 'make it east facing' or 'mirror the plan'."
    )
    return lines


def help_text(plan: FloorPlan) -> list[str]:
    return [
        "**What I can do with this plan**",
        "- Rooms: make bigger / smaller or an exact size, move, swap, add, remove, rename, "
        "change use (e.g. 'make the study a bedroom')",
        "- Direction: 'make it east facing', 'rotate 90 degrees', 'mirror the plan'",
        "- Doors: add, remove, move, change width (e.g. 'make the main door 4 ft')",
        "- Windows: add, remove, change width",
        "- Plot: change the plot size; pool position (side, centre, U-shape, two blocks)",
        "- Drawing: show sizes in feet, metres or cm",
        "- History: 'undo', 'go back to version 3'",
        "- Checks: 'area statement', 'room schedule', 'doors and windows', "
        "'which way do the rooms face'",
    ]


REPORTS = {
    "areas": areas,
    "schedule": schedule,
    "openings": openings,
    "orientation": orientation,
    "help": help_text,
}


def report(plan: FloorPlan, topic: InfoTopic) -> str:
    return "\n".join(REPORTS[topic](plan))
