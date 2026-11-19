"""The plan verifier: pure code, no AI. plan -> issues {floor, kind, severity, item, message, at}.

severity: "critical" (the house would be built wrong: the review page keeps "Build" off until each is fixed or
dismissed), "warning" (probably wrong, worth a look), "info".

kind / what it finds:
  dangling_wall     a full-height wall end that touches no other wall (a gap in the outline, or a stray line)
  open_room         a room whose outline is not closed by walls on at least 3 of its 4 sides
  room_overlap      two rooms that share more than a sliver of floor
  untyped_room      a room without a type
  window_inside     a window with a room on both sides (windows belong in outer walls)
  door_no_way       a door with no walkable space 1.5 ft beyond it on one side
  stair_no_landing  a stair going up with no stair or open space above it on the next storey
  stair_direction   a stair whose UP mark is at its top end (the climb runs the wrong way)
  floor_overhang    an upper storey's room that lies outside the storey below (nothing holds it up)
  area_total        the rooms' total differs from a total stated on the drawing by more than 10 %
Standard library only (server.py runs it whenever plan.json is written, beside checks.py)."""

SLIVER = 4.0          # sq ft: overlaps smaller than this are drawing noise
TOUCH = 0.6           # ft: how close two walls must come to count as joined


def _area(q):
    return max(0.0, q[1] - q[0]) * max(0.0, q[3] - q[2])


def _inter(a, b):
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[2], b[2]))


def _near(w, x, y, m=TOUCH):
    return w[0] - m <= x <= w[1] + m and w[2] - m <= y <= w[3] + m


def _room_at(f, x, y):
    for k, r in enumerate(f.get("rooms", [])):
        if any(q[0] <= x <= q[1] and q[2] <= y <= q[3] for q in r.get("rects", [])):
            return k
    return None


def _ends(w):
    """the two end points of a wall box, on its centre line"""
    x0, x1, y0, y1 = w[:4]
    if x1 - x0 >= y1 - y0:
        cy = (y0 + y1) / 2
        return (x0, cy), (x1, cy)
    cx = (x0 + x1) / 2
    return (cx, y0), (cx, y1)


def _issue(out, fi, kind, severity, item, message, at):
    out.append(dict(floor=fi, kind=kind, severity=severity, item=item, message=message,
                    at=[round(at[0], 2), round(at[1], 2)]))


def verify(plan):
    out = []
    floors = plan.get("floors", [])
    for fi, f in enumerate(floors):
        name = f.get("name") or f"Floor {fi}"
        walls = [w for w in f.get("walls", []) if len(w) >= 4]
        full = [w for w in walls if not (len(w) > 4 and w[4])]
        rooms = f.get("rooms", [])
        # walls connect: every end of a full-height wall touches another wall or an opening (doors and windows sit
        # in gaps between wall pieces)
        ops = [o["rect"] for o in f.get("openings", []) if "rect" in o]
        for k, w in enumerate(full):
            for (x, y) in _ends(w):
                # (an open passage between rooms is a gap with walls on both sides: only a line with nothing near
                # its end is a stray)
                if not any(j != k and _near(v, x, y, 6.0) for j, v in enumerate(walls)) and not any(_near(r, x, y, 1.0) for r in ops):
                    _issue(out, fi, "dangling_wall", "info", ["wall", k],
                           f"{name}: a wall ends in mid-air (a gap in the outline, or a stray line)", (x, y))
        # rooms closed and typed; no overlaps
        for k, r in enumerate(rooms):
            rects = r.get("rects") or []
            if not r.get("type"):
                _issue(out, fi, "untyped_room", "critical", ["room", k], f'{name}: "{r.get("label") or "a room"}" has no type',
                       ((rects[0][0] + rects[0][1]) / 2, (rects[0][2] + rects[0][3]) / 2) if rects else (0, 0))
            if not rects or r.get("type") in ("garden", "yard", "parking", "pool", "water", "dock", "court", "custom", "open", "balcony"):
                continue
            q = max(rects, key=_area)
            sides = 0
            for (ax, ay, bx, by) in ((q[0], q[2], q[1], q[2]), (q[0], q[3], q[1], q[3]), (q[0], q[2], q[0], q[3]), (q[1], q[2], q[1], q[3])):
                pts = [(ax + (bx - ax) * t, ay + (by - ay) * t) for t in (0.25, 0.5, 0.75)]
                if sum(any(_near(w, x, y, 0.8) for w in walls + ops) for x, y in pts) >= 2:
                    sides += 1
            if sides < 2:          # one or two open sides are an open plan; fewer than two walls is no room
                _issue(out, fi, "open_room", "info", ["room", k],
                       f'{name}: "{r.get("label") or r.get("type")}" is not closed by walls ({sides} of 4 sides)',
                       ((q[0] + q[1]) / 2, (q[2] + q[3]) / 2))
        INSIDE_OK = {"stair", "lift", "open", "void", "duct"}       # drawn inside another room on purpose
        for i in range(len(rooms)):
            for j in range(i + 1, len(rooms)):
                if {rooms[i].get("type"), rooms[j].get("type")} & INSIDE_OK:
                    continue
                ov = sum(_inter(a, b) for a in rooms[i].get("rects", []) for b in rooms[j].get("rects", []))
                if ov > SLIVER:
                    a = rooms[i]["rects"][0]
                    _issue(out, fi, "room_overlap", "critical", ["room", i],
                           f'{name}: "{rooms[i].get("label") or rooms[i].get("type")}" and "{rooms[j].get("label") or rooms[j].get("type")}" '
                           f"overlap by {ov:.0f} sq ft", ((a[0] + a[1]) / 2, (a[2] + a[3]) / 2))
        # openings: windows in outer walls, doors with a way through
        for k, o in enumerate(f.get("openings", [])):
            x0, x1, y0, y1 = o["rect"]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            ends = [(cx, y0 - 1.5), (cx, y1 + 1.5)] if o.get("axis") == "x" else [(x0 - 1.5, cy), (x1 + 1.5, cy)]
            sides = [_room_at(f, *e) for e in ends]
            if o.get("type") == "window" and all(s is not None for s in sides):
                kinds = {rooms[s].get("type") for s in sides}
                if not kinds & {"garden", "yard", "balcony", "open", "pool", "water", "court", "parking", "dock"}:
                    _issue(out, fi, "window_inside", "warning", ["opening", k],
                           f"{name}: a window between two rooms (windows belong in outer walls)", (cx, cy))
            if o.get("type") == "door":
                # a side is shut when a wall stands 1.5 ft out across the whole width of the door
                def shut(e):
                    pts = [(x0 + (x1 - x0) * t, e[1]) for t in (0.2, 0.5, 0.8)] if o.get("axis") == "x" else \
                          [(e[0], y0 + (y1 - y0) * t) for t in (0.2, 0.5, 0.8)]
                    return all(any(_near(w, px, py, 0.1) for w in full) for px, py in pts)
                if any(shut(e) for e in ends):
                    _issue(out, fi, "door_no_way", "critical", ["opening", k],
                           f"{name}: a door opens straight onto a wall", (cx, cy))
        # stairs: the UP mark at the bottom end; something above the stair on the next storey
        above = floors[fi + 1] if fi + 1 < len(floors) else None
        for k, s in enumerate(f.get("stairs", [])):
            r = s["rect"]
            words = {w[0].upper(): (w[1], w[2]) for w in s.get("words") or [] if isinstance(w, (list, tuple)) and len(w) >= 3}
            if "UP" in words and "DN" in words:
                ax = 0 if s.get("axis") == "x" else 1
                up, dn = words["UP"][ax], words["DN"][ax]
                lo, hi = (r[0], r[1]) if ax == 0 else (r[2], r[3])
                # UP is written where the climb starts: if the drawing has it nearer the far end than DN, say so
                if abs(up - lo) > abs(dn - lo) and abs(up - hi) < abs(dn - hi) and s.get("up") is True and s.get("dir", 1) == 1:
                    _issue(out, fi, "stair_direction", "info", ["stair", k],
                           f"{name}: the stair's UP mark is at its far end: check which way it climbs", ((r[0] + r[1]) / 2, (r[2] + r[3]) / 2))
            if above is not None and s.get("up", True):
                hit = any(_inter(r, t["rect"]) > 0 for t in above.get("stairs", [])) or \
                      any(_inter(r, q) > 0.3 * _area(r) for z in above.get("rooms", []) if z.get("type") in ("stair", "open", "void")
                          for q in z.get("rects", []))
                if not hit:
                    _issue(out, fi, "stair_no_landing", "warning", ["stair", k],
                           f"{name}: the stair has no stair or opening above it on {above.get('name') or 'the next storey'}",
                           ((r[0] + r[1]) / 2, (r[2] + r[3]) / 2))
        # storeys stack: an upper room must stand over the storey below (its walls' extent)
        if fi > 0:
            below = floors[fi - 1]
            bw = [w for w in below.get("walls", []) if len(w) >= 4]
            if bw:
                bx0, bx1 = min(w[0] for w in bw) - 1, max(w[1] for w in bw) + 1
                by0, by1 = min(w[2] for w in bw) - 1, max(w[3] for w in bw) + 1
                for k, r in enumerate(rooms):
                    if r.get("type") in ("balcony", "open", "garden", "yard"):
                        continue
                    for q in r.get("rects", []):
                        inside = _inter(q, (bx0, bx1, by0, by1))
                        if _area(q) > SLIVER and inside < 0.5 * _area(q):
                            _issue(out, fi, "floor_overhang", "warning", ["room", k],
                                   f'{name}: "{r.get("label") or r.get("type")}" lies mostly outside the storey below',
                                   ((q[0] + q[1]) / 2, (q[2] + q[3]) / 2))
                            break
    # the rooms' total against a total written on the drawing (plan["stated_area_sqft"], when a reader found one)
    stated = plan.get("stated_area_sqft")
    if isinstance(stated, (int, float)) and stated > 0:
        total = sum(_area(q) for f in floors for r in f.get("rooms", []) if r.get("type") not in ("garden", "yard", "parking", "pool", "water", "dock", "court")
                    for q in r.get("rects", []))
        if abs(total - stated) / stated > 0.10:
            _issue(out, 0, "area_total", "warning", ["plan", 0],
                   f"the rooms add up to {total:.0f} sq ft but the drawing states {stated:.0f} sq ft", (0, 0))
    order = {"critical": 0, "warning": 1, "info": 2}
    out.sort(key=lambda i: (order[i["severity"]], i["floor"]))
    return out
