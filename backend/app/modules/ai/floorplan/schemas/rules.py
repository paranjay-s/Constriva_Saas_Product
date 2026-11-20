"""Layout rules: the spatial requests a person makes, as data the solver enforces.

The LLM turns words into rules; it never places anything. Rooms are named by a
reference: a room id ("kitchen_1"), a room type ("kitchen" = the first kitchen) or a label
("BAR"). `resolve_ref` maps a reference to an id once the rooms exist.

    touches       one room shares a wall with each of several others; with door=True a
                  door joins each pair (works for outdoor areas: "the pool touches the
                  kitchen, living and bar, each with a door onto it")
    door_between  a door between two named spaces (they must share a wall)
    place         front / rear / left / right / centre, relative to the facing (front =
                  the road side; left and right as seen from the road, facing the house)
    zone          public, private, service or outdoor
    size          minimum / maximum area and width, and the longest-to-shortest side ratio
    daylight      the room has an exterior wall (on the setback line or onto an open area)

Rules are hard constraints of the layout. Every generated or edited plan is checked
against them (validator RULE_...). When rules cannot all hold, the generator names the
rules that conflict and offers the closest layouts that drop one of them.
"""

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(default="", description="The person's words for this rule")


class Touches(_Rule):
    kind: Literal["touches"]
    room: str
    others: list[str] = Field(min_length=1)
    door: bool = False


class DoorBetween(_Rule):
    kind: Literal["door_between"]
    a: str
    b: str


class Place(_Rule):
    kind: Literal["place"]
    room: str
    side: Literal["front", "rear", "left", "right", "centre"]


class ZoneRule(_Rule):
    kind: Literal["zone"]
    room: str
    zone: Literal["public", "private", "service", "outdoor"]


class SizeRule(_Rule):
    kind: Literal["size"]
    room: str
    min_area_m2: float | None = Field(default=None, gt=0)
    max_area_m2: float | None = Field(default=None, gt=0)
    min_width_cm: int | None = Field(default=None, gt=0)
    max_width_cm: int | None = Field(default=None, gt=0)
    max_aspect: float | None = Field(default=None, ge=1.0, le=6.0)


class Daylight(_Rule):
    kind: Literal["daylight"]
    room: str


Rule = Annotated[
    Touches | DoorBetween | Place | ZoneRule | SizeRule | Daylight,
    Field(discriminator="kind"),
]


def rule_rooms(rule: _Rule) -> list[str]:
    """Every room reference a rule names."""
    if isinstance(rule, Touches):
        return [rule.room, *rule.others]
    if isinstance(rule, DoorBetween):
        return [rule.a, rule.b]
    return [rule.room]  # type: ignore[attr-defined]


def describe_rule(rule: _Rule, names: dict[str, str] | None = None) -> str:
    """A short plain description, for conflicts and the notes panel."""
    n = names or {}

    def nm(ref: str) -> str:
        return n.get(ref, ref.replace("_", " ").upper())

    if rule.text:
        return rule.text
    if isinstance(rule, Touches):
        others = ", ".join(nm(o) for o in rule.others)
        door = ", each with a door" if rule.door else ""
        return f"{nm(rule.room)} touches {others}{door}"
    if isinstance(rule, DoorBetween):
        return f"a door between {nm(rule.a)} and {nm(rule.b)}"
    if isinstance(rule, Place):
        return f"{nm(rule.room)} at the {rule.side}"
    if isinstance(rule, ZoneRule):
        return f"{nm(rule.room)} in the {rule.zone} zone"
    if isinstance(rule, SizeRule):
        parts = []
        if rule.min_area_m2:
            parts.append(f"at least {rule.min_area_m2:g} m²")
        if rule.max_area_m2:
            parts.append(f"at most {rule.max_area_m2:g} m²")
        if rule.min_width_cm:
            parts.append(f"at least {rule.min_width_cm / 100:g} m wide")
        if rule.max_width_cm:
            parts.append(f"at most {rule.max_width_cm / 100:g} m wide")
        if rule.max_aspect:
            parts.append(f"no longer than {rule.max_aspect:g} times its width")
        return f"{nm(rule.room)} " + ", ".join(parts)
    return f"{nm(rule.room)} gets daylight from an outside wall"  # type: ignore[attr-defined]


def resolve_ref(ref: str, rooms: list) -> str | None:
    """A room reference -> a room id: an id, else the first room of that type, else the
    first room whose label matches (ignoring case and spaces)."""
    ids = {r.id for r in rooms}
    if ref in ids:
        return ref
    key = ref.strip().lower().replace(" ", "_")
    for r in rooms:
        if r.type == key:
            return r.id
    label = ref.strip().upper().replace("_", " ")
    for r in rooms:
        if (r.label or "").upper() == label:
            return r.id
    for r in rooms:
        if label and label in (r.label or "").upper():
            return r.id
    return None


def resolve_rule(rule, rooms: list):
    """The rule with every reference replaced by a room id, or None if a room is missing."""
    data = rule.model_dump()
    for field in ("room", "a", "b"):
        if field in data:
            rid = resolve_ref(data[field], rooms)
            if rid is None:
                return None
            data[field] = rid
    if "others" in data:
        others = [resolve_ref(o, rooms) for o in data["others"]]
        if any(o is None for o in others):
            return None
        data["others"] = list(dict.fromkeys(others))
    return type(rule).model_validate(data)


_FILLER = {"ROOM", "AREA", "THE", "A", "AN", "AND", "OF", "WITH", "TO", "IN", "ON", "AT", "MY"}


def _words(text: str) -> set[str]:
    return set(re.findall(r"[A-Z]+", (text or "").upper())) - _FILLER


def _type_candidates(ref: str, rooms: list) -> list:
    """The rooms a type reference could mean, when there are several of that type."""
    if ref in {r.id for r in rooms}:
        return []
    key = ref.strip().lower().replace(" ", "_")
    same = [r for r in rooms if r.type == key]
    return same if len(same) > 1 else []


def resolve_rules(rules: list, rooms: list) -> list:
    """Every rule with its references replaced by room ids (None where a room is missing),
    like resolve_rule, but a room type with several rooms ("garden" when there is a front
    lawn and a backyard garden, "bath" with an attached and a common bath) goes to the
    right one:
      1. the room whose own label words appear in the rule's words ("front yard lawn" ->
         FRONT LAWN, "common washroom" -> COMMON BATH), when exactly one fits best;
      2. otherwise a room no other rule names yet, a room attached to another room only
         when the rule also names that room, then the first one.
    Rules are matched in two passes so a clear match is never taken by an earlier vague one.
    """
    from app.modules.ai.floorplan.schemas.common import DEFAULT_LABEL

    picks: dict[tuple[int, str, int], str] = {}  # (rule, field, position) -> room id
    pending: list[tuple[int, str, int, str]] = []
    named: set[str] = set()

    def refs(rule) -> list[tuple[str, int, str]]:
        out = []
        for f in ("room", "a", "b"):
            if hasattr(rule, f):
                out.append((f, 0, getattr(rule, f)))
        for k, o in enumerate(getattr(rule, "others", []) or []):
            out.append(("others", k, o))
        return out

    for i, rule in enumerate(rules):
        said = _words(rule.text)
        for f, k, ref in refs(rule):
            cands = _type_candidates(ref, rooms)
            if not cands:
                rid = resolve_ref(ref, rooms)
                if rid is not None:
                    picks[(i, f, k)] = rid
                    named.add(rid)
                continue
            # words every candidate's label shares say nothing about which one is meant
            labels = [_words(r.label or DEFAULT_LABEL.get(r.type, "")) for r in cands]
            generic = set.intersection(*labels)
            scores = [len((w - generic) & said) for w in labels]
            best = max(scores)
            if best > 0 and scores.count(best) == 1:
                rid = cands[scores.index(best)].id
                picks[(i, f, k)] = rid
                named.add(rid)
            else:
                pending.append((i, f, k, ref))

    for i, f, k, ref in pending:
        cands = _type_candidates(ref, rooms)
        others = {v for (j, _, _), v in picks.items() if j == i}

        def rank(r, others=others):
            attached = getattr(r, "attached_to", None)
            return (r.id in named, bool(attached) and attached not in others)

        rid = min(cands, key=rank).id
        picks[(i, f, k)] = rid
        named.add(rid)

    out = []
    for i, rule in enumerate(rules):
        data = rule.model_dump()
        missing = False
        for f, k, _ in refs(rule):
            rid = picks.get((i, f, k))
            if rid is None:
                missing = True
                break
            if f == "others":
                data["others"][k] = rid
            else:
                data[f] = rid
        if missing:
            out.append(None)
            continue
        if "others" in data:
            data["others"] = list(dict.fromkeys(data["others"]))
        out.append(type(rule).model_validate(data))
    return out
