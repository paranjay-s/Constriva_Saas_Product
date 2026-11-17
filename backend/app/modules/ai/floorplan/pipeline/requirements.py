"""Brief -> the exact list of rooms to plan, with stable ids (code, not the LLM).

Ids: bed_1.. (master first), bath_k / dress_k attached to bed_k, bath_c1.. for common
bathrooms, then <type>_<n> for every other room. A lobby is added for 3+ bedrooms so
every bedroom can open onto circulation.
"""

from dataclasses import dataclass

from app.modules.ai.floorplan.schemas.brief import Brief
from app.modules.ai.floorplan.schemas.common import DEFAULT_LABEL

BEDROOM_TYPES = ("master_bedroom", "bedroom")


@dataclass(frozen=True)
class ReqRoom:
    id: str
    type: str
    label: str
    attached_to: str | None = None
    block: str | None = None  # two-block villa: "main" / "guest" / "pool" (opens on deck)


def _label(t: str, label: str | None) -> str:
    return (label or DEFAULT_LABEL[t]).strip().upper()[:24]


def expand_rooms(brief: Brief) -> tuple[list[ReqRoom], list[str]]:
    rooms: list[ReqRoom] = []
    notes: list[str] = []
    beds = sorted(
        (r for r in brief.rooms if r.type in BEDROOM_TYPES),
        key=lambda r: r.type != "master_bedroom",
    )

    attached = 0
    n = 0
    for req in beds:
        for _ in range(req.count):
            n += 1
            bid = f"bed_{n}"
            rooms.append(ReqRoom(bid, req.type, _label(req.type, req.label), block=req.block))
            if req.attached_bath:
                rooms.append(ReqRoom(f"bath_{n}", "bath", "BATH", attached_to=bid, block=req.block))
                attached += 1
            if req.dress_room:
                rooms.append(
                    ReqRoom(f"dress_{n}", "dress", "DRESS", attached_to=bid, block=req.block)
                )

    explicit_common = sum(r.count for r in brief.rooms if r.type == "bath")
    if brief.bathrooms is None:
        # about one common bath for every two bedrooms that have no attached bath
        without = n - attached
        common = max(explicit_common, (without + 1) // 2 if without > 0 else (1 if n == 0 else 0))
        notes.append(f"Bathrooms not given: planned {attached + common} in total.")
    else:
        common = brief.bathrooms - attached
        if common < 0:
            notes.append(
                f"{attached} attached baths were asked for but only {brief.bathrooms} bathrooms; "
                f"keeping the {attached} attached baths."
            )
            common = 0
        if common == 0 and n - attached > 0:
            common = 1
            notes.append(
                "Some bedrooms have no attached bath, so a common bathroom was added "
                f"({attached + 1} bathrooms in total)."
            )
    for i in range(common):
        rooms.append(ReqRoom(f"bath_c{i + 1}", "bath", "BATH"))

    counters: dict[str, int] = {}
    for req in brief.rooms:
        if req.type in BEDROOM_TYPES or req.type == "bath":
            continue
        for _ in range(req.count):
            counters[req.type] = counters.get(req.type, 0) + 1
            rooms.append(
                ReqRoom(
                    f"{req.type}_{counters[req.type]}",
                    req.type,
                    _label(req.type, req.label),
                    block=req.block,
                )
            )

    if n >= 3 and not any(r.type in ("lobby", "passage") for r in rooms):
        rooms.append(ReqRoom("lobby_1", "lobby", "LOBBY"))
    return rooms, notes


def describe(brief: Brief) -> str:
    """Short human summary, e.g. '3 bedrooms (2 with attached bath), 2 bathrooms'."""
    beds = sum(r.count for r in brief.rooms if r.type in BEDROOM_TYPES)
    att = sum(r.count for r in brief.rooms if r.type in BEDROOM_TYPES and r.attached_bath)
    s = f"{beds} bedroom{'s' if beds != 1 else ''}"
    if att:
        s += f" ({att} with attached bath)" if att < beds else " with attached baths"
    return s
