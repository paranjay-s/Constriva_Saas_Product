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
