"""Shared literal types for the floor plan schemas."""

from typing import Literal

Side = Literal["north", "south", "east", "west"]
Zone = Literal["public", "private", "service", "circulation", "open"]

# Where a swimming pool sits relative to the house (pipeline/pool_layouts.py):
#   side       touches a plot edge, beside the house (default)
#   u_shape    touches only the rear edge; rooms on its other three sides
#   centre     touches no plot edge; rooms on all four sides
#   two_block  runs between a main block (road side) and a guest block
PoolLayout = Literal["side", "u_shape", "centre", "two_block"]
# Which building a room belongs to in a two-block villa; "pool" = opens onto the deck
Block = Literal["main", "guest", "pool"]

RoomType = Literal[
    "bedroom",
    "master_bedroom",
    "living",
    "family_hall",
    "dining",
    "kitchen",
    "bath",
    "toilet",
    "dress",
    "store",
    "maid_room",
    "study",
    "lobby",
    "passage",
    "foyer",
    "utility",
    "stair",
    "courtyard",
    "garden",
    "balcony",
    "parking",
    "pool",
    "deck",
    "shaft",
    "other",
]

ZONE_BY_TYPE: dict[str, Zone] = {
    "bedroom": "private",
    "master_bedroom": "private",
    "dress": "private",
    "study": "private",
    "living": "public",
    "family_hall": "public",
    "dining": "public",
    "kitchen": "service",
    "bath": "service",
    "toilet": "service",
    "store": "service",
    "maid_room": "service",
    "utility": "service",
    "lobby": "circulation",
    "passage": "circulation",
    "foyer": "circulation",
    "stair": "circulation",
    "courtyard": "open",
    "garden": "open",
    "balcony": "open",
    "parking": "open",
    "pool": "open",
    "deck": "open",
    "shaft": "open",
    "other": "public",
}

WET_TYPES = frozenset({"bath", "toilet", "kitchen", "utility"})

DEFAULT_LABEL: dict[str, str] = {
    "bedroom": "BED ROOM",
    "master_bedroom": "MASTER BED ROOM",
    "living": "LIVING",
    "family_hall": "FAMILY HALL",
    "dining": "DINING",
    "kitchen": "KITCHEN",
    "bath": "BATH",
    "toilet": "TOILET",
    "dress": "DRESS",
    "store": "STORE",
    "maid_room": "MAID ROOM",
    "study": "STUDY",
    "lobby": "LOBBY",
    "passage": "PASSAGE",
    "foyer": "FOYER",
    "utility": "UTILITY",
    "stair": "STAIR",
    "courtyard": "COURTYARD",
    "garden": "GARDEN",
    "balcony": "BALCONY",
    "parking": "PARKING",
    "pool": "SWIMMING POOL",
    "deck": "SIT-OUT",
    "shaft": "OPEN",
    "other": "ROOM",
}


def is_open(room_type: str) -> bool:
    """Open areas have no enclosing walls of their own (courtyard, garden, pool, deck...)."""
    return ZONE_BY_TYPE.get(room_type) == "open"
