"""Cameras for the High stills (PATCHES 57): one per room and four elevations, from a built house's meta.json.

    python3 tools/still_shots.py JOB/meta.json JOB/plan.json OUT/shots.json OUT/tour.json [--rooms N]

Writes shots for cinema.py --shots (feet, like its tours) and the small tour file cinema.py needs to start.
- A room: the camera stands at eye height in the corner nearest the room's door, a little in from the walls,
  moved further in while it would stand inside furniture, and looks level at the far corner (verticals stay
  straight). The lens is chosen so the far wall fills the picture: 16 mm in small rooms, up to 24 mm in large ones.
- Elevations: front, rear, left and right (front = the side facing the road when the plan says so, else the side
  of the main door, else south), named by compass too; level cameras at 1.6 m, 35 mm, far enough for the whole
  house, the lens shifted up to take in the roof.
Only rooms where a person stands are shot (no shafts, ducts, voids, water or stairs); the largest rooms first.
"""

import json
import math
import sys

M_TO_FT = 1 / 0.3048
SKIP = {"lift", "duct", "open", "stair", "pool", "water", "dock", "yard", "custom", "court"}
NAMES = {"bedroom": "Bedroom", "toilet": "Bathroom", "kitchen": "Kitchen", "living": "Living room", "dining": "Dining",
         "majlis": "Majlis", "prayer": "Prayer room", "puja": "Puja room", "garden": "Garden", "parking": "Parking"}


def largest(rects):
    return max(rects, key=lambda r: (r[1] - r[0]) * (r[3] - r[2]))


def inside(px, py, boxes, pad=0.25):
    return any(b[0] - pad <= px <= b[1] + pad and b[2] - pad <= py <= b[3] + pad for b in boxes)


def room_shot(room, floor, eye):
    x0, x1, y0, y1 = largest(room["rects"])
    w, d = x1 - x0, y1 - y0
    if w < 1.2 or d < 1.2:
        return None
    doors = [o["rect"] for o in floor.get("openings", []) if o.get("type") == "door"]
    corners = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]

    def door_dist(c):
        ds = [math.hypot(c[0] - (r[0] + r[1]) / 2, c[1] - (r[2] + r[3]) / 2) for r in doors
              if x0 - 0.5 <= (r[0] + r[1]) / 2 <= x1 + 0.5 and y0 - 0.5 <= (r[2] + r[3]) / 2 <= y1 + 0.5]
        return min(ds) if ds else 0.0

    cx, cy = min(corners, key=door_dist)
    fx, fy = x0 + x1 - cx, y0 + y1 - cy                   # the far corner
    boxes = floor.get("colliders", []) + [f for f in floor.get("furniture", []) if isinstance(f, list)]
    step = 0.04
    t = 0.12
    while t < 0.45:                                       # in from the corner along the diagonal, out of furniture
        px, py = cx + (fx - cx) * t, cy + (fy - cy) * t
        if not inside(px, py, [b for b in boxes if (b[1] - b[0]) < w * 0.9 and (b[3] - b[2]) < d * 0.9]):
            break
        t += step
    px, py = cx + (fx - cx) * t, cy + (fy - cy) * t
    dist = math.hypot(fx - px, fy - py)
    lens = 16 if dist < 4.5 else 20 if dist < 7 else 24
    z = floor["z"] + eye
    look_x, look_y = fx - (fx - px) * 0.15, fy - (fy - py) * 0.15
    return dict(p=[round(px * M_TO_FT, 2), round(py * M_TO_FT, 2), round(z * M_TO_FT, 2)],
                t=[round(look_x * M_TO_FT, 2), round(look_y * M_TO_FT, 2), round(z * M_TO_FT, 2)],
                lens=lens, level=True)


def front_side(meta, plan):
    road = (plan.get("road_side") or "").lower()
    if road in ("north", "south", "east", "west"):
        return road
    g = meta["floors"][0]
    x0, x1, y0, y1 = meta["bounds"]
    best = None
    for o in g.get("openings", []):                       # the widest door on the outline
        if o.get("type") != "door":
            continue
        r = o["rect"]
        mx, my = (r[0] + r[1]) / 2, (r[2] + r[3]) / 2
        side = min((("south", my - y0), ("north", y1 - my), ("west", mx - x0), ("east", x1 - mx)), key=lambda s: s[1])
        width = max(r[1] - r[0], r[3] - r[2])
        if side[1] < 0.6 and (best is None or width > best[0]):
            best = (width, side[0])
    return best[1] if best else "south"


def elevations(meta, plan):
    x0, x1, y0, y1 = meta["bounds"]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    top = meta.get("roof_z", 3.2) + 1.2
    front = front_side(meta, plan)
    north = float(meta.get("north_deg") or 0.0)
    order = ["south", "east", "north", "west"]           # plan sides, anticlockwise from the bottom of the page
    k = order.index(front)
    roles = {order[k]: "front", order[(k + 2) % 4]: "rear", order[(k + 1) % 4]: "right", order[(k + 3) % 4]: "left"}
    out = []
    for side, role in roles.items():
        span = (x1 - x0) if side in ("south", "north") else (y1 - y0)
        fov = 2 * math.atan(36 / 2 / 35)
        dist = max(span, top * 1.6) / 2 / math.tan(fov / 2) * 1.15 + 2
        dx, dy = {"south": (0, -1), "north": (0, 1), "west": (-1, 0), "east": (1, 0)}[side]
        hx, hy = (cx + dx * ((x1 - x0) / 2 + dist), cy) if dx else (cx, cy + dy * ((y1 - y0) / 2 + dist))
        bearing = (math.degrees(math.atan2(dx, dy)) - north) % 360
        compass = ["north", "east", "south", "west"][int(((bearing + 45) % 360) // 90)]
        out.append(dict(name=f"elevation_{role}", title=f"{role.title()} elevation ({compass})",
                        p=[round(hx * M_TO_FT, 2), round(hy * M_TO_FT, 2), round(1.6 * M_TO_FT, 2)],
                        t=[round(cx * M_TO_FT, 2), round(cy * M_TO_FT, 2), round(1.6 * M_TO_FT, 2)],
                        lens=35, level=True, shift_y=0.12, ev=0.0))
    return out


def main():
    meta, plan = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
    most = int(sys.argv[sys.argv.index("--rooms") + 1]) if "--rooms" in sys.argv else 40
    eye = float(meta.get("eye", 1.6)) - 0.05
    shots, seen = [], {}
    rooms = []
    for k, f in enumerate(meta["floors"]):
        for r in f["rooms"]:
            if r["type"] in SKIP or not r.get("rects"):
                continue
            x0, x1, y0, y1 = largest(r["rects"])
            rooms.append(((x1 - x0) * (y1 - y0), k, f, r))
    rooms.sort(key=lambda t: -t[0])
    for _, k, f, r in rooms[:most]:
        sh = room_shot(r, f, eye)
        if not sh:
            continue
        label = (r.get("label") or NAMES.get(r["type"], r["type"])).strip()
        base = "".join(ch if ch.isalnum() else "_" for ch in label.lower()).strip("_")[:28] or r["type"]
        seen[base] = seen.get(base, 0) + 1
        name = base if seen[base] == 1 else f"{base}_{seen[base]}"
        shots.append(dict(name=f"room_{name}", title=label.title(), floor=f["name"], **sh))
    shots += elevations(meta, plan)
    json.dump(shots, open(sys.argv[3], "w"), indent=1)
    x0, x1, y0, y1 = meta["bounds"]
    c = [(x0 + x1) / 2 * M_TO_FT, (y0 + y1) / 2 * M_TO_FT, 5.0]
    tour = dict(fps=30, plan=sys.argv[2], keys=[dict(p=c, t=[c[0] + 1, c[1], c[2]]), dict(p=[c[0] + 1, c[1], 5.0],
                                                                                            t=[c[0] + 2, c[1], 5.0])])
    json.dump(tour, open(sys.argv[4], "w"))
    print(f"{len(shots)} shots ({len(shots) - 4} rooms, 4 elevations)")


if __name__ == "__main__":
    main()
