"""Room types and the labels that name them, read from web/rooms.json (the one list for the detector, the furniture
rules, the builder, the review page and our backend's converter).

classify("GUEST BEDROOM") -> ("bedroom", "exact"). The label's words are matched against each type's phrases, longest
phrase first (SERVICE LIFT before LIFT, STAIRCASE HALL before HALL), ties by the priority list; then abbreviations at
the start of a word (KIT., BEDR); then near spellings of words of five letters or more (KITCHN). Nothing found ->
(None, None): the caller must not guess silently.
"""
import difflib, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "web", "rooms.json"), encoding="utf-8") as fh:
    VOCAB = json.load(fh)
TYPES = VOCAB["types"]
PRIORITY = {t: i for i, t in enumerate(VOCAB["priority"])}


def kinds(*names):
    """the types of these kinds: kinds('indoor') -> {'bedroom', ...}"""
    return {t for t, v in TYPES.items() if v["kind"] in names}


def words(text):
    """upper case, apostrophes dropped (MAID'S = MAIDS), split on spaces and punctuation; dots inside a word stay
    (W.C, B.R) and dots at its ends go; numbers and sizes (12'X14', 25,00) are not words"""
    text = str(text).upper().replace("’", "'").replace("'S ", "S ").replace("'", "")
    out = []
    for t in re.split(r"[\s/,:;()\[\]&+_\-–]+", text):
        t = t.strip(".")
        if t and not re.fullmatch(r"[\d.,X×\"]+|\d.*", t):
            out.append(t)
    return out


PHRASES = sorted(((tuple(words(p)), t) for t, ps in VOCAB["phrases"].items() for p in ps if words(p)),
                 key=lambda pt: (-len(pt[0]), PRIORITY.get(pt[1], 99)))
ABBREV = sorted(((a.strip("."), t) for t, ab in VOCAB["abbreviations"].items() for a in ab),
                key=lambda at: (-len(at[0]), PRIORITY.get(at[1], 99)))
SINGLE = sorted({(p[0], t) for p, t in PHRASES if len(p) == 1 and len(p[0]) >= 5})


def classify(label):
    """-> (type, how) with how 'exact', 'abbreviation' or 'fuzzy'; (None, None) when no type fits.
    A dotted word (ENT.LOBBY) is also read as its parts when it means nothing whole."""
    ws = words(label)
    if not ws:
        return None, None
    found = _classify(ws)
    parts = [p for w in ws for p in w.split(".") if p]
    if found[0] is None and parts != ws:
        found = _classify(parts)
    return found


def _classify(ws):
    for phrase, typ in PHRASES:          # longest phrase first, then priority
        n = len(phrase)
        if any(tuple(ws[i:i + n]) == phrase for i in range(len(ws) - n + 1)):
            return typ, "exact"
    for ab, typ in ABBREV:
        if len(ab) >= 3 and any(w.startswith(ab) for w in ws):
            return typ, "abbreviation"
    for p, typ in PHRASES:               # a longer word that starts with a whole one-word phrase (BEDROOMS, TOILET1)
        if len(p) == 1 and len(p[0]) >= 3 and any(w.startswith(p[0]) for w in ws):
            return typ, "abbreviation"
    best = None
    for w in ws:
        if len(w) < 5 or not w.isascii():
            continue
        for p, typ in SINGLE:
            r = difflib.SequenceMatcher(None, w, p).ratio()
            if r >= 0.85 and (best is None or r > best[0]):
                best = (r, typ)
    return (best[1], "fuzzy") if best else (None, None)


def names(label, typ):
    """does the label name this type anywhere (DRG./DIN. names living and dining)?"""
    ws = words(label)
    ws = ws + [p for w in ws for p in w.split(".") if p and "." in w]
    return any(t == typ and any(tuple(ws[i:i + len(p)]) == p for i in range(len(ws) - len(p) + 1)) for p, t in PHRASES)
