"""Room `boq_type`: what a room is used for, as the material calculator needs it.

Shared by the plan parser (which writes `boq_type`) and the calculator (which reads it and
derives it from the name when a stored plan has none). The rules are section 2 of
docs/materials_formula_spec.md.

`boq_type` is not `room.type`. `room.type` belongs to the 3D adapter and nothing here
reads or writes it.

Only indoor rooms are typed. The keyword rules are primary: a type supplied by the
parser's model is used only when the rules return OTHER, which covers Arabic and
abbreviated labels.
"""

from typing import Literal, get_args

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
