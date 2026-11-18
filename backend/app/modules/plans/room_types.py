"""Room `boq_kind` and `boq_type`: how the material calculator sees a room.

Shared by the plan parser (which writes both keys) and the calculator (which reads them
and derives them when a stored plan has none). The rules are section 2 of
docs/materials_formula_spec.md.

Neither key is the 3D adapter's. `room.kind` and `room.type` belong to the 3D code:
`room.kind` is read here and never changed, `room.type` is never read or written.

`boq_kind` starts from `room.kind` and differs from it in two cases: parking and driveways
are outdoor (paved area, outside the built area), and a semi-open room whose name is a
bathroom, kitchen or laundry ("Wash", "Washroom") is indoor.

Only rooms whose `boq_kind` is indoor are typed. The keyword rules are primary: a type
supplied by the parser's model is used only when the rules return OTHER, which covers
Arabic and abbreviated labels.
"""

import re
from typing import Literal, get_args

BOQ_KINDS: tuple[str, ...] = ("indoor", "semi_open", "outdoor", "void")

# Paved outdoor area whatever the 3D kind says (spec section 2.1, rule 2).
PARKING_WORDS = ("parking", "car park", "car porch", "carport", "driveway")
# A semi-open room named as one of these is an indoor room for the BOQ (rule 3).
WET_ROOM_TYPES = ("BATH", "KITCHEN", "LAUNDRY")

BoqType = Literal[
    "BATH", "KITCHEN", "LAUNDRY", "CIRC", "LIVING", "DINING", "STORE", "BED", "STUDY", "OTHER"
]
BOQ_TYPES: tuple[str, ...] = get_args(BoqType)

# In order: the first matching rule wins. A rule matches when the lowercased name contains
# one of its keywords, or when one of its abbreviations is a whole word of the name.
# (type, keywords found anywhere in the name, abbreviations matched as whole words)
KEYWORD_RULES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "BATH",
        (
            "bath",
            "toilet",
            "toi",
            "wc",
            "w.c",
            "washroom",
            "powder",
            "lavatory",
            "restroom",
            "shower",
            "ensuite",
        ),
        ("bth",),
    ),
    ("KITCHEN", ("kitchen", "pantry"), ("kit",)),
    ("LAUNDRY", ("laundry", "utility", "wash"), ("util",)),
    ("CIRC", ("hallway", "corridor", "passage", "lobby", "foyer", "stair", "lift", "entrance"), ()),
    (
        "LIVING",
        ("living", "majlis", "family", "lounge", "drawing", "sitting"),
        ("drg", "liv", "lvg"),
    ),
    ("DINING", ("dining",), ("din",)),
    ("STORE", ("store", "storage", "closet", "dress", "wardrobe"), ()),
    ("BED", ("bed", "master", "guest", "maid", "driver", "nanny"), ("br", "bdr", "mbr")),
    ("STUDY", ("study", "office", "library"), ()),
    ("LIVING", ("hall",), ()),
)

# A kitchen label that also matches one of these rules is an open-plan living space.
OPEN_PLAN_TYPES = ("LIVING", "DINING")
# A pantry smaller than this is a store, not a kitchen.
SMALL_PANTRY_MAX_M2 = 4.0
# A bathroom whose label also names one of these is a combined dressing and toilet room.
DRESSING_WORDS = ("dress", "closet", "wardrobe")
# Share of a combined dressing and toilet room that is the bathroom.
DRESS_BATH_SHARE = 0.5


def _words(lower: str) -> set[str]:
    """The runs of letters of a name: "drg./din. 12'x14'" gives drg, din, x."""
    return set(re.findall(r"[a-z]+", lower))


def _matching_types(name: object) -> list[str]:
    """Every rule the name matches, in rule order (a type can appear twice)."""
    lower = str(name or "").lower()
    words = _words(lower)
    return [
        boq_type
        for boq_type, keywords, abbreviations in KEYWORD_RULES
        if any(keyword in lower for keyword in keywords)
        or any(abbreviation in words for abbreviation in abbreviations)
    ]


def _first_rule(name: object) -> str:
    matches = _matching_types(name)
    return matches[0] if matches else "OTHER"


def is_open_plan_kitchen(name: object) -> bool:
    """True for a label such as "Living / Dining / Kitchen" or "KIT./DIN.".

    Such a room is typed LIVING and one kitchen is counted for it.
    """
    matches = _matching_types(name)
    return bool(matches) and matches[0] == "KITCHEN" and any(t in OPEN_PLAN_TYPES for t in matches)


def is_small_pantry(name: object, area_m2: float | None) -> bool:
    """True for a room that is a kitchen only by the word pantry and is under 4 m2."""
    if area_m2 is None or area_m2 >= SMALL_PANTRY_MAX_M2:
        return False
    lower = str(name or "").lower()
    return (
        _first_rule(lower) == "KITCHEN"
        and "pantry" in lower
        and "kitchen" not in lower
        and "kit" not in _words(lower)
    )


def is_dress_bath(name: object) -> bool:
    """True for a combined dressing and toilet room, such as "DRESS/TOI."."""
    lower = str(name or "").lower()
    return _first_rule(lower) == "BATH" and any(word in lower for word in DRESSING_WORDS)


def boq_type_from_name(name: object, area_m2: float | None = None) -> str:
    """The type the rules give a room. OTHER when no rule matches.

    `area_m2` is the room's area, used only for the pantry rule; without it a pantry is a
    kitchen.
    """
    if is_open_plan_kitchen(name):
        return "LIVING"
    if is_small_pantry(name, area_m2):
        return "STORE"
    return _first_rule(name)


def valid_boq_type(value: object) -> str | None:
    """`value` as a type code, or None when it is not one."""
    text = str(value or "").strip().upper()
    return text if text in BOQ_TYPES else None


def resolve_boq_type(name: object, supplied: object = None, area_m2: float | None = None) -> str:
    """Type for a freshly parsed indoor room: the rules, then the model's own answer."""
    by_rule = boq_type_from_name(name, area_m2)
    if by_rule != "OTHER":
        return by_rule
    return valid_boq_type(supplied) or "OTHER"


def stored_or_derived_boq_type(
    name: object, stored: object = None, area_m2: float | None = None
) -> str:
    """Type for a room of a stored plan: its `boq_type` when valid, else the rules."""
    return valid_boq_type(stored) or boq_type_from_name(name, area_m2)


# --------------------------------------------------------------------------- boq_kind


def is_parking(name: object) -> bool:
    """True for parking, car park, car porch, carport and driveway labels."""
    lower = " ".join(str(name or "").lower().split())
    return any(word in lower for word in PARKING_WORDS)


def valid_boq_kind(value: object) -> str | None:
    text = str(value or "").strip().lower()
    return text if text in BOQ_KINDS else None


def boq_kind_from(name: object, kind: object) -> str | None:
    """`boq_kind` of a room from its name and its `room.kind` (spec section 2.1).

    `kind` is never changed by this: the result is a second key next to it. None when
    `kind` is not one of the four kinds, so the caller can classify the room first.
    """
    base = valid_boq_kind(kind)
    if base is None or base == "void":
        return base
    if is_parking(name):
        return "outdoor"
    if base == "semi_open" and _first_rule(name) in WET_ROOM_TYPES:
        return "indoor"
    return base


def stored_or_derived_boq_kind(name: object, kind: object, stored: object = None) -> str | None:
    """Kind for a room of a stored plan: its `boq_kind` when valid, else the rules."""
    return valid_boq_kind(stored) or boq_kind_from(name, kind)
