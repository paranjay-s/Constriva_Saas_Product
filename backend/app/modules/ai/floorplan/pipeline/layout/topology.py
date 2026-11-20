"""Circulation topology: which room each room opens into (its parent).

Every room except the entrance room (root) gets exactly one parent and must share a
wall with it long enough for a door. Parent links form a tree rooted at the entrance,
so a layout that honours them is reachable by construction.
"""

from dataclasses import dataclass

from app.modules.ai.floorplan.rules import OPENING_END_CLEARANCE_CM
from app.modules.ai.floorplan.schemas.program import ProgramRoom, RoomProgram

CIRCULATION = ("lobby", "passage")
HUBS = ("family_hall", "living")
PRIVATE_LEAF = (
    "bedroom",
    "master_bedroom",
    "study",
    "store",
    "bath",
    "toilet",
    "maid_room",
    "prayer",
    "puja",
    "gym",
)
# reached from outside, no door
OPEN_EDGE = ("garden", "lawn", "parking", "driveway", "dock", "balcony", "pool")

ENTRANCE_DOOR_CM = 100


def door_width(room_type: str) -> int:
    """Door leaf opening (cm), taken as the clear width. Dubai Building Code K.5.4.1
    (Table K.4): general doors 915 mm, bathrooms and WCs 710 mm (RULES.md)."""
    if room_type in ("bath", "toilet"):
        return 75
    if room_type in ("store", "dress", "utility"):
        return 80
    return 95


def door_span_needed(room_type: str) -> int:
    """Minimum shared wall length (cm) for the door into a room of this type."""
    return door_width(room_type) + 2 * OPENING_END_CLEARANCE_CM + 6


@dataclass(frozen=True)
class Topology:
    root: str
    parent: dict[str, str | None]

    def children(self, room_id: str) -> list[str]:
        return [c for c, p in self.parent.items() if p == room_id]


def _first(program: RoomProgram, types: tuple[str, ...]) -> ProgramRoom | None:
    for t in types:
        for r in program.rooms:
            if r.type == t and r.block not in ("guest", "pool"):
                return r
    return None


SPECIAL_POOL = ("u_shape", "centre", "two_block")


def build_topology(program: RoomProgram) -> Topology:
    """Main house rooms hang off the entrance as before. With the pool inside the house
    (pool_layout u_shape / centre / two_block) the pool deck opens off the living room,
    the pool toilet opens onto the deck, and a guest block hangs off the deck through its
    lounge: living -> deck -> lounge -> guest rooms."""
    rooms = {r.id: r for r in program.rooms}
    foyer = _first(program, ("foyer",))
    hub = _first(program, HUBS)
    corridor = _first(program, CIRCULATION)
    dining = _first(program, ("dining",))
    kitchen = _first(program, ("kitchen",))
    bedrooms = [r for r in program.rooms if r.type in ("master_bedroom", "bedroom")]
    pool = next((r for r in program.rooms if r.type == "pool"), None)
    inner_pool = pool if pool and program.pool_layout in SPECIAL_POOL else None
    lounge = next((r for r in program.rooms if r.block == "guest" and r.type in HUBS), None)

    root = (foyer or hub or corridor or program.rooms[0]).id
    private_hub = (corridor or hub or foyer or program.rooms[0]).id
    public_hub = (hub or foyer or corridor or program.rooms[0]).id

    parent: dict[str, str | None] = {}
    for r in program.rooms:
        p: str | None
        if r.id == root:
            p = None
        elif r.attached_to and r.attached_to in rooms:
            p = r.attached_to
        elif inner_pool and r.id == inner_pool.id:
            p = public_hub  # the deck opens off the living room
        elif inner_pool and r.block == "pool":
            p = inner_pool.id  # pool toilet / changing room
        elif inner_pool and lounge and r.id == lounge.id:
            p = inner_pool.id  # the guest block is reached across the deck
        elif inner_pool and lounge and r.block == "guest":
            p = lounge.id
        elif r.type == "dress" and bedrooms:
            p = bedrooms[0].id
        elif r.type in PRIVATE_LEAF:
            p = private_hub
        elif r.type == "kitchen":
            p = (dining or hub or foyer or corridor or program.rooms[0]).id
        elif r.type in ("utility", "maid_room", "driver_room"):
            p = (kitchen or corridor or hub or program.rooms[0]).id
        elif r.type == "dining":
            p = public_hub
        elif r.type in HUBS:
            p = foyer.id if foyer else (hub.id if hub and hub.id != r.id else root)
        elif r.type in CIRCULATION:
            p = public_hub if public_hub != r.id else root
        elif r.type in OPEN_EDGE:
            p = None
        elif r.type in ("courtyard", "deck"):  # opens off the living room
            p = public_hub
        else:
            p = public_hub
        if p == r.id:
            p = root if r.id != root else None
        parent[r.id] = p
    # Any non-root room left without a parent (other than open edge areas) hangs off root.
    for rid, p in parent.items():
        if p is None and rid != root and rooms[rid].type not in OPEN_EDGE:
            parent[rid] = root
    _break_cycles(parent, root)
    return Topology(root=root, parent=parent)


def _break_cycles(parent: dict[str, str | None], root: str) -> None:
    for start in list(parent):
        seen = []
        node: str | None = start
        while node is not None and node not in seen:
            seen.append(node)
            node = parent.get(node)
        if node is not None and node != root:  # cycle found
            parent[seen[-1]] = root
