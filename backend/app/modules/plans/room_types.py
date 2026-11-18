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

# In order: the first rule with a keyword found in the lowercased name wins.
KEYWORD_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
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
    ),
    ("KITCHEN", ("kitchen", "pantry")),
    ("LAUNDRY", ("laundry", "utility", "wash")),
    ("CIRC", ("hallway", "corridor", "passage", "lobby", "foyer", "stair", "lift", "entrance")),
    ("LIVING", ("living", "majlis", "family", "lounge", "drawing", "sitting")),
    ("DINING", ("dining",)),
    ("STORE", ("store", "storage", "closet", "dressing", "wardrobe")),
    ("BED", ("bed", "master", "guest", "maid", "driver", "nanny")),
    ("STUDY", ("study", "office", "library")),
    ("LIVING", ("hall",)),
)

# A kitchen label that also names one of these is an open-plan living space.
OPEN_PLAN_WORDS = ("living", "dining", "family", "lounge", "hall")


def _first_rule(name: object) -> str:
    lower = str(name or "").lower()
    for boq_type, keywords in KEYWORD_RULES:
        if any(keyword in lower for keyword in keywords):
            return boq_type
    return "OTHER"


def is_open_plan_kitchen(name: object) -> bool:
    """True for a label such as "Living / Dining / Kitchen".

    Such a room is typed LIVING and one kitchen is counted for it.
    """
    lower = str(name or "").lower()
    return _first_rule(lower) == "KITCHEN" and any(word in lower for word in OPEN_PLAN_WORDS)


def boq_type_from_name(name: object) -> str:
    """The type the keyword rules give a room name. OTHER when no rule matches."""
    if is_open_plan_kitchen(name):
        return "LIVING"
    return _first_rule(name)


def valid_boq_type(value: object) -> str | None:
    """`value` as a type code, or None when it is not one."""
    text = str(value or "").strip().upper()
    return text if text in BOQ_TYPES else None


def resolve_boq_type(name: object, supplied: object = None) -> str:
    """Type for a freshly parsed indoor room: the rules, then the model's own answer."""
    by_rule = boq_type_from_name(name)
    if by_rule != "OTHER":
        return by_rule
    return valid_boq_type(supplied) or "OTHER"


def stored_or_derived_boq_type(name: object, stored: object = None) -> str:
    """Type for a room of a stored plan: its `boq_type` when valid, else the rules."""
    return valid_boq_type(stored) or boq_type_from_name(name)


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
