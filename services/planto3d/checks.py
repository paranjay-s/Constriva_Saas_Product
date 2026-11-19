"""What a person should check on the review page before building: plan -> list of {floor, kind, item, message}.

kind / what it flags:
  unknown_label   a room whose label no rule knows (built as an unfurnished multipurpose room)
  multi_label     a room whose label names two or more functions (KITCHEN / DINING): one space, several uses
  door_blocked    a door with no room on one of its sides (it leads nowhere, or a wall was misread as a door)
  area_mismatch   a room whose area differs by more than 10 % from the size written in its label
  unlabelled      an unlabelled indoor space larger than 150 sq ft (14 m2)
Standard library only; called whenever plan.json is written (server.py)."""
import rooms

AREA_TOLERANCE = 0.10
BIG_UNLABELLED = 150.0           # sq ft


def _area(r):
    return sum((q[1] - q[0]) * (q[3] - q[2]) for q in r.get("rects", []))


def _room_at(f, x, y):
    for k, r in enumerate(f.get("rooms", [])):
        if any(q[0] <= x <= q[1] and q[2] <= y <= q[3] for q in r.get("rects", [])):
            return k
    return None


def plan_checks(plan):
    out = []
    wall = (plan.get("wall_pt") or 0) / (plan.get("scale_pt_per_ft") or 1) if plan.get("wall_pt") else 0.5
    for fi, f in enumerate(plan.get("floors", [])):
        name = f.get("name") or f"Floor {fi}"
        for k, r in enumerate(f.get("rooms", [])):
            label = (r.get("label") or "").strip()
            say = lambda kind, msg: out.append(dict(floor=fi, kind=kind, item=["room", k], message=f"{name}: {msg}"))
            if r.get("type") == "multipurpose" or (label and rooms.classify(label)[0] is None and r.get("type") in ("room", None)):
                say("unknown_label", f'"{label or "unnamed"}" is not a known room type: choose its type')
            named = rooms.functions(label) if label else []
            if len(named) >= 2:
                say("multi_label", f'"{label}" names {" and ".join(named)}: one space with several uses')
            dims = r.get("dims")
            if dims and _area(r) > 0:
                # a label gives the clear size (between wall faces) or, on generated plans, the size between wall
                # centre lines: the room is flagged only when neither reading is within 10 %
                want = dims[0] * dims[1]
                w = max(sum(q[1] - q[0] for q in r["rects"][:1]), 1e-6)
                d = _area(r) / w
                centre = (w + wall) * (d + wall)
                if want > 0 and min(abs(_area(r) - want), abs(centre - want)) / want > AREA_TOLERANCE:
                    say("area_mismatch", f'"{label}" is {_area(r):.0f} sq ft but its label says {want:.0f} sq ft')
            if not label and r.get("type") in rooms.kinds("indoor") and _area(r) > BIG_UNLABELLED:
                say("unlabelled", f"an unlabelled space of {_area(r):.0f} sq ft: what is it?")
        for k, o in enumerate(f.get("openings", [])):
            if o.get("type") != "door":
                continue
            x0, x1, y0, y1 = o["rect"]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            ends = [(cx, y0 - 1.5), (cx, y1 + 1.5)] if o.get("axis") == "x" else [(x0 - 1.5, cy), (x1 + 1.5, cy)]
            if any(_room_at(f, *e) is None for e in ends) and not all(_room_at(f, *e) is None for e in ends) and fi > 0:
                out.append(dict(floor=fi, kind="door_blocked", item=["opening", k],
                                message=f"{name}: a door leads to no room on one side"))
            elif all(_room_at(f, *e) is None for e in ends):
                out.append(dict(floor=fi, kind="door_blocked", item=["opening", k],
                                message=f"{name}: a door has no room on either side"))
    return out


# ---- source and confidence of every room and opening (shown on the review page; the checks above cap them)
READER_FACTOR = {"detector": 1.0, "ai": 0.85}
LABEL_CONF = {"exact": 0.95, "abbreviation": 0.8, "fuzzy": 0.6}
CAPS = {"unknown_label": 0.3, "door_blocked": 0.3, "area_mismatch": 0.5, "multi_label": 0.7, "unlabelled": 0.5}


def annotate(plan, reader="user"):
    """set src (who made it: detector, ai or user) and conf (0-1, how likely it is right) on every room and opening.
    An element that has a src keeps it (a person's save keeps what the reader made); one without is the `reader`'s.
    Walls are lists: their source and confidence are per floor (wall_src, wall_conf). Sets plan["confidence"] too."""
    caps = {}
    for c in plan.get("checks") or plan_checks(plan):
        key = (c["floor"], *c["item"])
        caps[key] = min(caps.get(key, 1.0), CAPS.get(c["kind"], 1.0))
    seen = {"rooms": [], "openings": []}
    for fi, f in enumerate(plan.get("floors", [])):
        f.setdefault("wall_src", reader)
        f["wall_conf"] = 1.0 if f["wall_src"] == "user" else round(0.8 * READER_FACTOR.get(f["wall_src"], 1.0), 2)
        for k, r in enumerate(f.get("rooms", [])):
            src = r.setdefault("src", reader)
            if src == "user":
                conf = 1.0
            elif src == "ai" and isinstance(r.get("confidence"), (int, float)):
                conf = float(r["confidence"])         # typed by the AI classifier (backend plan3d/areas.py)
            else:
                label = (r.get("label") or "").strip()
                how = rooms.classify(label)[1] if label else None
                conf = LABEL_CONF.get(how, 0.5 if not label else 0.3) * READER_FACTOR.get(src, 1.0)
            r["conf"] = round(min(conf, caps.get((fi, "room", k), 1.0)), 2)
            seen["rooms"].append(r["conf"])
        for k, o in enumerate(f.get("openings", [])):
            src = o.setdefault("src", reader)
            if src == "user":
                conf = 1.0
            else:
                conf = (0.9 if o.get("hinge") else 0.65) if o.get("type") == "door" else 0.8
                conf *= READER_FACTOR.get(src, 1.0)
            o["conf"] = round(min(conf, caps.get((fi, "opening", k), 1.0)), 2)
            seen["openings"].append(o["conf"])
    plan["confidence"] = {k: round(sum(v) / len(v), 2) if v else None for k, v in seen.items()}
    if not plan.get("kind"):
        plan["kind"] = building_kind(plan)
    return plan


NARROW_FT = 40.0       # a house no wider than this (its shorter side) on two or more storeys is a townhouse


def building_kind(plan):
    """apartment, townhouse or villa, from what any plan shows: one storey with no grounds of its own (no garden, court,
    pool, parking: a balcony does not count) is an apartment; otherwise a house whose footprint's shorter side is at most
    NARROW_FT feet is a townhouse, a wider one a villa. A guess from geometry, so it is shown with the plan, not imposed."""
    fl = plan.get("floors") or []
    if not fl:
        return None
    grounds = {t for t in rooms.kinds("outdoor", "water")} - {"balcony"}
    has_grounds = any(r.get("type") in grounds for f in fl for r in f.get("rooms", []))
    if len(fl) == 1 and not has_grounds:
        return "apartment"
    ws = fl[0].get("walls") or []
    if not ws:
        return None
    w = min(max(x[1] for x in ws) - min(x[0] for x in ws), max(x[3] for x in ws) - min(x[2] for x in ws))
    return "townhouse" if w <= NARROW_FT else "villa"


SEVERITY = {"unknown_label": "warning", "multi_label": "info", "door_blocked": "warning", "area_mismatch": "warning",
            "unlabelled": "info"}


def all_checks(plan):
    """the review page's whole checklist: these checks plus the verifier's (verify.py), each with a severity,
    most severe first"""
    import verify
    out = [dict(c, severity=c.get("severity") or SEVERITY.get(c["kind"], "info")) for c in plan_checks(plan)]
    out += verify.verify(plan)
    order = {"critical": 0, "warning": 1, "info": 2}
    return sorted(out, key=lambda c: (order.get(c["severity"], 2), c["floor"]))
