"""Analysis tools the chat uses (deterministic; the LLM only phrases the result).

    profile(material)                 durability, water, care, installation, pros / cons
    suitability(material, place)      fits a wet / outdoor / hot / busy spot or not, and why
    alternatives(material, place)     catalog options for the same surface that suit the place
    compare(a, b)                     two profiles side by side
    supporting(lines)                 adhesive, grout, primer... from each material's net area
    totals(lines)                     one total per material across rooms
    substitute(material, new_name)    a catalog material in place of the photo's one
    parse_piece_size(text)            "2 x 4 ft tiles", "600x1200 mm" -> PieceSize

Knowledge lives in data/material_knowledge.json and data/material_rules.json (editable,
marked "to be verified with the architecture firm").
"""

import math
import re

from app.modules.ai.material_agent.data_files import catalog_by_id, knowledge, rules
from app.modules.ai.material_agent.normalise import match_catalog
from app.modules.ai.material_agent.schemas import Material, PieceSize, QuantityLine, SupportLine
from app.modules.ai.material_agent.space import room_kind
from app.modules.ai.material_agent.units import fmt, round_half_up, to_ft

NEEDS_TEXT = {
    "wet": "water resistance",
    "outdoor": "weather resistance",
    "heat": "heat resistance near the hob",
    "traffic": "heavy foot traffic",
}
NEED_FLAG = {"wet": "wet_ok", "outdoor": "outdoor_ok", "heat": "heat_ok", "traffic": "traffic_ok"}
PLACE_NEEDS = [  # words in a place -> needs (checked before room kinds)
    (r"\b(shower|wet|bath|toilet|washroom|wash area|utility|sink)", ["wet"]),
    (
        r"\b(outdoor|outside|exterior|facade|terrace|balcony|garden|pool|rain|sun)",
        ["outdoor", "wet"],
    ),
    (r"\b(hob|stove|cooktop|behind the cooking|platform|counter|backsplash)", ["heat", "wet"]),
    (r"\b(stair|entrance|lobby|corridor|commercial|shop|office floor|parking)", ["traffic"]),
]


# -------------------------------------------------------------------- profiles


def catalog_entry(m: Material | str | None) -> dict | None:
    if m is None:
        return None
    if isinstance(m, Material):
        return catalog_by_id().get(m.catalog_id or "") or match_catalog(m.name, m.surface)
    return catalog_by_id().get(m) or match_catalog(m)


def profile(m: Material | str) -> dict:
    """What we know about a material (category guidance + material-specific notes)."""
    entry = catalog_entry(m)
    k = knowledge()
    name = m.display_name if isinstance(m, Material) else (entry["name"] if entry else str(m))
    category = entry["category"] if entry else (m.category if isinstance(m, Material) else "other")
    base = dict(k["categories"].get(category, {}))
    if entry:
        base.update(k["materials"].get(entry["id"], {}))
    out = {
        "name": name,
        "catalog_name": entry["name"] if entry else None,
        "category": category,
        **base,
    }
    if isinstance(m, Material):
        out["seen_in_photo"] = {
            "surface": m.surface,
            "where": m.location,
            "finish": ", ".join(x for x in (m.finish, m.pattern, m.colour, m.size_hint) if x),
            "confidence": m.confidence,
            "recognised_from": m.evidence,
            "could_also_be": m.look_alikes,
        }
    return out


def place_needs(place: str) -> list[str]:
    low = (place or "").lower()
    for pat, needs in PLACE_NEEDS:
        if re.search(pat, low):
            return needs
    kind = room_kind(low)
    return list(knowledge()["room_needs"].get(kind or "", []))


def suitability(m: Material | str, place: str) -> tuple[bool | None, list[str]]:
    """(True / False / None if unknown, reasons)."""
    p = profile(m)
    needs = place_needs(place)
    if not needs:
        return (True if p.get("durability") else None), ["No special demands for this place."]
    reasons, ok = [], True
    for need in needs:
        flag = p.get(NEED_FLAG[need])
        if flag is False:
            ok = False
            reasons.append(f"Not suited: {place} needs {NEEDS_TEXT[need]}.")
        elif flag is True:
            reasons.append(f"Fine for {NEEDS_TEXT[need]}.")
    if p.get("water") and "wet" in needs:
        reasons.append(p["water"])
    return ok, reasons


def alternatives(m: Material | str, place: str = "", limit: int = 4) -> list[dict]:
    """Catalog options in place of `m` (same family first), filtered for the place."""
    p = profile(m)
    entry = catalog_entry(m)
    own = entry["id"] if entry else None
    ids = [i for i in p.get("alternatives", []) if i != own]
    surface = m.surface if isinstance(m, Material) else (entry["surfaces"][0] if entry else "")
    if len(ids) < limit and surface:  # fill up with other catalog materials for that surface
        ids += [
            e["id"]
            for e in catalog_by_id().values()
            if surface in e["surfaces"] and e["id"] not in ids and e["id"] != own
        ]
    out = []
    for i in ids:
        alt = profile(i)
        ok, why = suitability(i, place) if place else (True, [])
        if ok is False:
            continue
        out.append(
            {
                "name": alt["name"],
                "why": alt.get("pros", [])[:2],
                "watch_out": alt.get("cons", [])[:1],
                "suits_place": why[:1] if place else [],
            }
        )
        if len(out) >= limit:
            break
    return out


def compare(a: Material | str, b: Material | str) -> dict:
    keys = ("durability", "water", "maintenance", "install", "pros", "cons", "good_for", "avoid")
    pa, pb = profile(a), profile(b)
    return {
        "a": {k: pa.get(k) for k in ("name", *keys)},
        "b": {k: pb.get(k) for k in ("name", *keys)},
    }


# ------------------------------------------------------------ supporting items


def supporting(lines: list[QuantityLine], materials: list[Material]) -> list[SupportLine]:
    """Adhesive, grout, primer... per material from its net area (rules in material_rules.json)."""
    items = rules().get("supporting", {})
    by_id = {m.id: m for m in materials}
    # (material, item) -> net area; a counter top slab is fixed, not laid like a floor
    area: dict[tuple[str, str], float] = {}
    for ln in lines:
        m = by_id.get(ln.material_id)
        if m is None or ln.net_qty <= 0:
            continue
        p = profile(m)
        if "platform" in ln.application.lower():
            keys = ["countertop_sealant"] + (["sealer"] if p.get("category") == "stone" else [])
        else:
            keys = p.get("supporting", [])
        for key in keys:
            area[(m.id, key)] = area.get((m.id, key), 0.0) + ln.net_qty
    out: list[SupportLine] = []
    for (mid, key), net in area.items():
        rule = items.get(key)
        if not rule:
            continue
        per = float(rule["sqft_per_unit"])
        qty = math.ceil(round(net / per, 6))
        out.append(
            SupportLine(
                material_id=mid,
                material=by_id[mid].display_name,
                item=rule["name"],
                qty=qty,
                unit=unit_for(qty, rule["unit"]),
                basis=f"{fmt(net)} sq ft ÷ {fmt(per)} sq ft per "
                f"{unit_for(1, rule['unit']).split(' ')[0]}, rounded up",
            )
        )
    return out


def unit_for(qty: float, unit: str) -> str:
    """'bags (20 kg)' -> 'bag (20 kg)' for 1; 'kg' stays 'kg'."""
    if qty != 1:
        return unit
    first, _, rest = unit.partition(" ")
    if first.endswith("s") and first not in ("kg",):
        first = first[:-1]
    return f"{first} {rest}".strip()


def totals(lines: list[QuantityLine]) -> list[dict]:
    """One total per material across every room / surface it is used on."""
    acc: dict[str, dict] = {}
    for ln in lines:
        t = acc.setdefault(
            ln.material, {"material": ln.material, "total_sq_ft": 0.0, "places": [], "buy": {}}
        )
        t["total_sq_ft"] = round_half_up(t["total_sq_ft"] + ln.total_qty, 1)
        t["places"].append(ln.application)
        if ln.buy_qty is not None and ln.buy_unit:
            t["buy"][ln.buy_unit] = t["buy"].get(ln.buy_unit, 0) + ln.buy_qty
    return list(acc.values())


# ----------------------------------------------------------- substitute / sizes


def substitute(old: Material, new_name: str) -> Material:
    """The material to use instead (catalog entry if known), same place and share."""
    entry = match_catalog(new_name, old.surface)
    name = entry["name"] if entry else new_name.strip()[:120]
    return old.model_copy(
        update={
            "catalog_id": entry["id"] if entry else None,
            "name": name,
            "display_name": name[:1].upper() + name[1:],
            "category": entry["category"] if entry else old.category,
            "finish": "",
            "pattern": "",
            "colour": "",
            "size_hint": "",
            "confidence": "high",
            "look_alikes": [],
            "evidence": "chosen by you",
            "replaces": old.replaces or old.display_name,
        }
    )


_SIZE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(mm|cm|m|ft|feet|'|in|inch|\")?\s*(?:x|×|by|\*)\s*(\d+(?:\.\d+)?)\s*(mm|cm|m|ft|feet|'|in|inch|\")?",
    re.I,
)
_UNIT = {"feet": "ft", "'": "ft", "inch": "in", '"': "in"}


def parse_piece_size(text: str) -> PieceSize | None:
    """'2 x 4 ft tiles' / '600x1200 mm' / '800 x 1600' (numbers over 20 are taken as mm)."""
    m = _SIZE.search(text or "")
    if not m:
        return None
    a, b = float(m.group(1)), float(m.group(3))
    unit = (m.group(2) or m.group(4) or "").lower()
    unit = _UNIT.get(unit, unit) or ("mm" if max(a, b) > 20 else "ft")
    w, ln = to_ft(a, unit), to_ft(b, unit)
    if not (0 < w <= 20 and 0 < ln <= 20):
        return None
    return PieceSize(
        width_ft=round(w, 4), length_ft=round(ln, 4), label=f"{fmt(a)} × {fmt(b)} {unit}"
    )
