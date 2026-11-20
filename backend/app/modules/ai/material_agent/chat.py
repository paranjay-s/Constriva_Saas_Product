"""Follow-up messages -> ChatIntent (the LLM only classifies; code does the rest).

Order:
  1. a money question is answered with a fixed sentence (no LLM),
  2. an answer to the last question ("L-shape", one of the offered rooms) is merged into
     the pending request without an LLM call when it matches an option,
  3. otherwise the LLM returns a ChatIntent; without an LLM a small keyword reader is
     used so the feature still works offline.
"""

import json
import logging
import re

from app.modules.ai.llm.client import LLMClient, LLMError
from app.modules.ai.material_agent.data_files import catalog
from app.modules.ai.material_agent.normalise import find_material, match_catalog
from app.modules.ai.material_agent.schemas import ChatIntent, ManualSpace, Material
from app.modules.ai.material_agent.space import room_kind
from app.modules.ai.material_agent.vision import prompt

logger = logging.getLogger("construtiva.ai.material.chat")

MONEY_ANSWER = (
    "This tool identifies materials and calculates quantities only; it does not give money "
    "figures. You can share the quantity list with the firm or your supplier for that."
)
_MONEY = re.compile(
    r"(\bcost|\bprice|\bpricing|\bbudget|\bexpens|\bcheap|\bafford|\bquote|\bquotation|"
    r"\brupee|\brs\.?\s*\d|₹|\$|\binr\b|\bhow much (will|would|does) (it|this|that) (be|take)\b|"
    r"\bper (sq|square) ?(ft|feet|foot|m) (rate|charge)|\brate\b|\bcharges?\b|\bspend)",
    re.I,
)

LAYOUT_WORDS = [
    ("l_shape", r"\bl[\s-]?shape|\bl[\s-]?shaped|\bl\b"),
    ("u_shape", r"\bu[\s-]?shape|\bu[\s-]?shaped|\bu\b"),
    ("parallel", r"\bparallel|\bgalley|two walls|opposite walls"),
    ("island", r"\bisland"),
    ("one_wall", r"\bone[\s-]?wall|\bstraight|\bsingle wall|\blinear|\bin[\s-]?line"),
]
APPLICATION_WORDS = [
    ("backsplash", r"\bback ?splash|\bdado|\bbacksplash"),
    ("platform", r"\bplatform|\bcounter ?tops?|\bcounters?|\bslab top|\bkitchen top"),
    ("ceiling", r"\bceiling"),
    ("floor", r"\bfloor(ing)?\b"),
    ("all_walls", r"\ball (the )?walls|\bwalls\b|\bwall cladding everywhere"),
    ("one_wall", r"\bwall\b"),
]
_UNIT = r"(ft|feet|foot|'|m|metres?|meters?|cm|mm|in|inch(es)?|\")"
_DIMS = re.compile(
    rf"(\d+(?:\.\d+)?)\s*{_UNIT}?\s*(?:x|×|by|\*)\s*(\d+(?:\.\d+)?)\s*{_UNIT}?"
    rf"(?:\s*(?:x|×|by|\*)\s*(\d+(?:\.\d+)?)\s*{_UNIT}?)?",
    re.I,
)
_HEIGHT = re.compile(
    rf"(?:height|high|tall)\D{{0,12}}(\d+(?:\.\d+)?)\s*{_UNIT}?|(\d+(?:\.\d+)?)\s*{_UNIT}?\s*(?:high|tall|height)",
    re.I,
)
_WASTAGE = re.compile(
    r"(\d+(?:\.\d+)?)\s*%?\s*(?:percent\s*)?wastage|wastage\D{0,12}(\d+(?:\.\d+)?)", re.I
)
_DEPTH = re.compile(
    rf"(?:depth|deep)\D{{0,12}}(\d+(?:\.\d+)?)\s*{_UNIT}?|(\d+(?:\.\d+)?)\s*{_UNIT}?\s*deep", re.I
)
_PROJECT = re.compile(r"\bproject\s*(?:named|called)?\s*[:\-]?\s*[\"']?([^\"'?.,]+)", re.I)


_WHOLE_DESIGN = re.compile(
    r"\b(replicat\w*|same (design|look|style|finish\w*|interior)|this (design|look|style)|"
    r"copy (this|the) (design|look)|whole (design|look|room|house)|all (the )?materials|"
    r"every(thing| material)|all (the )?quantit\w*|all quantit\w*|complete (list|design)|"
    r"full (list|design|bill)|according to (my|the) (floor )?plan|in my (floor )?plan|"
    r"(on|to|for) my (floor )?plan)",
    re.I,
)


_EXPLAIN_QTY = re.compile(
    r"\b(how (did|do|does|was|were|is|are) (you|it|this|that|the)\b.*\b(calculat|comput|get|"
    r"arriv|come|work|reach|find)|how (you|u) (calculat|got|get)|why\b.*\b(wastage|waste|"
    r"sheets?|boxes|litres?|liters?|round|share|percent|%|sq ?ft|quantity|quantities|number|so "
    r"(much|many|high|low))|where (does|did) .*\b(come from|from)|explain (the |this |that |your )?"
    r"(calculation|quantit|number|math|working|breakdown|wastage)|show (me )?(the )?"
    r"(working|calculation|math|steps)|what (did you|have you) assum|assumptions?\b|breakdown)",
    re.I,
)


def is_quantity_question(text: str) -> bool:
    """'how did you calculate this?', 'why 10% wastage?', 'why 3 sheets?'."""
    return bool(_EXPLAIN_QTY.search(text))


def is_whole_design(text: str) -> bool:
    """'replicate this design in my floor plan', 'all materials', 'same look for my kitchen'."""
    return bool(_WHOLE_DESIGN.search(text))


def is_money_question(text: str) -> bool:
    return bool(_MONEY.search(text))


def _unit(u: str | None) -> str | None:
    if not u:
        return None
    u = u.lower()
    if u in ("'", "ft", "feet", "foot"):
        return "ft"
    if u in ('"', "in", "inch", "inches"):
        return "in"
    if u.startswith("met") or u == "m":
        return "m"
    return u if u in ("cm", "mm") else None


def layout_in(text: str) -> str | None:
    t = text.lower()
    for value, pat in LAYOUT_WORDS:
        if re.search(pat, t):
            return value
    return None


def application_in(text: str) -> str | None:
    t = text.lower()
    for value, pat in APPLICATION_WORDS:
        if re.search(pat, t):
            return value
    return None


_STOP = {
    "how",
    "much",
    "many",
    "what",
    "for",
    "the",
    "of",
    "in",
    "on",
    "my",
    "a",
    "an",
    "is",
    "need",
    "needed",
    "do",
    "i",
    "we",
    "to",
    "and",
    "with",
    "use",
    "will",
    "it",
    "this",
    "that",
    "be",
    "should",
    "can",
    "you",
    "please",
    "there",
    "about",
    "tell",
    "me",
    "explain",
    "shape",
    "layout",
    "wall",
    "walls",
    "project",
    "plan",
    "sq",
    "ft",
    "feet",
    "required",
}


def _material_words(low: str, materials: list[Material]) -> str:
    """The material named in the message, without the room / surface words around it.

    Returns the session material's name when one matches, otherwise the catalog word the
    person used ("granite"), so the reply can say it is not in the photo.
    """
    tokens = [
        w
        for w in re.findall(r"[a-z]+", low)
        if w not in _STOP
        and len(w) > 1
        and not room_kind(w)
        and not application_in(w)
        and not layout_in(w)
    ]
    text = " ".join(tokens)
    if not text:
        return ""
    found = find_material(materials, text) if materials else []
    if len(found) == 1:
        return found[0].name
    for t in tokens:
        one = find_material(materials, t) if materials else []
        if len(one) == 1:
            return one[0].name
    entry = match_catalog(text)
    return text if entry else ""


_PIECE = re.compile(r"\b(tiles?|slabs?|sheets?|planks?|pieces?|panels?|boards?)\b", re.I)
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", re.I)
_SWAP = re.compile(
    r"\b(instead|replace|replacing|swap|switch|change (it |this |that )?to|go with|"
    r"use .+ in place)\b",
    re.I,
)
_ALTERNATIVES = re.compile(
    r"\b(alternatives?|other options?|options? (for|instead)|substitutes?|similar|something else|"
    r"what else (can|could|should) (i|we) use|what (can|could|should) (i|we) use|instead of|"
    r"replacement|better (option|material|choice)|make it better|improve|upgrade)\b",
    re.I,
)
_COMPARE = re.compile(
    r"\b(vs\.?|versus|compare|comparison|difference between|better than|which is better)\b", re.I
)
_SUITABLE = re.compile(
    r"\b(can (i|we|it|this|that) (use|be used|go)|suitable|good (for|in)|ok (for|in)|fine (for|in)|"
    r"work (in|for|outside|outdoors)|waterproof|water ?resist|outdoors?|outside|bathroom|wet area|"
    r"near (the )?(hob|stove|sink))\b",
    re.I,
)
_MAINT = re.compile(
    r"\b(maintain|maintenance|clean|cleaning|care|upkeep|polish(ing)? again)\b", re.I
)
_DURABLE = re.compile(
    r"\b(durab\w*|how long|last|scratch\w*|stain\w*|strong|chip\w*|crack\w*|life ?span|wear)\b",
    re.I,
)
_INSTALL = re.compile(
    r"\b(install\w*|fix(ed|ing)? on|lay(ing)?|fitting|apply|applied|"
    r"how (is|do you) (it )?(put|fit))\b",
    re.I,
)
_PROS = re.compile(
    r"\b(pros|cons|advantages?|disadvantages?|benefits?|downsides?|good and bad)\b", re.I
)
_SUPPORT = re.compile(
    r"\b(adhesive|grout|primer|putty|sealer|underlay|plywood|backing|consumables?|accessor\w*|"
    r"supporting|what else (do|will|would) (i|we) need|along with|other things needed)\b",
    re.I,
)
_TOTALS = re.compile(
    r"\b(total|totals|altogether|overall|combined|sum|grand total|whole house)\b", re.I
)
_DESIGN = re.compile(
    r"\b(design|look|style|colou?r|small room|space|feel|theme|suit|match|go with|combination|"
    r"aesthetic|modern|luxur\w*|warm|cozy|bright|dark)\b",
    re.I,
)
_ADVICE = re.compile(
    r"\b(alternatives?|instead|substitut\w*|compare|vs|versus|suitable|maintain|maintenance|"
    r"durab\w*|install\w*|pros|cons)\b",
    re.I,
)


_WANTS_QTY = re.compile(
    r"\b(quantit\w*|how much|how many|replicat\w*|materials? (needed|required)|"
    r"all (the )?materials|"
    r"floor ?plan|my plan)\b",
    re.I,
)


def catalog_mentions(text: str) -> list[str]:
    """Catalog material names mentioned in the text, in order ('marble', 'quartz')."""
    low = f" {re.sub(r'[^a-z0-9 ]+', ' ', text.lower())} "
    found: list[tuple[int, int, str]] = []
    for entry in catalog():
        for alias in entry["aliases"]:
            a = re.sub(r"[^a-z0-9 ]+", " ", alias.lower()).strip()
            i = low.find(f" {a} ")
            if a and i >= 0:
                found.append((i, -len(a), a))
    found.sort()
    out: list[str] = []
    end = -1
    for i, neg_len, a in found:
        if i >= end:
            out.append(a)
            end = i - neg_len
    return out


def tool_intent(t: str, materials: list[Material], material: str, room: str) -> ChatIntent | None:
    """The analysis tools: sizes, shares, swaps, supporting items, totals, advice."""
    low = t.lower()
    if _PIECE.search(low) and re.search(r"\d\s*(?:x|×|by|\*)\s*\d", low):
        return ChatIntent(action="set_piece_size", material=material, question=t[:200])
    pct = _PERCENT.search(low)
    if pct and "wastage" not in low and "waste" not in low:
        return ChatIntent(action="set_coverage", material=material, percent=float(pct.group(1)))
    if _SUPPORT.search(low):
        return ChatIntent(action="supporting_materials", material=material)
    if _TOTALS.search(low) and not _DESIGN.search(low):
        return ChatIntent(action="totals")
    names = catalog_mentions(low)
    in_photo = [n for n in names if find_material(materials, n)]
    if _COMPARE.search(low) and len(names) >= 2:
        return ChatIntent(
            action="advise",
            topic="compare",
            material=names[0],
            other_material=names[1],
            question=t[:200],
        )
    if (
        _SWAP.search(low)
        and not _ALTERNATIVES.search(low.replace("instead", ""))
        or (re.search(r"\b(use|go with|switch to)\b", low) and "instead" in low)
    ):
        new = [n for n in names if not find_material(materials, n)] or names[-1:]
        old = in_photo[0] if in_photo else material
        if new and old and new[0] in old:
            old = ""  # "use quartz instead": the old one is the material talked about last
        m = re.search(r"\breplace (\w[\w ]*?) with (\w[\w ]*)", low)
        if m:
            old, new = m.group(1), [m.group(2)]
        if new and (not old or new[0] not in old):
            return ChatIntent(action="substitute", material=old, other_material=new[0])
    topic = None
    if _ALTERNATIVES.search(low):
        topic = "alternatives"
    elif _COMPARE.search(low):
        topic = "compare"
    elif _SUITABLE.search(low):
        topic = "suitability"
    elif _MAINT.search(low):
        topic = "maintenance"
    elif _DURABLE.search(low):
        topic = "durability"
    elif _INSTALL.search(low):
        topic = "installation"
    elif _PROS.search(low):
        topic = "pros_cons"
    elif (
        _DESIGN.search(low)
        and re.match(r"\s*(is|will|would|does|do|should|can|how|what|which)\b", low)
        and not _WANTS_QTY.search(low)
    ):
        topic = "general"  # a design question, not "give me the quantities for this design"
    if topic is None:
        return None
    place = ""
    for word in (
        "bathroom",
        "outdoor",
        "outside",
        "kitchen",
        "balcony",
        "terrace",
        "shower",
        "floor",
        "wall",
    ):
        if word in low:
            place = word
            break
    return ChatIntent(
        action="advise",
        topic=topic,  # type: ignore[arg-type]
        material=material if topic != "general" else "",
        place=place or room,
        question=t[:200],
    )


def keyword_intent(text: str, materials: list[Material]) -> ChatIntent:
    """Offline reader for the common requests (used when no LLM is configured)."""
    t = text.strip()
    low = t.lower()
    if is_money_question(t):
        return ChatIntent(action="money_question")
    data: dict = {}
    if m := _DIMS.search(t):
        data["length"] = float(m.group(1))
        data["width"] = float(m.group(4))
        if m.group(7):
            data["height"] = float(m.group(7))
        data["unit"] = _unit(m.group(2)) or _unit(m.group(5)) or "ft"
    if (h := _HEIGHT.search(t)) and "height" not in data:
        data["height"] = float(h.group(1) or h.group(3))
        data["unit"] = data.get("unit") or _unit(h.group(2) or h.group(4)) or "ft"
    if d := _DEPTH.search(t):
        data["depth"] = float(d.group(1) or d.group(3))
    if w := _WASTAGE.search(t):
        data["wastage_pct"] = float(w.group(1) or w.group(2))
    if p := _PROJECT.search(t):
        if not re.search(r"\b(plan|upload|attach)", low):
            data["project_name"] = p.group(1).strip()
    layout = layout_in(t)
    application = application_in(t)
    room = next(
        (
            w
            for w in re.findall(r"[a-z]+(?: \d+)?", low)
            if room_kind(w) and w not in ("room", "bed")
        ),
        "",
    )
    material = _material_words(low, materials)
    if application == "platform" and not room:
        room = "kitchen"
    if "project_name" in data and not (application or material):
        return ChatIntent(action="use_project", **data)
    if re.search(r"\b(only|now|just) (the )?(ceiling|floor|wall|tv wall|backsplash|facade)", low):
        return ChatIntent(action="change_focus", focus=t)
    if is_quantity_question(t) and not _ADVICE.search(low):
        return ChatIntent(
            action="explain_quantity",
            material=material,
            application=application,  # type: ignore[arg-type]
            question=t[:200],
        )
    if re.search(r"\b(what is|what's|explain|tell me about|how did you|why)\b", low) and material:
        return ChatIntent(action="explain_material", material=material)
    tool = tool_intent(t, materials, material, room)
    if tool is not None:
        return tool
    if is_whole_design(t) and not (material and application):
        return ChatIntent(
            action="apply_all",
            room=room if room != "kitchen" or "kitchen" in low else "",
            layout=layout,  # type: ignore[arg-type]
            **data,
        )
    if application or (material and room):
        return ChatIntent(
            action="apply_material",
            material=material,
            application=application,  # type: ignore[arg-type]
            room=room,
            layout=layout,  # type: ignore[arg-type]
            **data,
        )
    if data:
        return ChatIntent(action="recalculate", **data)
    if layout:
        return ChatIntent(action="unclear", layout=layout)  # type: ignore[arg-type]
    return ChatIntent(action="unclear", question="")


def llm_intent(llm: LLMClient, text: str, context: dict) -> ChatIntent:
    user = "Context:\n" + json.dumps(context, ensure_ascii=False) + "\n\nMessage:\n" + text
    return llm.structured(
        system=prompt("material_chat"), user=user, schema=ChatIntent, task="material_chat"
    )


def interpret(
    llm: LLMClient | None, text: str, materials: list[Material], context: dict
) -> ChatIntent:
    if is_money_question(text):
        return ChatIntent(action="money_question")
    if llm is not None:
        try:
            return llm_intent(llm, text, context)
        except LLMError as e:
            logger.info("material chat LLM failed (%s); using keywords", e)
    return keyword_intent(text, materials)


def answer_to_pending(text: str, pending: dict) -> dict | None:
    """Fill the missing field from a direct answer ('L-shape', an offered option)."""
    missing = pending.get("missing")
    options: list[str] = pending.get("options") or []
    low = text.strip().lower()
    chosen = next((o for o in options if o.lower() == low), None)
    if chosen is None:
        chosen = next((o for o in options if low and (low in o.lower() or o.lower() in low)), None)
    intent = dict(pending.get("intent") or {})
    if missing == "layout":
        layout = layout_in(chosen or text)
        if layout:
            intent["layout"] = layout
            return intent
        return None
    if missing == "room" and pending.get("rooms"):
        return _room_answer(text, pending, intent)
    if chosen is None:
        return None
    if missing == "room":
        intent["room"] = pending.get("option_values", {}).get(chosen, chosen)
        return intent
    if missing == "material":
        intent["material"] = chosen
        return intent
    if missing == "application":
        intent["application"] = application_in(chosen) or intent.get("application")
        return intent
    if missing == "other_material":
        intent["other_material"] = chosen
        return intent
    if missing == "project":
        intent["project_name"] = chosen
        return intent
    if missing == "side":
        intent["__side"] = options.index(chosen)
        return intent
    return None


def _room_answer(text: str, pending: dict, intent: dict) -> dict | None:
    """A typed or tapped answer to "which room?": by button, number, ordinal, size, name,
    several at once ("toilet 1 and 3") or "all of them" (space.pick_rooms)."""
    from app.modules.ai.material_agent.schemas import RoomGeom
    from app.modules.ai.material_agent.space import pick_rooms

    rooms = [RoomGeom.model_validate(r) for r in pending["rooms"]]
    values: dict = pending.get("option_values") or {}
    labels = [o for o in pending.get("options") or [] if o != "All of them"][: len(rooms)]
    got = pick_rooms(text, rooms, labels if len(labels) == len(rooms) else None)
    if got is None:
        from app.modules.ai.material_agent.space import match_room

        m = match_room(rooms, text)
        narrower = m.status == "ambiguous" and len(m.options) < len(rooms)
        if narrower or m.room is not None:
            # "Toilet" when the choices were every room: narrow to the toilets (a new,
            # shorter question) or take the one room of that kind
            got = [rooms.index(m.room)] if m.room is not None else None
            if got is None:
                intent["room"] = text.strip()
                return intent
    if got is None:
        return None
    if got == "all":
        if "All of them" in values:
            intent["room"] = values["All of them"]
            return intent
        got = list(range(len(rooms)))
    picks = [values.get(labels[i], "") for i in got] if len(labels) == len(rooms) else []
    picks = [p.split(":", 1)[1] for p in picks if p.startswith("__pick__:")]
    if not picks:
        return None
    intent["room"] = "__pick__:" + ",".join(picks)
    return intent


_WALL_WORDS = re.compile(r"\b(wall|facade|façade|backsplash|elevation|partition)\b", re.I)
_LABEL_WORDS = re.compile(
    r"\b((?:tv|feature|accent|bed ?back|headboard|kitchen|living|bedroom)\s+wall)\b", re.I
)


def space_from_text(text: str) -> ManualSpace | None:
    """A size typed in the first prompt: 'TV wall 12 x 10 ft' -> wall 12 x 10;
    'kitchen 10 x 8 ft' -> room 10 x 8; 'living 14 x 12 x 10 ft' -> room with height."""
    m = _DIMS.search(text or "")
    if not m:
        return None
    a, b = float(m.group(1)), float(m.group(4))
    c = float(m.group(7)) if m.group(7) else None
    unit = _unit(m.group(2)) or _unit(m.group(5)) or _unit(m.group(8)) or "ft"
    if c is None and _WALL_WORDS.search(text):
        label = _LABEL_WORDS.search(text)
        name = label.group(1).title().replace("Tv ", "TV ") if label else "Wall"
        return ManualSpace(kind="wall", unit=unit, length=a, height=b, label=name)  # type: ignore[arg-type]
    room = next(
        (
            w
            for w in re.findall(r"[a-z]+(?: \d+)?", text.lower())
            if room_kind(w) and w not in ("room", "bed")
        ),
        "",
    )
    return ManualSpace(
        kind="room", unit=unit, length=a, width=b, height=c, label=room.title() or "Room"
    )  # type: ignore[arg-type]
