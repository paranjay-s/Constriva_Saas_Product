"""Room `kind` rules shared by the plan parser and the material calculator.

`kind` says how a space is built: indoor, semi_open, outdoor, or void (a shaft, duct or
open-to-sky cut-out with no floor slab). Rooms that are outdoor or void get no masonry,
slab or flooring quantities.

The word "open" needs care. Matching it anywhere in the name used to turn "Open Kitchen"
into a void. It now marks a void only as "open to sky" / "open shaft", or when the label
is the bare word OPEN (optionally with its size, e.g. `OPEN 4'6"X10'4"`), which is how
drawings label an open-to-sky cut-out.
"""

import re

from app.modules.plans.schemas import RoomKind

ROOM_KINDS: tuple[RoomKind, ...] = ("indoor", "semi_open", "outdoor", "void")

OPEN_VOID_PHRASES = ("open to sky", "open shaft")

# Words that only describe a size, so `OPEN 3' WD.` still counts as a bare OPEN label.
_SIZE_WORDS = frozenset({"x", "wd", "wide", "ft", "feet", "in", "inch", "m", "mm", "cm"})

# The parser's rules. A keyword in the name wins over the kind the model reported.
PARSER_OUTDOOR_WORDS = ("lawn", "garden", "backyard", "yard")
PARSER_SEMI_OPEN_WORDS = (
    "park",
    "car",
    "driveway",
    "garage",
    "porch",
    "verandah",
    "veranda",
    "stair",
    "balcony",
    "terrace",
    "patio",
    "deck",
    "sitout",
    "wash",
)
PARSER_VOID_WORDS = ("shaft", "duct", "void")


def is_open_void_label(name: str | None) -> bool:
    """True for "open to sky", "open shaft" and a bare OPEN label; False for "Open Kitchen"."""
    lower = " ".join(str(name or "").lower().split())
    if any(phrase in lower for phrase in OPEN_VOID_PHRASES):
        return True
    words = [w for w in re.findall(r"[a-z]+", lower) if w not in _SIZE_WORDS]
    return words == ["open"]


def parser_room_kind(name: str | None, reported: object = None) -> RoomKind:
    """Kind for a freshly parsed room: name keywords first, then the model's own answer."""
    lower = str(name or "").lower()
    if any(word in lower for word in PARSER_OUTDOOR_WORDS):
        return "outdoor"
    if any(word in lower for word in PARSER_SEMI_OPEN_WORDS):
        return "semi_open"
    if any(word in lower for word in PARSER_VOID_WORDS) or is_open_void_label(lower):
        return "void"
    text = str(reported or "").lower().strip()
    for kind in ROOM_KINDS:
        if text == kind:
            return kind
    return "indoor"
