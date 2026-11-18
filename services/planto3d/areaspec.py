"""Areas no builder knows (a helipad, a koi pond, a putting green...), described by a spec in a fixed JSON form and
built by one tested builder. A spec is data only: no code from a model is ever run.

Spec (u, v are fractions 0-1 of the area's bounding box; sizes in metres):
{
  "type": "helipad",                      lower-case letters, digits, spaces, '-' and '_', at most 40 characters
  "name": "Helipad", "description": "...",               text, at most 60 / 300 characters
  "surface": one of SURFACES,
  "edge": "none" | "kerb" | "low_wall" | "fence" | "railing",
  "height": {"mode": "flat" | "raised" | "recessed", "value_m": 0 to 3},
  "walkable": true | false,
  "markings": [ {"kind": "line", "from": [u, v], "to": [u, v], "width_m": 0.02-1},
                {"kind": "circle", "centre": [u, v], "radius": 0.01-0.5 (of the shorter side), "width_m": ...},
                {"kind": "arc", "centre": [u, v], "radius": ..., "start_deg": 0-360, "end_deg": 0-360, "width_m": ...},
                {"kind": "text", "at": [u, v], "text": "H", "size_m": 0.2-10} ],   at most 40
  "objects": [ {"part": one of PARTS, "at": [u, v], "rot": 0-360} ]               at most 20
}
validate(spec) -> (clean spec, problems); a spec with problems is not used: the area is built as a labelled generic
zone (GENERIC). The library (areas/library.json) keeps every validated spec by type name, marked reviewed or not.
"""
import json, math, os, re, threading

HERE = os.path.dirname(os.path.abspath(__file__))
LIBRARY = os.path.join(HERE, "areas", "library.json")
SURFACES = {"concrete": "concrete", "asphalt": "asphalt", "grass": "turf", "turf": "turf", "sand": "sand",
            "gravel": "pebbles", "wood_deck": "deck", "stone": "terrace", "tile": "tile", "rubber": "court_green",
            "water": "water", "clay": "terracotta", "pavers": "pavers"}
EDGES = ("none", "kerb", "low_wall", "fence", "railing")
PARTS = ("plant", "outdoor_set", "car", "bench", "lamp", "post", "flag")
TYPE = re.compile(r"^[a-z0-9][a-z0-9 _-]{0,39}$")
GENERIC = dict(type="generic", name="Area", description="", surface="concrete", edge="kerb",
               height=dict(mode="flat", value_m=0.0), walkable=True, markings=[], objects=[])
_lock = threading.Lock()


def _num(v, lo, hi):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and lo <= v <= hi


def _uv(p):
    return isinstance(p, list) and len(p) == 2 and all(_num(x, 0, 1) for x in p)


def validate(spec):
    """-> (clean spec or None, [problems]). Unknown keys are dropped; anything out of range is a problem."""
    bad = []
    if not isinstance(spec, dict):
        return None, ["the spec is not an object"]
    out = {}
    t = spec.get("type")
    if not isinstance(t, str) or not TYPE.match(t.strip().lower()):
        bad.append("type must be a short name of letters, digits, spaces, - or _")
    else:
        out["type"] = t.strip().lower()
    for key, most in (("name", 60), ("description", 300)):
        v = spec.get(key, "")
        if not isinstance(v, str) or len(v) > most:
            bad.append(f"{key} must be text of at most {most} characters")
        else:
            out[key] = "".join(c for c in v if c.isprintable())
    if spec.get("surface") not in SURFACES:
        bad.append(f"surface must be one of {', '.join(SURFACES)}")
    out["surface"] = spec.get("surface")
    if spec.get("edge", "none") not in EDGES:
        bad.append(f"edge must be one of {', '.join(EDGES)}")
    out["edge"] = spec.get("edge", "none")
    h = spec.get("height", {"mode": "flat", "value_m": 0})
    if not isinstance(h, dict) or h.get("mode") not in ("flat", "raised", "recessed") or not _num(h.get("value_m", 0), 0, 3):
        bad.append("height must be {mode: flat | raised | recessed, value_m: 0 to 3}")
    else:
        out["height"] = {"mode": h["mode"], "value_m": float(h.get("value_m", 0))}
    if not isinstance(spec.get("walkable", True), bool):
        bad.append("walkable must be true or false")
    out["walkable"] = spec.get("walkable", True)
    marks = spec.get("markings", [])
    if not isinstance(marks, list) or len(marks) > 40:
        bad.append("markings must be a list of at most 40")
        marks = []
    out["markings"] = []
    for i, m in enumerate(marks):
        k = m.get("kind") if isinstance(m, dict) else None
        w = m.get("width_m", 0.1) if isinstance(m, dict) else None
        ok = (k == "line" and _uv(m.get("from")) and _uv(m.get("to")) and _num(w, 0.02, 1)) or \
             (k == "circle" and _uv(m.get("centre")) and _num(m.get("radius"), 0.01, 0.5) and _num(w, 0.02, 1)) or \
             (k == "arc" and _uv(m.get("centre")) and _num(m.get("radius"), 0.01, 0.5) and _num(m.get("start_deg"), 0, 360)
              and _num(m.get("end_deg"), 0, 360) and _num(w, 0.02, 1)) or \
             (k == "text" and _uv(m.get("at")) and isinstance(m.get("text"), str) and re.fullmatch(r"[A-Z0-9 ]{1,12}", m["text"] or "")
              and _num(m.get("size_m"), 0.2, 10))
        if not ok:
            bad.append(f"marking {i} is not a valid line, circle, arc or text")
        else:
            out["markings"].append({kk: m[kk] for kk in ("kind", "from", "to", "centre", "radius", "start_deg", "end_deg", "width_m", "at", "text", "size_m") if kk in m})
    objs = spec.get("objects", [])
    if not isinstance(objs, list) or len(objs) > 20:
        bad.append("objects must be a list of at most 20")
        objs = []
    out["objects"] = []
    for i, o in enumerate(objs):
        if not (isinstance(o, dict) and o.get("part") in PARTS and _uv(o.get("at")) and _num(o.get("rot", 0), 0, 360)):
            bad.append(f"object {i} must be {{part: one of {', '.join(PARTS)}, at: [u, v], rot: 0-360}}")
        else:
            out["objects"].append({"part": o["part"], "at": o["at"], "rot": float(o.get("rot", 0))})
    return (None, bad) if bad else (out, [])


def load():
    try:
        with open(LIBRARY, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save(spec, source="ai", reviewed=False):
    """add a validated spec to the library under its type name (a later spec of the same type replaces it)"""
    clean, bad = validate(spec)
    if bad:
        raise ValueError("; ".join(bad))
    with _lock:
        lib = load()
        lib[clean["type"]] = dict(spec=clean, source=source, reviewed=bool(reviewed))
        os.makedirs(os.path.dirname(LIBRARY), exist_ok=True)
        tmp = LIBRARY + ".part"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(lib, fh, indent=1, sort_keys=True)
        os.replace(tmp, LIBRARY)
    return clean


def spec_for(name):
    """the library's spec for an area type name, or None"""
    entry = load().get((name or "").strip().lower())
    return entry["spec"] if entry else None


def parts(spec, rect, ft_per_m=1 / 0.3048):
    """-> (boxes (x0, x1, y0, y1, z0, z1, material) in feet, objects [(part, x, y, rot)], walkable)"""
    spec = spec or GENERIC
    x0, x1, y0, y1 = rect
    W, D = x1 - x0, y1 - y0
    P = lambda u, v: (x0 + u * W, y0 + v * D)
    mat = SURFACES.get(spec["surface"], "concrete")
    h = spec["height"]["value_m"] * ft_per_m
    top = h if spec["height"]["mode"] == "raised" else -h if spec["height"]["mode"] == "recessed" else 0.0
    boxes = [(x0, x1, y0, y1, min(top, 0) - 0.1, top + 0.02, mat)]
    e = 0.4
    eh = {"kerb": 0.5, "low_wall": 2.5, "fence": 4.0, "railing": 3.5}.get(spec["edge"], 0)
    if eh:
        em = {"kerb": "concrete", "low_wall": "exterior", "fence": "fence", "railing": "steel"}[spec["edge"]]
        boxes += [(x0, x1, y0, y0 + e, top, top + eh, em), (x0, x1, y1 - e, y1, top, top + eh, em),
                  (x0, x0 + e, y0, y1, top, top + eh, em), (x1 - e, x1, y0, y1, top, top + eh, em)]
    z = top + 0.02
    paint = lambda a, b, w: _bar(a, b, w * ft_per_m, z, "line_paint")
    for m in spec["markings"]:
        if m["kind"] == "line":
            boxes += paint(P(*m["from"]), P(*m["to"]), m["width_m"])
        elif m["kind"] in ("circle", "arc"):
            c, r = P(*m["centre"]), m["radius"] * min(W, D)
            a0, a1 = (0, 360) if m["kind"] == "circle" else (m["start_deg"], m["end_deg"] if m["end_deg"] > m["start_deg"] else m["end_deg"] + 360)
            n = max(8, int((a1 - a0) / 10))
            pts = [(c[0] + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), c[1] + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
            for a, b in zip(pts, pts[1:]):
                boxes += paint(a, b, m["width_m"])
        else:       # text: a block letter per character from a 3x5 stroke font
            s = m["size_m"] * ft_per_m
            cx, cy = P(*m["at"])
            for i, ch in enumerate(m["text"]):
                ox = cx + (i - (len(m["text"]) - 1) / 2) * s * 0.8
                for (u0, v0), (u1, v1) in FONT.get(ch, []):
                    boxes += paint((ox + (u0 - 1) * s / 4, cy + (v0 - 2) * s / 4), (ox + (u1 - 1) * s / 4, cy + (v1 - 2) * s / 4), m["size_m"] / 8)
    objs = [(o["part"], *P(*o["at"]), o["rot"]) for o in spec["objects"]]
    return boxes, objs, spec["walkable"]


def _bar(a, b, w, z, mat):
    """a painted stroke from a to b, w wide, as axis-aligned boxes (diagonals as a staircase of short boxes)"""
    (ax, ay), (bx, by) = a, b
    L = math.hypot(bx - ax, by - ay)
    if L < 1e-6:
        return []
    if abs(ax - bx) < 1e-6 or abs(ay - by) < 1e-6:
        return [(min(ax, bx) - w / 2, max(ax, bx) + w / 2, min(ay, by) - w / 2, max(ay, by) + w / 2, z, z + 0.02, mat)]
    n = max(2, int(L / max(w, 0.2)))
    out = []
    for i in range(n):
        x, y = ax + (bx - ax) * (i + 0.5) / n, ay + (by - ay) * (i + 0.5) / n
        out.append((x - w / 2, x + w / 2, y - w / 2, y + w / 2, z, z + 0.02, mat))
    return out


# 3 x 5 block font (u 0-2, v 0-4), strokes between grid points: enough for markings such as H, 18, P, TEE
_S = {"top": ((0, 4), (2, 4)), "mid": ((0, 2), (2, 2)), "bot": ((0, 0), (2, 0)), "lt": ((0, 2), (0, 4)), "lb": ((0, 0), (0, 2)),
      "rt": ((2, 2), (2, 4)), "rb": ((2, 0), (2, 2)), "c": ((1, 0), (1, 4))}
_G = {"0": "top bot lt lb rt rb", "1": "c", "2": "top mid bot rt lb", "3": "top mid bot rt rb", "4": "mid lt rt rb", "5": "top mid bot lt rb",
      "6": "top mid bot lt lb rb", "7": "top rt rb", "8": "top mid bot lt lb rt rb", "9": "top mid bot lt rt rb", "A": "top mid lt lb rt rb",
      "B": "top mid bot lt lb rt rb", "C": "top bot lt lb", "D": "top bot lt lb rt rb", "E": "top mid bot lt lb", "F": "top mid lt lb",
      "G": "top bot lt lb rb", "H": "mid lt lb rt rb", "I": "top bot c", "J": "bot rt rb lb", "K": "mid lt lb rt rb", "L": "bot lt lb",
      "M": "top lt lb rt rb c", "N": "top lt lb rt rb", "O": "top bot lt lb rt rb", "P": "top mid lt lb rt", "Q": "top bot lt lb rt rb",
      "R": "top mid lt lb rt rb", "S": "top mid bot lt rb", "T": "top c", "U": "bot lt lb rt rb", "V": "bot lt lb rt rb", "W": "bot lt lb rt rb c",
      "X": "mid lt lb rt rb", "Y": "mid lt rt c", "Z": "top mid bot rt lb"}
FONT = {ch: [_S[s] for s in strokes.split()] for ch, strokes in _G.items()}
