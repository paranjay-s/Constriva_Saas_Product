"""plan JSON -> furnished 3D house -> baked lighting -> web model (house.glb + lightmaps + meta.json).
Run: blender -b --factory-startup -P planto3d/blender/gen.py -- plan.json OUTDIR [--quality draft|high] [--no-bake]
Progress lines: 'PROGRESS <0-100> <message>' on stdout (read by the server)."""
import json, math, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..")]
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PLAN, JOB = os.path.abspath(argv[0]), os.path.abspath(argv[1])
QUALITY = argv[argv.index("--quality") + 1] if "--quality" in argv else "high"
# the person's own furniture models (server.py furniture sets): assets/custom/<set>/; none = the shared ones
FURNITURE_SET = argv[argv.index("--furniture-set") + 1] if "--furniture-set" in argv else ""
if not re.match(r"^[a-f0-9]{16}$", FURNITURE_SET or "0" * 16):
    FURNITURE_SET = ""
BAKE = "--no-bake" not in argv
os.makedirs(JOB, exist_ok=True)

import bpy  # noqa: E402
from lib import *  # noqa: E402,F401
import lib  # noqa: E402
import furnish  # noqa: E402
from catalog import CATALOG  # noqa: E402
from mathutils import Vector  # noqa: E402


def progress(p, msg):
    print(f"PROGRESS {int(p)} {msg}", flush=True)


plan = json.load(open(PLAN))
H, SLAB = plan.get("floor_height", 10.0), plan.get("slab", 0.5)
FFH = H + SLAB
lib.WALL_H = H
floors = plan["floors"]
NF = len(floors)
# A plan whose lowest storey is titled FIRST, SECOND... FLOOR is an upper storey drawn on its own: it is built at its
# own height, on a plain block that stands for the storeys that are not drawn, so its terraces are not the ground.
UPPER_TITLES = ["FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH"]
_title = (floors[0].get("title") or floors[0].get("name") or "").upper() if floors else ""
BASE = next((i + 1 for i, t in enumerate(UPPER_TITLES) if t in _title.split()), 0)
progress(2, "building walls")

mat("tile", tex="large_floor_tiles_02", tile=1.5)
mat("pavers", tex="herringbone_pavement", tile=1.6)
mat("asphalt", tex="asphalt_02", tile=4.0)
mat("footpath", tex="square_concrete_pavers", tile=1.5)
mat("pebbles", tex="dry_river_pebbles", tile=0.8)
mat("terrace", tex="concrete_tiles", tile=1.5)
mat("turf", tex="leafy_grass", tile=1.0, tint=(0.5, 0.75, 0.35))
mat("exterior", (0.93, 0.91, 0.87), 0.9, tex="white_plaster_02", tile=2.5, albedo=False)
mat("plinth_stone", (0.56, 0.53, 0.49), 0.8, tex="granite_tile", tile=1.5)      # the stone base of outer walls
mat("cushion", rough=0.95, tex="caban", tile=0.5, tint=(0.55, 0.45, 0.35))

# The house's palette, seeded by the plan's geometry: the same plan always looks the same, different plans differ.
# Every scheme keeps the handover's warm villa look (warm whites, stone, oak or walnut); PLAN3D_STYLE picks one.
SCHEMES = {
    "warm_oak":   dict(wall=(0.86, 0.80, 0.70), exterior=(0.93, 0.91, 0.87), wood=None, accent=(0.62, 0.42, 0.28),
                       cushion=(0.55, 0.45, 0.35)),
    "limestone":  dict(wall=(0.90, 0.86, 0.79), exterior=(0.88, 0.82, 0.72), wood=(0.80, 0.66, 0.50),
                       accent=(0.70, 0.55, 0.40), cushion=(0.72, 0.66, 0.56)),
    "walnut":     dict(wall=(0.84, 0.80, 0.74), exterior=(0.90, 0.88, 0.84), wood=(0.62, 0.45, 0.32),
                       accent=(0.45, 0.30, 0.20), cushion=(0.40, 0.42, 0.36)),
    "sand":       dict(wall=(0.88, 0.82, 0.72), exterior=(0.86, 0.76, 0.60), wood=(0.85, 0.70, 0.52),
                       accent=(0.66, 0.48, 0.32), cushion=(0.62, 0.50, 0.40)),
}


def plan_scheme(plan):
    """a scheme name from a hash of the plan's walls and rooms (not its labels or job id)"""
    import hashlib
    geo = [[[round(v, 1) for v in w[:4]] for w in f.get("walls", [])] +
           [[round(v, 1) for q in r.get("rects", []) for v in q] for r in f.get("rooms", [])] for f in plan.get("floors", [])]
    h = int(hashlib.sha256(json.dumps(geo).encode()).hexdigest(), 16)
    names = sorted(SCHEMES)
    return os.environ.get("PLAN3D_STYLE") if os.environ.get("PLAN3D_STYLE") in SCHEMES else names[h % len(names)]


SCHEME = plan_scheme(plan)
_sc = SCHEMES[SCHEME]
mat("wall", _sc["wall"], 0.9, tex="white_plaster_02", tile=1.5, albedo=False)
mat("exterior", _sc["exterior"], 0.9, tex="white_plaster_02", tile=2.5, albedo=False)
mat("wall_accent", rough=0.5, tex="american_walnut_veneer", tile=1.2, tint=_sc["accent"])
mat("cushion", rough=0.95, tex="caban", tile=0.5, tint=_sc["cushion"])
if _sc["wood"]:
    mat("wood", tex="laminate_floor_02", tile=2.0, tint=_sc["wood"])

import rooms  # noqa: E402

# room types (web/rooms.json): floor material, which rooms get a ceiling, lamp and furniture, which are open to the sky
FLOOR_MAT = {t: v["floor"] for t, v in rooms.TYPES.items()}
OPEN_SKY = rooms.kinds("outdoor", "water", "void")       # no slab above these
VOID = rooms.kinds("void")    # OPEN, SHAFT, CUTOUT, VOID: open down to the storey below, on any storey
INDOOR = rooms.kinds("indoor")
WATER, SHAFT = rooms.kinds("water"), rooms.kinds("shaft")
mat("pooltile", (0.62, 0.82, 0.9), 0.3, tex="large_floor_tiles_02", tile=0.6, tint=(0.62, 0.84, 0.95), grey=True)
mat("water", (0.05, 0.38, 0.52), 0.03, alpha=0.55)
mat("deck", tex="laminate_floor_02", tile=1.2, tint=(0.62, 0.45, 0.3))
mat("coping", (0.88, 0.85, 0.8), 0.6)


mat("court_green", (0.16, 0.42, 0.3), 0.75)
mat("court_blue", (0.12, 0.3, 0.55), 0.75)
mat("court_wood", tex="laminate_floor_02", tile=2.0, tint=(0.85, 0.6, 0.38))
mat("line_paint", (0.95, 0.95, 0.93), 0.6)
mat("fence", (0.15, 0.17, 0.16), 0.5, alpha=0.35)
mat("lamp_glow", (1.0, 0.85, 0.6), 0.5, emit=6.0)
mat("sand", (0.86, 0.78, 0.6), 0.95)
import areaspec  # noqa: E402

# official court sizes (feet, length x width) and markings in fractions of them: a drawn court is marked to its own
# size, as the proportions of the real one
COURTS = {"tennis": (78.0, 36.0), "padel": (65.6, 32.8), "basketball": (91.9, 49.2)}


def sport(label):
    t = (label or "").upper()
    return next((k for k in COURTS if k.upper() in t), "tennis")


def court_parts(zn):
    """a court: playing surface, the sport's markings scaled to the drawn rectangle, net or hoops, a fence"""
    out = []
    x0, x1, y0, y1 = max(zn["rects"], key=lambda r: (r[1] - r[0]) * (r[3] - r[2]))
    sp = sport(zn.get("label"))
    long_x = x1 - x0 >= y1 - y0
    L, Wd = (x1 - x0, y1 - y0) if long_x else (y1 - y0, x1 - x0)
    surf = {"tennis": "court_green", "padel": "court_blue", "basketball": "court_wood"}[sp]
    out.append((x0, x1, y0, y1, -0.02, 0.02, surf))
    m = 0.06 * min(L, Wd)                    # run-off margin inside the drawn area
    def line(a0, a1, b0, b1):                 # along-length a, across b, as fractions of the playing area
        la, lb = L - 2 * m, Wd - 2 * m
        A0, A1, B0, B1 = m + a0 * la, m + a1 * la, m + b0 * lb, m + b1 * lb
        r = (x0 + A0, x0 + A1, y0 + B0, y0 + B1) if long_x else (x0 + B0, x0 + B1, y0 + A0, y0 + A1)
        out.append((*r, 0.02, 0.04, "line_paint"))
    t = 0.008
    for a in (0, 1):                          # base lines and side lines
        line(a - t / 2 if a else 0, a + t / 2 if not a else a, 0, 1)
        line(0, 1, a - t / 2 if a else 0, a + t / 2 if not a else a)
    if sp == "tennis":
        for b in (0.125, 0.875):              # singles lines
            line(0, 1, b - t / 2, b + t / 2)
        for a in (0.27, 0.73):                # service lines
            line(a - t / 2, a + t / 2, 0.125, 0.875)
        line(0.27, 0.73, 0.5 - t / 2, 0.5 + t / 2)       # centre service line
    elif sp == "padel":
        for a in (0.15, 0.85):
            line(a - t / 2, a + t / 2, 0, 1)
        line(0.15, 0.85, 0.5 - t / 2, 0.5 + t / 2)
    else:
        line(0.5 - t / 2, 0.5 + t / 2, 0, 1)                 # half-court line
        for a0, a1 in ((0, 0.19), (0.81, 1)):                 # keys
            line(a0, a1, 0.34, 0.34 + t)
            line(a0, a1, 0.66 - t, 0.66)
    mid = (x0 + x1) / 2 if long_x else (y0 + y1) / 2
    if sp in ("tennis", "padel"):             # the net across the middle
        net = (mid - 0.1, mid + 0.1, y0 + m * 0.5, y1 - m * 0.5) if long_x else (x0 + m * 0.5, x1 - m * 0.5, mid - 0.1, mid + 0.1)
        out.append((*net, 0.0, 3.0, "fence"))
    else:                                     # two hoops on posts at the ends
        c = (y0 + y1) / 2 if long_x else (x0 + x1) / 2
        for e in ((x0 + m * 0.6, x1 - m * 0.6) if long_x else (y0 + m * 0.6, y1 - m * 0.6)):
            post = (e - 0.25, e + 0.25, c - 0.25, c + 0.25) if long_x else (c - 0.25, c + 0.25, e - 0.25, e + 0.25)
            board = (e - 0.1, e + 0.1, c - 3, c + 3) if long_x else (c - 3, c + 3, e - 0.1, e + 0.1)
            out += [(*post, 0, 10.0, "steel"), (*board, 8.5, 12.0, "line_paint")]
    f = 0.15                                  # chain-link fence round the court (posts and a see-through panel)
    out += [(x0, x1, y0, y0 + f, 0, 10, "fence"), (x0, x1, y1 - f, y1, 0, 10, "fence"),
            (x0, x0 + f, y0, y1, 0, 10, "fence"), (x1 - f, x1, y0, y1, 0, 10, "fence")]
    return out


def parking_parts(zn):
    """painted bays (9 ft wide) across the paving, and for a CARPORT a canopy on four posts"""
    out = []
    for x0, x1, y0, y1 in zn["rects"]:
        along_x = x1 - x0 >= y1 - y0
        n = int((x1 - x0 if along_x else y1 - y0) // 9)
        for i in range(1, n):
            a = (x0 if along_x else y0) + i * 9
            out.append((a - 0.1, a + 0.1, y0 + 1, y1 - 1, 0.0, 0.03, "line_paint") if along_x else (x0 + 1, x1 - 1, a - 0.1, a + 0.1, 0.0, 0.03, "line_paint"))
        if "CARPORT" in (zn.get("label") or "").upper().replace(" ", "") or "CAR PORCH" in (zn.get("label") or "").upper():
            for px, py in ((x0 + 0.5, y0 + 0.5), (x1 - 0.5, y0 + 0.5), (x0 + 0.5, y1 - 0.5), (x1 - 0.5, y1 - 0.5)):
                out.append((px - 0.25, px + 0.25, py - 0.25, py + 0.25, 0, 8.5, "steel"))
            out.append((x0, x1, y0, y1, 8.5, 8.9, "steel"))
    return out


POOL_MIN_FT = 3.0  # a pool rectangle narrower than this is paved round the water, not filled (PATCHES 53)


SERVICE_LIFT = ("SERVICE", "GOODS", "FREIGHT", "CARGO", "DUMB")     # label words of a service lift (PATCHES 56)


def lift_cabin(zn, rect, door_side):
    """a lift car standing in the shaft: floor, ceiling with a light panel and three walls (open on the landing side).
    A passenger lift: wood panels, a mirror on the back wall, a handrail and a button panel. A service lift (its
    label says SERVICE, GOODS ...): brushed steel walls with bumper rails at trolley height, a chequer-plate floor."""
    x0, x1, y0, y1 = rect
    g = 0.2                                   # running clearance to the shaft
    a0, a1, b0, b1 = x0 + g, x1 - g, y0 + g, y1 - g
    service = any(w in (zn.get("label") or "").upper() for w in SERVICE_LIFT)
    wall_m, floor_m = ("steel_brushed", "cast_iron") if service else ("teak", "marble")
    t, top = 0.12, 7.6
    out = [(a0, a1, b0, b1, 0.0, 0.15, floor_m), (a0, a1, b0, b1, top, top + 0.15, "steel"),
           ((a0 + a1) / 2 - 0.9, (a0 + a1) / 2 + 0.9, (b0 + b1) / 2 - 0.9, (b0 + b1) / 2 + 0.9, top - 0.03, top,
            "light")]
    walls = {"S": (a0, a1, b0, b0 + t), "N": (a0, a1, b1 - t, b1), "W": (a0, a0 + t, b0, b1), "E": (a1 - t, a1, b0, b1)}
    back = {"S": "N", "N": "S", "W": "E", "E": "W"}[door_side]
    for sd, (p0, p1, q0, q1) in walls.items():
        if sd == door_side:
            continue
        out.append((p0, p1, q0, q1, 0.15, top, wall_m))
        inward = {"S": 1, "N": -1, "W": 1, "E": -1}[sd]
        if sd in "SN":
            f0, f1 = sorted(((q1 if inward > 0 else q0), (q1 if inward > 0 else q0) + inward * 0.12))
            span = (p0 + 0.3, p1 - 0.3)
        else:
            f0, f1 = sorted(((p1 if inward > 0 else p0), (p1 if inward > 0 else p0) + inward * 0.12))
            span = (q0 + 0.3, q1 - 0.3)

        def rail(z0, z1, m, f0=f0, f1=f1, span=span, sd=sd):
            return (span[0], span[1], f0, f1, z0, z1, m) if sd in "SN" else (f0, f1, span[0], span[1], z0, z1, m)

        if service:
            out += [rail(1.0, 1.4, "black"), rail(2.6, 3.0, "black")]
        else:
            out.append(rail(2.95, 3.05, "chrome"))
            if sd == back:
                c0, c1 = span
                m0, m1 = (c0 + c1) / 2 - 1.0, (c0 + c1) / 2 + 1.0
                out.append((m0, m1, f0, f1, 3.4, 6.8, "mirror") if sd in "SN" else (f0, f1, m0, m1, 3.4, 6.8, "mirror"))
    # the button panel beside the door, on the wall to its right
    side_wall = {"S": "E", "N": "W", "W": "S", "E": "N"}[door_side]
    p0, p1, q0, q1 = walls[side_wall]
    if side_wall in "SN":
        y_ = q1 + 0.02 if side_wall == "S" else q0 - 0.06
        x_ = a1 - 0.8 if door_side == "E" else a0 + 0.5
        out.append((x_, x_ + 0.35, *sorted((y_, y_ + 0.04)), 3.6, 5.0, "black_glass"))
    else:
        x_ = p1 + 0.02 if side_wall == "W" else p0 - 0.06
        y_ = b1 - 0.8 if door_side == "N" else b0 + 0.5
        out.append((*sorted((x_, x_ + 0.04)), y_, y_ + 0.35, 3.6, 5.0, "black_glass"))
    return out


def pool_ladder(b, along_x, deep):
    """a chrome ladder at the end away from the steps: two rails over the coping and three treads"""
    out = []
    if along_x:                                # steps at the low-x end; the ladder on the high-x wall
        x = b[1] - 0.15
        cy = (b[2] + b[3]) / 2
        for y in (cy - 0.8, cy + 0.8):
            out += [(x - 0.06, x + 0.06, y - 0.06, y + 0.06, -min(deep, 3.5), 2.6, "chrome"),
                    (x - 0.6, x + 0.06, y - 0.06, y + 0.06, 2.5, 2.62, "chrome")]
        out += [(x - 0.35, x, cy - 0.8, cy + 0.8, z - 0.05, z, "steel_brushed") for z in (-0.9, -1.9, -2.9) if z > -deep]
    else:
        y = b[3] - 0.15
        cx = (b[0] + b[1]) / 2
        for x in (cx - 0.8, cx + 0.8):
            out += [(x - 0.06, x + 0.06, y - 0.06, y + 0.06, -min(deep, 3.5), 2.6, "chrome"),
                    (x - 0.06, x + 0.06, y - 0.6, y + 0.06, 2.5, 2.62, "chrome")]
        out += [(cx - 0.8, cx + 0.8, y - 0.35, y, z - 0.05, z, "steel_brushed") for z in (-0.9, -1.9, -2.9) if z > -deep]
    return out


def water_parts(zn, k):
    """a pool: a basin sunk 4.5 ft (raised 1.5 ft on an upper storey) lined with tile, coping round it, three steps
    at one short end and a water plane; a water body or fountain: a shallow basin; a dock: water with a walkable plank
    deck along its two long sides, on posts. -> (boxes, walkable rects); the rest of the zone is closed to the walker"""
    out, walk = [], []
    pool_zone = zn["type"] == "pool"
    water_rect = zn.get("water") if pool_zone else None
    for r in zn["rects"]:
        x0, x1, y0, y1 = r
        narrow = min(x1 - x0, y1 - y0) < (POOL_MIN_FT if pool_zone else 1.2)
        if water_rect or narrow:
            # the model's water outline (or nothing, for a sliver): the rest is paved deck at ground level.
            # Filling a sliver gave a "line of water" with inverted coping boxes.
            if not narrow or min(x1 - x0, y1 - y0) > 0.05:
                out.append((x0, x1, y0, y1, -0.1, 0.12 if pool_zone else 0.05, "coping"))
                walk.append((x0, x1, y0, y1))
            continue
        if zn["type"] == "dock":
            long_x = x1 - x0 >= y1 - y0
            d = min(4.0, (min(x1 - x0, y1 - y0)) / 3)
            out.append((x0, x1, y0, y1, -3.0, -1.2, "water"))
            decks = [(x0, x1, y0, y0 + d), (x0, x1, y1 - d, y1)] if long_x else [(x0, x0 + d, y0, y1), (x1 - d, x1, y0, y1)]
            for q in decks:
                out.append((*q, -0.25, 0.0, "deck"))
                walk.append(q)
                n = max(2, int(max(q[1] - q[0], q[3] - q[2]) / 6) + 1)
                for i in range(n):          # posts down into the water, a cleat and an edge light at each
                    t = i / (n - 1)
                    px, py = (q[0] + (q[1] - q[0]) * t, (q[2] + q[3]) / 2) if long_x else ((q[0] + q[1]) / 2, q[2] + (q[3] - q[2]) * t)
                    out.append((px - 0.3, px + 0.3, py - 0.3, py + 0.3, -3.5, 0.2, "deck"))
                    ex, ey = (px, q[3] - 0.3 if q[2] < (y0 + y1) / 2 else q[2] + 0.3) if long_x else (q[1] - 0.3 if q[0] < (x0 + x1) / 2 else q[0] + 0.3, py)
                    out.append((ex - 0.4, ex + 0.4, ey - 0.12, ey + 0.12, 0.0, 0.35, "steel"))
                    out.append((ex - 0.15, ex + 0.15, ey - 0.15, ey + 0.15, 0.0, 0.12, "lamp_glow"))
            continue
        pool = zn["type"] == "pool"
        deep = (4.5 if k == 0 else -1.5) if pool else (1.0 if k == 0 else -0.8)
        c = 0.8 if pool else 0.5                      # coping width
        out += [(x0, x1, y0, y0 + c, -0.1, 0.15, "coping"), (x0, x1, y1 - c, y1, -0.1, 0.15, "coping"),
                (x0, x0 + c, y0, y1, -0.1, 0.15, "coping"), (x1 - c, x1, y0, y1, -0.1, 0.15, "coping")]
        b = (x0 + c, x1 - c, y0 + c, y1 - c)
        if deep > 0:                                  # sunk into the ground: lining walls and a floor
            t = 0.3
            out += [(b[0], b[1], b[2], b[3], -deep - t, -deep, "pooltile"),
                    (b[0], b[1], b[2], b[2] + t, -deep, -0.1, "pooltile"), (b[0], b[1], b[3] - t, b[3], -deep, -0.1, "pooltile"),
                    (b[0], b[0] + t, b[2], b[3], -deep, -0.1, "pooltile"), (b[1] - t, b[1], b[2], b[3], -deep, -0.1, "pooltile")]
            if pool and min(b[1] - b[0], b[3] - b[2]) > 5:        # three steps down at one short end
                along_x = b[1] - b[0] >= b[3] - b[2]
                for i in range(3):
                    top = -(i + 1) * deep / 4
                    q = (b[0] + t + i * 1.2, b[0] + t + (i + 1) * 1.2, b[2] + t, b[3] - t) if along_x else \
                        (b[0] + t, b[1] - t, b[2] + t + i * 1.2, b[2] + t + (i + 1) * 1.2)
                    out.append((*q, -deep, top, "pooltile"))
                out += pool_ladder(b, along_x, deep)
            out.append((*b, -0.5, -0.45, "water"))
            if "FOUNTAIN" in (zn.get("label") or "").upper():      # a central jet
                cx, cy = (b[0] + b[1]) / 2, (b[2] + b[3]) / 2
                out += [(cx - 0.6, cx + 0.6, cy - 0.6, cy + 0.6, -0.5, 0.6, "coping"), (cx - 0.12, cx + 0.12, cy - 0.12, cy + 0.12, 0.6, 4.0, "water")]
        else:                                         # on a slab: a raised basin
            h = -deep
            t = 0.4
            out += [(b[0], b[1], b[2], b[3], 0.0, 0.1, "pooltile"),
                    (x0, x1, y0, y0 + t, 0, h + 0.15, "coping"), (x0, x1, y1 - t, y1, 0, h + 0.15, "coping"),
                    (x0, x0 + t, y0, y1, 0, h + 0.15, "coping"), (x1 - t, x1, y0, y1, 0, h + 0.15, "coping"),
                    (*b, h - 0.3, h - 0.25, "water")]
    if water_rect and (water_rect[1] - water_rect[0]) >= POOL_MIN_FT and (water_rect[3] - water_rect[2]) >= POOL_MIN_FT:
        # the model's water rectangle: a basin there, the rest of the pool area paved round it
        b = tuple(water_rect)
        cut = [(*b, -9, 9)]
        out = [o for o in out if o[6] != "coping"] + [
            (*q[:4], -0.1, 0.12, "coping") for o in out if o[6] == "coping" for q in subtract_all([(*o[:4], -0.1, 0.12)], cut)
        ]
        walk = [q[:4] for q in subtract_all([(*w, -1, 1) for w in walk], cut)]
        t = 0.3
        if k == 0:
            deep = 4.5
            out += [(b[0], b[1], b[2], b[3], -deep - t, -deep, "pooltile"),
                    (b[0], b[1], b[2], b[2] + t, -deep, -0.1, "pooltile"), (b[0], b[1], b[3] - t, b[3], -deep, -0.1, "pooltile"),
                    (b[0], b[0] + t, b[2], b[3], -deep, -0.1, "pooltile"), (b[1] - t, b[1], b[2], b[3], -deep, -0.1, "pooltile"),
                    (*b, -0.5, -0.45, "water")]
        else:
            out += [(*b, 0.0, 0.1, "pooltile"), (*b, 1.2, 1.25, "water")]
    return out, walk


# ------------------------------------------------------------------ helpers
def window_parts(windows):
    """frame + glass boxes for (x0,x1,y0,y1,sill,head) given at exact wall thickness."""
    out = []
    for x0, x1, y0, y1, s, h in windows:
        fr = 0.18
        if (x1 - x0) > (y1 - y0):
            ym = (y0 + y1) / 2
            t0, t1 = ym - 0.1, ym + 0.1
            out += [(x0, x1, t0, t1, s, s + fr, "frame"), (x0, x1, t0, t1, h - fr, h, "frame"),
                    (x0, x0 + fr, t0, t1, s, h, "frame"), (x1 - fr, x1, t0, t1, s, h, "frame")]
            n = max(1, round((x1 - x0) / 2.5))
            out += [(x0 + (x1 - x0) * i / n - fr / 2, x0 + (x1 - x0) * i / n + fr / 2, t0, t1, s, h, "frame") for i in range(1, n)]
            out.append((x0, x1, ym - 0.01, ym + 0.01, s, h, "glass"))
        else:
            xm = (x0 + x1) / 2
            t0, t1 = xm - 0.1, xm + 0.1
            out += [(t0, t1, y0, y1, s, s + fr, "frame"), (t0, t1, y0, y1, h - fr, h, "frame"),
                    (t0, t1, y0, y0 + fr, s, h, "frame"), (t0, t1, y1 - fr, y1, s, h, "frame")]
            n = max(1, round((y1 - y0) / 2.5))
            out += [(t0, t1, y0 + (y1 - y0) * i / n - fr / 2, y0 + (y1 - y0) * i / n + fr / 2, s, h, "frame") for i in range(1, n)]
            out.append((xm - 0.01, xm + 0.01, y0, y1, s, h, "glass"))
    return out


def zone_at(f, x, y):
    for z in f["rooms"]:
        for r in z["rects"]:
            if r[0] - 0.05 <= x <= r[1] + 0.05 and r[2] - 0.05 <= y <= r[3] + 0.05:
                return z
    return None


def bbox_of(rs):
    return (min(r[0] for r in rs), max(r[1] for r in rs), min(r[2] for r in rs), max(r[3] for r in rs))


def boxes_minus(base, holes):
    return disjoint(subtract_all([base], holes))


def zone_boxes(f, keep):
    return [(*r, -9, 99) for zn in f["rooms"] if keep(zn["type"]) for r in zn["rects"]]


def meet(a, b):
    """the overlaps of two lists of boxes (they may overlap one another: fine for cutting)"""
    return [tuple(v for i in range(3) for v in (max(p[2 * i], q[2 * i]), min(p[2 * i + 1], q[2 * i + 1])))
            for p in a for q in b if overlap(p, q)]


def upper_slab(k, well):
    """the slab under storey k >= 1 -> (slab boxes, void boxes), plan feet.
    It is this storey's floor and the roof of the storey below, so it spans both outlines. It is left open only
    where nothing stands on it: an OPEN / SHAFT / CUTOUT of this storey; a yard or garden of this storey over a part
    of the storey below that is open to the sky too, or over no storey at all (over a roofed room it is a terrace on
    that room's roof); an open area below with no room of this storey over it; and the stairwell."""
    f, below = floors[k], floors[k - 1]
    open_below = zone_boxes(below, lambda t: t in OPEN_SKY) + \
        subtract_all([(*bboxes[k], -9, 99)], [(*bboxes[k - 1], -9, 99)])
    voids = zone_boxes(f, lambda t: t in VOID)
    voids += meet(zone_boxes(f, lambda t: t in OPEN_SKY and t not in VOID), open_below)
    voids += subtract_all(zone_boxes(below, lambda t: t in OPEN_SKY), zone_boxes(f, lambda t: t not in OPEN_SKY))
    # a room's cells stop at the inner face of the outer wall: a void that close to the outline is open to it,
    # or a sliver of slab is left standing along the edge
    ux0, ux1 = min(bboxes[k][0], bboxes[k - 1][0]), max(bboxes[k][1], bboxes[k - 1][1])
    uy0, uy1 = min(bboxes[k][2], bboxes[k - 1][2]), max(bboxes[k][3], bboxes[k - 1][3])
    voids = [(v[0] - 1 if v[0] - ux0 < 0.6 else v[0], v[1] + 1 if ux1 - v[1] < 0.6 else v[1],
              v[2] - 1 if v[2] - uy0 < 0.6 else v[2], v[3] + 1 if uy1 - v[3] < 0.6 else v[3], -9, 99) for v in voids]
    base = disjoint([(*bboxes[k], -SLAB, -0.02), (*bboxes[k - 1], -SLAB, -0.02)])
    slab = [b for b in disjoint(subtract_all(base, voids + well)) if b[1] - b[0] > 0.01 and b[3] - b[2] > 0.01]
    return slab, voids


GUARD_T, GUARD_H = 0.33, 3.5      # as thick as a wall, as high as an upper storey's low walls


def edge_guards(f, slab, well):
    """a parapet along each edge of an upper slab that drops to the storey below or to the ground and has no wall or
    opening on it: terraces and balconies are closed like the roof, and the walker cannot step off them.
    None along the stairwell: the flights arrive across its edge."""
    t = GUARD_T
    solid = [(*b[:4], -9, 99) for b in slab] + [(w[0] - 0.5, w[1] + 0.5, w[2] - 0.5, w[3] + 0.5, -9, 99) for w in well]
    built = [(w[0] - t, w[1] + t, w[2] - t, w[3] + t, -9, 99) for w in f["walls"]] + \
            [(r[0] - t, r[1] + t, r[2] - t, r[3] + t, -9, 99) for r in (o["rect"] for o in f["openings"])]
    out = []
    for x0, x1, y0, y1, *_ in slab:
        ty, tx = min(t, y1 - y0), min(t, x1 - x0)          # (a slab piece thinner than a wall: the guard fills it)
        for probe, along_x, band in (((x0, x1, y0 - 0.05, y0), True, (y0, y0 + ty)), ((x0, x1, y1, y1 + 0.05), True, (y1 - ty, y1)),
                                     ((x0 - 0.05, x0, y0, y1), False, (x0, x0 + tx)), ((x1, x1 + 0.05, y0, y1), False, (x1 - tx, x1))):
            for p in subtract_all([(*probe, -9, 99)], solid):
                if (p[3] - p[2] if along_x else p[1] - p[0]) < 0.04:
                    continue                        # a rounding sliver between two slab pieces, not an open edge
                g = (p[0], p[1], *band) if along_x else (*band, p[2], p[3])
                out += subtract_all([(*g, 0, GUARD_H)], built)
    return [b for b in disjoint(out) if max(b[1] - b[0], b[3] - b[2]) >= 0.5 and min(b[1] - b[0], b[3] - b[2]) >= 0.2]


VENT_MAX = 2.6


def opening_heights(f, o):
    r = o["rect"]
    if o["type"] != "window":
        return (-1, 7.0)
    cx, cy = (r[0] + r[1]) / 2, (r[2] + r[3]) / 2
    sides = [zone_at(f, cx, cy - 1.0), zone_at(f, cx, cy + 1.0)] if o["axis"] == "x" else \
            [zone_at(f, cx - 1.0, cy), zone_at(f, cx + 1.0, cy)]
    wet = any(z and z["type"] == "toilet" for z in sides)
    width = max(r[1] - r[0], r[3] - r[2])
    return (6.0, 7.5) if wet or width <= VENT_MAX else (3.0, 7.0)


CURTAIN_ROOMS = {"bedroom", "living", "dining", "study", "room", "dress", "puja"}


def curtains(f, items):
    """linen curtains on a brass rod at each full-size window of a living room or bedroom, on the room side.
    Floor length, unless furniture stands in front of the window: then they stop above the sill."""
    for o in f["openings"]:
        if o["type"] != "window":
            continue
        sill, head = opening_heights(f, o)
        if sill >= 5:                        # high ventilator or bathroom window
            continue
        x0, x1, y0, y1 = o["rect"]
        along_x = o["axis"] == "x"
        a0, a1 = (x0, x1) if along_x else (y0, y1)
        for side in (-1, 1):
            face = (y0 if side < 0 else y1) if along_x else (x0 if side < 0 else x1)
            probe = (((x0 + x1) / 2, face + side), (face + side, (y0 + y1) / 2))[not along_x]
            zn = zone_at(f, *probe)
            if not zn or zn["type"] not in CURTAIN_ROOMS:
                continue
            plane = face + side * 0.3
            strip = (a0 - 0.6, a1 + 0.6, *sorted((face, face + side * 1.2)))
            if not along_x:
                strip = (strip[2], strip[3], strip[0], strip[1])
            blocked = any(it.get("box") and overlap((*strip, 0, 1), (*it["box"], 0, 1)) for it in items)
            bottom = sill - 0.3 if blocked else 0.1
            rod = min(head + 0.6, lib.WALL_H - 0.3)
            c = (a0 + a1) / 2
            # past the window edge by 0.6 ft, unless a door or another window is right there
            line = lambda q: (q["rect"][2] + q["rect"][3]) / 2 if along_x else (q["rect"][0] + q["rect"][1]) / 2
            near = [(q["rect"][0], q["rect"][1]) if along_x else (q["rect"][2], q["rect"][3]) for q in f["openings"]
                    if q is not o and q["axis"] == o["axis"] and abs(line(q) - line(o)) < 0.3]     # same wall
            ext = [0.05 if any(a0 - 0.8 <= e <= a0 + 0.01 for _, e in near) else 0.6,
                   0.05 if any(a1 - 0.01 <= e <= a1 + 0.8 for e, _ in near) else 0.6]
            r = item("curtain", c if along_x else plane, plane if along_x else c, 0 if along_x else 90)
            lo, hi = a0 - ext[0] - c, a1 + ext[1] - c           # rod ends, local x
            p_cyl(r, "curtain_rod", 0.05, 0.05, hi - lo + 0.2, "brass", (lo - 0.1, 0, rod), rot=(0, 90, 0), segs=12)
            for e in (lo - 0.1, hi + 0.1):
                p_cyl(r, "rod_end", 0.1, 0.1, 0.12, "brass", (e - 0.06, 0, rod), rot=(0, 90, 0), segs=12)
            pw = max(1.3, (a1 - a0) * 0.3)
            for e, s_ in ((lo, 1), (hi, -1)):                 # each panel gathered at one end of the rod
                p_pleats(r, "curtain", pw, rod - bottom, "curtain", (e + s_ * pw / 2, 0, bottom))
            done(r, collide=False)


# ------------------------------------------------------------------ stairs
def stair_parts(f, rise):
    """flights + landing from the detected tread runs. The flight next to the UP word starts at floor level
    at its UP end; the next flight starts where the previous one ended (dog-leg). -> (boxes, meta)"""
    fl = [dict(s) for s in f["stairs"]]
    if not fl:
        return [], []
    # The detector gives every flight near an UP word "up", and the flights of a dog-leg lie side by side, so both
    # get it: the climb starts on the flight that holds the word (nearest to it), not on whichever is listed first.
    words = [(p[1], p[2]) for s in fl for p in s.get("words") or [] if p[0].startswith("UP")]
    def gap(s, p):
        x0, x1, y0, y1 = s["rect"]
        return math.hypot(max(x0 - p[0], 0, p[0] - x1), max(y0 - p[1], 0, p[1] - y1))
    up = [min(fl, key=lambda s: gap(s, words[0]))] if words else [s for s in fl if s["up"]] or fl[:1]
    order = [up[0]] + [s for s in fl if s is not up[0]]
    boxes, meta = [], []
    z = 0.0
    prev_end = None
    per = rise / len(order)
    for k, s in enumerate(order):
        x0, x1, y0, y1 = s["rect"]
        ax = 0 if s["axis"] == "x" else 1      # direction of travel along x or y
        lo, hi = (x0, x1) if ax == 0 else (y0, y1)
        if k == 0:
            # start at the end nearest to the UP word
            w = next((p for p in s.get("words") or [] if p[0].startswith("UP")), None)
            pos = (w[1], w[2]) if w else ((x0 + x1) / 2, (y0 + y1) / 2)
            start = lo if abs(pos[ax] - lo) < abs(pos[ax] - hi) else hi
        else:
            start = lo if abs(prev_end - lo) < abs(prev_end - hi) else hi
        d = 1 if start == lo else -1
        n = max(3, s["steps"])
        run = (hi - lo) / n
        for i in range(n):
            a = start + d * i * run
            b = a + d * run
            a, b = min(a, b), max(a, b)
            zt = z + per * (i + 1) / n
            bx = (a, b, y0, y1, 0, zt) if ax == 0 else (x0, x1, a, b, 0, zt)
            boxes.append((*bx, "stair"))
        end = start + d * (hi - lo)
        meta.append(dict(rect=[x0, x1, y0, y1], axis=s["axis"], start=start, dir=d, z0=z, z1=z + per))
        z += per
        prev_end = end
        # landing beyond this flight's end, across the whole stair, if another flight follows
        if k + 1 < len(order):
            sb = bbox_of([q["rect"] for q in order])
            depth = (y1 - y0) if ax == 0 else (x1 - x0)
            if ax == 0:
                L = (end, end + d * depth) if d > 0 else (end + d * depth, end)
                lb = (max(L[0], sb[0] - depth), min(L[1], sb[1] + depth), sb[2], sb[3])
            else:
                L = (end, end + d * depth) if d > 0 else (end + d * depth, end)
                lb = (sb[0], sb[1], max(L[0], sb[2] - depth), min(L[1], sb[3] + depth))
            boxes.append((*lb, z - 0.5, z, "stair"))
            meta.append(dict(rect=list(lb), landing=True, z0=z, z1=z))
    return boxes, meta


# ------------------------------------------------------------------ procedural furniture not in lib
def nightstand(x, y, rot):
    group("nightstand", [(-0.75, 0.75, -0.7, 0.7, 0.2, 2.0, "teak"), (-0.7, 0.7, -0.75, -0.7, 1.15, 1.95, "laminate_w"),
                         (-0.2, 0.2, -0.82, -0.75, 1.5, 1.6, "brass")], x, y, rot, bevel=0.02)
    r = item("table_lamp", x, y, rot, z=2.0)
    p_cyl(r, "lamp_base", 0.18, 0.12, 0.7, "ceramic")
    p_cyl(r, "lamp_shade", 0.45, 0.3, 0.6, "curtain", (0, 0, 0.7), solid=0.01)
    done(r, collide=False)


def sofa(x, y, rot, w=7.0):
    """velvet sofa: rounded arms and back, loose seat and back cushions, throw pillows, brass feet"""
    hw = w / 2
    r = item("sofa", x, y, rot)
    for sx in (-1, 1):
        for sy in (-1, 1):
            p_cyl(r, "sofa_foot", 0.08, 0.05, 0.35, "brass", (sx * (hw - 0.35), sy * 1.2, 0), segs=16)
    p_soft(r, "sofa_base", w, 3.0, 0.9, "velvet", (0, 0, 0.35), r=0.12)
    for s_ in (-1, 1):
        p_soft(r, "sofa_arm", 0.62, 3.0, 1.9, "velvet", (s_ * (hw - 0.31), 0, 0.35), r=0.25)
    p_soft(r, "sofa_back", w - 1.2, 0.6, 1.55, "velvet", (0, 1.2, 1.2), r=0.2)
    n = max(2, round((w - 1.24) / 2.2))
    cw = (w - 1.24) / n
    for i in range(n):
        cx = -hw + 0.62 + cw * (i + 0.5)
        p_soft(r, "seat_cushion", cw - 0.04, 2.35, 0.55, "velvet", (cx, -0.3, 1.2), r=0.2)
        p_soft(r, "back_cushion", cw - 0.06, 0.55, 1.45, "velvet", (cx, 0.62, 1.68), (-12, 0, 0), r=0.24)
    for s_, m in ((-1, "jacquard"), (1, "boucle")):
        p_soft(r, "throw_pillow", 1.3, 0.38, 1.3, m, (s_ * (hw - 1.45), 0.2, 1.72), (-24, 0, -s_ * 12), r=0.22)
    return done(r)


def coffee_table(x, y, rot):
    """tea table: oval white marble top on a walnut base with a shelf; books and a bowl on top"""
    r = item("coffee_table", x, y, rot)
    p_cyl(r, "table_top", 1.0, 1.0, 0.1, "marble_top", (0, 0, 1.35), sx=1.8, segs=64, bevel=0.03, seg=2)
    p_cyl(r, "table_apron", 0.92, 0.92, 0.18, "teak", (0, 0, 1.17), sx=1.82, segs=64)
    p_cyl(r, "table_shelf", 0.85, 0.85, 0.08, "teak", (0, 0, 0.35), sx=1.8, segs=64)
    for sx in (-1, 1):
        for sy in (-1, 1):
            p_cyl(r, "table_leg", 0.07, 0.1, 1.17, "teak", (sx * 1.05, sy * 0.48, 0), segs=16)
    p_box(r, "book", 0.9, 0.65, 0.1, "blue_accent", (-0.7, 0.05, 1.45), (0, 0, 8), bevel=0.01)
    p_box(r, "book", 0.8, 0.6, 0.08, "throw", (-0.68, 0.08, 1.55), (0, 0, -4), bevel=0.01)
    p_bowl(r, "bowl", 0.35, 0.22, "ceramic", (0.75, -0.05, 1.67))
    p_box(r, "tray", 1.0, 0.6, 0.05, "brass", (0.0, 0.0, 0.43), bevel=0.01)
    return done(r)


def tv_unit(x, y, rot):
    group("tv_unit", [(-2.5, 2.5, -0.7, 0.7, 0.5, 1.9, "teak"), (-2.4, 2.4, -0.72, -0.7, 0.7, 1.7, "laminate_w")],
          x, y, rot, bevel=0.02)
    r = math.radians(rot)                 # the unit's back (local +y, 0.7 ft) is on the wall: hang the TV 0.1 ft off it
    tv(x - 0.5 * math.sin(r), y + 0.5 * math.cos(r), rot, z=3.4)


def dining_set(x, y, rot, w=6.0, d=3.2, seats=6):
    hw, hd = w / 2, d / 2
    group("dining_table", [(-hw, hw, -hd, hd, 2.35, 2.5, "teak"),
                           *[(sx * (hw - 0.4) - 0.12, sx * (hw - 0.4) + 0.12, sy * (hd - 0.4) - 0.12, sy * (hd - 0.4) + 0.12, 0, 2.35, "teak")
                             for sx in (-1, 1) for sy in (-1, 1)]], x, y, rot, bevel=0.02)
    per = seats // 2
    for side in (-1, 1):
        for i in range(per):
            cx = -hw + w * (i + 0.5) / per
            cy = side * (hd + 0.6)
            a = math.radians(rot)
            wx, wy = x + cx * math.cos(a) - cy * math.sin(a), y + cx * math.sin(a) + cy * math.cos(a)
            chair(wx, wy, rot + (180 if side < 0 else 0))      # backrest on the side away from the table


def chair(x, y, rot):
    """at rot 0 the backrest ends up on +y (drawn on -y, turned 180 by the group call)"""
    group("chair", [(-0.8, 0.8, -0.8, 0.8, 1.45, 1.6, "teak"), (-0.8, 0.8, -0.85, -0.7, 1.6, 3.2, "teak"),
                    *[(sx * 0.65 - 0.07, sx * 0.65 + 0.07, sy * 0.65 - 0.07, sy * 0.65 + 0.07, 0, 1.45, "teak")
                      for sx in (-1, 1) for sy in (-1, 1)],
                    (-0.7, 0.7, -0.7, 0.7, 1.6, 1.75, "cushion")], x, y, rot + 180, bevel=0.02, collide=False)


def car(x, y, rot):
    place("covered_car", x, y, rot, collide=False)


import bmesh, random  # noqa: E402

mat("foliage", rough=0.9, tex="leafy_grass", tile=0.6, tint=(0.35, 0.55, 0.25))
mat("bark", (0.25, 0.18, 0.12), 0.9)


def blob(root, name, r, loc, mn="foliage", sub=2, jitter=0.18, seed=0):
    """lumpy low-poly sphere (icosphere with random push) for foliage"""
    rnd = random.Random(seed)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r * lib.F)
    for v in bm.verts:
        v.co *= 1 + rnd.uniform(-jitter, jitter)
    return lib._mesh_obj(name, bm, mn, root, loc, smooth=60)


def tree(x, y, s=1.0, seed=0):
    """light procedural tree: tapered trunk + clustered canopy (~3k triangles)"""
    rnd = random.Random(seed)
    r = item("tree", x, y, 0)
    p_cyl(r, "trunk", 0.45 * s, 0.25 * s, 9 * s, "bark", segs=12)
    for k in range(6):
        a = rnd.uniform(0, 2 * math.pi)
        d = rnd.uniform(1.0, 3.2) * s
        blob(r, "canopy", rnd.uniform(2.6, 3.8) * s, (math.cos(a) * d, math.sin(a) * d, (9 + rnd.uniform(0, 4)) * s),
             sub=3, seed=seed * 10 + k)
    return done(r, collide=False)


# real potted plants (Poly Haven, CC0; fetch_assets.py) when they are downloaded; the drawn blob is only the fallback
PLANT = "potted_plant_02"       # 0.7 m as modelled; a floor plant stands about 1.1 m


def plant(x, y, rot):
    if os.path.exists(os.path.join(ASSETS, "models", PLANT, f"{PLANT}_1k.gltf")):
        root = place(PLANT, x, y, rot, scale=1.6, collide=False)
        # not baked: its leaf material turned a storey's whole light map black (PATCHES §31); lit in real time, as
        # the trees are
        for o in [root, *root.children_recursive]:
            o["unbaked"] = True
        return root
    r = item("plant", x, y, rot)
    p_cyl(r, "pot", 0.55, 0.75, 1.5, "terracotta", segs=24)
    p_cyl(r, "soil", 0.68, 0.68, 0.05, "concrete", (0, 0, 1.4), segs=24)
    for k, (dx, dy, dz, rr) in enumerate(((0, 0, 2.6, 0.9), (0.4, 0.2, 3.3, 0.7), (-0.35, -0.2, 3.1, 0.65), (0, 0.1, 3.9, 0.55))):
        blob(r, "leaves", rr, (dx, dy, dz), sub=2, jitter=0.25, seed=int(rot) + k)
    return done(r, collide=False)


def outdoor_set(x, y, rot):
    place("outdoor_table_chair_set_01", x, y, rot, collide=False)


mat("rug_round", rough=1.0, tex="caban", tile=0.9, tint=(0.86, 0.83, 0.78))


def bathtub(x, y, rot, l=5.4, w=2.6, h=1.8):
    """built-in tub along a wall (long side on local x, back against +y)"""
    t, hl, hw = 0.25, l / 2, w / 2
    group("bathtub", [(-hl, hl, -hw, hw, 0, 0.35, "white_gloss"),
                      (-hl, hl, -hw, -hw + t, 0.35, h, "white_gloss"), (-hl, hl, hw - t, hw, 0.35, h, "white_gloss"),
                      (-hl, -hl + t, -hw + t, hw - t, 0.35, h, "white_gloss"), (hl - t, hl, -hw + t, hw - t, 0.35, h, "white_gloss"),
                      (-hl + 0.4, -hl + 0.55, hw - 0.5, hw - 0.3, h, h + 0.6, "chrome"),
                      (-hl + 0.4, -hl + 0.95, hw - 0.42, hw - 0.36, h + 0.5, h + 0.58, "chrome")], x, y, rot, bevel=0.04)


def round_rug(x, y, r=4.0):
    root = item("round_rug", x, y, 0)
    p_cyl(root, "rug", r, r, 0.05, "rug_round", segs=72)
    done(root, collide=False)


def model(name, x, y, rot=0, z=0.0, scale=1.0):
    place(name, x, y, rot, z=z, scale=scale, collide=False)


# the asset library (services/planto3d/library, built by library/build/): pieces in the house style, used in place of
# the built-in builders when present. PLAN3D_LIBRARY=0 turns it off
LIB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "library")
LIBRARY = {}
if os.environ.get("PLAN3D_LIBRARY", "1") != "0" and os.path.exists(os.path.join(LIB_DIR, "index.json")):
    with open(os.path.join(LIB_DIR, "index.json")) as _fh:
        # usable: approved entries, the team-made pieces, and unreviewed AI-made ones only with PLAN3D_USE_UNREVIEWED
        _unrev = os.environ.get("PLAN3D_USE_UNREVIEWED", "").lower() in ("1", "true", "yes")
        LIBRARY = {e["id"]: e for e in json.load(_fh)["entries"] if e.get("review") == "approved" or
                   (e.get("review") != "rejected" and (str(e.get("source", "")).startswith("team-made") or _unrev))}
HANGING = {"chandelier", "pendant_cluster"}       # hung from the ceiling over (x, y), at their own size
USED_KITS = {}                                   # piece -> how many times the library served it (meta.json)
# build_report.json: per room and area what was read and what was built, and by which builder (PATCHES 53)
REPORT = {"zones": [], "items": []}


def _box_area(bs):
    return round(sum(max(0.0, b[1] - b[0]) * max(0.0, b[3] - b[2]) for b in bs), 2)


SIZE_TOLERANCE = 0.05   # a room built more than 5% away from the plan is an error (PATCHES 54)
_DIM = re.compile(r"""(\d{1,3})\s*['’]\s*-?\s*(\d{1,2})?\s*(?:"|”)?\s*[xX×*]\s*(\d{1,3})\s*['’]?\s*-?\s*(\d{1,2})?""")


def _label_ft(label):
    m = _DIM.search(label or "")
    if not m:
        return None
    a, ai, b, bi = m.groups()
    return float(a) + float(ai or 0) / 12, float(b) + float(bi or 0) / 12


def _size_errors(entry, zn):
    """Rooms built more than SIZE_TOLERANCE away from the plan: from their read area (a floor
    the build cut short) and from the size their label states."""
    out = []
    name = entry["label"] or entry["type"]
    built, read = entry.get("built_area_ft2"), entry["read_area_ft2"]
    if built is not None and read > 1 and entry["type"] not in ("stair", "open", "duct", "lift") and \
            abs(built - read) / read > SIZE_TOLERANCE and not entry.get("water_area_ft2"):
        out.append(f"{name}: built {built:.0f} sq ft, the plan has {read:.0f} sq ft")
    dims = _label_ft(zn.get("label"))
    rects = zn.get("rects") or []
    if dims and rects:
        q = max(rects, key=lambda r: (r[1] - r[0]) * (r[3] - r[2]))
        w, h = sorted((q[1] - q[0], q[3] - q[2]))
        a, b = sorted(dims)
        diff = max(abs(w - a) / a, abs(h - b) / b) if a and b else 0
        if diff > SIZE_TOLERANCE:
            out.append(f"{name}: built {w:.1f} x {h:.1f} ft, its label says {a:.1f} x {b:.1f} ft ({diff:.0%})")
    return out


def _report_zone(k, zn, builder, built_boxes=None, water_boxes=None):
    rects = zn.get("rects") or []
    xs = [v for r in rects for v in (r[0], r[1])]
    ys = [v for r in rects for v in (r[2], r[3])]
    entry = dict(floor=k, type=zn["type"], label=zn.get("label") or "", builder=builder,
                 read_area_ft2=_box_area(rects),
                 read_size_ft=[round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2)] if rects else None)
    if built_boxes is not None:
        entry["built_area_ft2"] = _box_area(built_boxes)
    if water_boxes is not None:
        entry["water_area_ft2"] = _box_area(water_boxes)
        if water_boxes:
            wx = [v for b in water_boxes for v in (b[0], b[1])]
            wy = [v for b in water_boxes for v in (b[2], b[3])]
            entry["water_size_ft"] = [round(max(wx) - min(wx), 2), round(max(wy) - min(wy), 2)]
    entry["errors"] = _size_errors(entry, zn)
    REPORT["zones"].append(entry)


def library_model(it):
    e = LIBRARY.get(it["fn"])
    if not e:
        return False
    path = os.path.join(LIB_DIR, e["browser"])
    if not os.path.exists(path):
        return False
    ok = custom(it, path, any_fn=True)
    if ok:
        USED_KITS[it["fn"]] = USED_KITS.get(it["fn"], 0) + 1
    return ok


def custom(it, path=None, any_fn=False):
    """the person's own model (assets/custom/<fn>.glb) in place of a built-in item, fitted to the item's footprint;
    with `path`, that model (a library piece)"""
    path = path or os.path.join(ASSETS, "custom", *([FURNITURE_SET] if FURNITURE_SET else []), it["fn"] + ".glb")
    x0, x1, y0, y1 = it.get("box") or (0, 0, 0, 0)
    hang = it["fn"] in HANGING
    if not hang and ((it["fn"] not in CATALOG and not any_fn) or x1 - x0 < 0.1 or y1 - y0 < 0.1):
        return False
    if not os.path.exists(path):
        return False
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)        # shortcut: imported once per item, fine for a house; cache if plans grow huge
    new = [o for o in bpy.data.objects if o not in before]
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in new if o.type == "MESH" for c in o.bound_box]
    if not pts:
        return False
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    rot = it["args"][2]
    if hang:              # at its own size over the point it was given
        s = 1.0
        x0 = x1 = it["args"][0]
        y0 = y1 = it["args"][1]
    else:
        bw, bd = ((y1 - y0), (x1 - x0)) if round(rot) % 180 == 90 else ((x1 - x0), (y1 - y0))
        s = min(bw * lib.F / max(hi.x - lo.x, 1e-6), bd * lib.F / max(hi.y - lo.y, 1e-6))
    root = bpy.data.objects.new(f"custom_{it['fn']}", None)
    collection("furniture").objects.link(root)
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        collection("furniture").objects.link(o)
        if o.parent is None:
            o.location -= Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))     # centred, standing on the floor
            o.parent = root
    root.scale = (s, s, s)
    root.rotation_euler = (0, 0, math.radians(rot))
    root.location = ((x0 + x1) / 2 * lib.F, (y0 + y1) / 2 * lib.F, lib.LEVEL * lib.F)
    return True


CALLS = dict(kitchen_island=kitchen_island, bar_stool=bar_stool, wall_art=wall_art, bathtub=bathtub, round_rug=round_rug, model=model, bed=bed, nightstand=nightstand, wardrobe=wardrobe, desk=desk, wc2=wc2, vanity=vanity,
             shower2=lambda x, y, rot: shower2(x, y, rot), geyser=lambda x, y, rot: geyser(x, y, rot),
             kitchen_run=kitchen_run, chimney=chimney, wall_cab2=wall_cab2, fridge2=fridge2, washer2=washer2,
             oven_stack=oven_stack,
             puja_mandir=puja_mandir, sofa=sofa, coffee_table=coffee_table, rug=rug, tv_unit=tv_unit,
             dining_set=dining_set, car=car, plant=plant, outdoor_set=outdoor_set)


# ------------------------------------------------------------------ build each storey
COLLIDERS, META_FLOORS, LAMPS = [], [], []
WET_GROUND = []     # pools, water and docks of the ground storey: the plinth and the site ground are open over them
by_floor = {}
DOWNLIGHT_ROOMS = {"living", "dining", "kitchen", "bedroom", "study", "foyer", "breakfast", "bar", "cinema"}
UNBAKED = []           # objects lit in real time in the walkthrough instead of baked (see plant)


PLINTH_H, PLINTH_T = 2.5, 0.08      # feet: height of the stone base on outer walls, and how far it stands out


def plinth_boxes(f, cuts):
    """boxes of stone cladding on every outer face of the storey's full-height walls (a face with no indoor room 1 ft
    beyond it at three points along it), cut away where a door or an opening reaches the floor"""
    rooms_in = [q for zn in f["rooms"] if zn["type"] in INDOOR for q in zn["rects"]]
    inside = lambda x, y: any(q[0] <= x <= q[1] and q[2] <= y <= q[3] for q in rooms_in)
    out = []
    for w in f["walls"]:
        if w[4]:
            continue
        x0, x1, y0, y1 = w[:4]
        if x1 - x0 >= y1 - y0:
            xs = [x0 + (x1 - x0) * t for t in (0.15, 0.5, 0.85)]
            if not any(inside(x, y0 - 1.0) for x in xs):
                out.append((x0, x1, y0 - PLINTH_T, y0, 0.0, PLINTH_H))
            if not any(inside(x, y1 + 1.0) for x in xs):
                out.append((x0, x1, y1, y1 + PLINTH_T, 0.0, PLINTH_H))
        else:
            ys = [y0 + (y1 - y0) * t for t in (0.15, 0.5, 0.85)]
            if not any(inside(x0 - 1.0, y) for y in ys):
                out.append((x0 - PLINTH_T, x0, y0, y1, 0.0, PLINTH_H))
            if not any(inside(x1 + 1.0, y) for y in ys):
                out.append((x1, x1 + PLINTH_T, y0, y1, 0.0, PLINTH_H))
    doors = [(c[0] - 0.1, c[1] + 0.1, c[2] - 0.4, c[3] + 0.4, -1.0, PLINTH_H + 1) for c in cuts if c[4] < 0.5]
    return disjoint(subtract_all(out, doors))


def new_objects(before):
    return [o for o in bpy.data.objects if o not in before]


bboxes = [bbox_of([w[:4] for w in f["walls"]]) for f in floors]
stair_box_prev = None
# The floor above a stair is cut only where the steps below come within head height of it (and over landings): over
# the first steps of a flight there is floor, and on the storey above that floor is where its own stair begins.
HEADROOM = 7.0
well_prev = []
for k, f in enumerate(floors):
    z = (k + BASE) * FFH
    set_level(z)
    before = set(bpy.data.objects)
    low_h = 5.0 if k == 0 and not BASE else 3.5      # boundary walls on the ground, parapets above it
    cuts, wins, door_list = [], [], []
    for o in f["openings"]:
        x0, x1, y0, y1 = o["rect"]
        s, hd = opening_heights(f, o)
        if o["axis"] == "x":
            c = (x0, x1, y0 - 0.06, y1 + 0.06, s, hd)
        else:
            c = (x0 - 0.06, x1 + 0.06, y0, y1, s, hd)
        cuts.append(c)
        if o["type"] == "window":
            wins.append((x0, x1, y0, y1, s, hd))
        else:
            door_list.append(o)
    walls_f = [list(w) for w in f["walls"]]
    if f["stairs"]:
        fb = bbox_of([s["rect"] for s in f["stairs"]])
        ax = f["stairs"][0]["axis"]
        for w in walls_f:      # low walls in the stair band (mid wall, landing edges) stop where the flights stop
            cx, cy = (w[0] + w[1]) / 2, (w[2] + w[3]) / 2
            in_band = (fb[2] - 0.2 <= cy <= fb[3] + 0.2 and fb[0] - 6 <= cx <= fb[1] + 6) if ax == "x" else \
                      (fb[0] - 0.2 <= cx <= fb[1] + 0.2 and fb[2] - 6 <= cy <= fb[3] + 6)
            if w[4] and in_band:
                if ax == "x":
                    w[0], w[1] = max(w[0], fb[0]), min(w[1], fb[1])
                else:
                    w[2], w[3] = max(w[2], fb[2]), min(w[3], fb[3])
        walls_f = [w for w in walls_f if w[1] - w[0] > 0.05 and w[3] - w[2] > 0.05]
        # a mid wall drawn dashed comes in pieces: join low pieces on one line with small gaps
        merged = True
        while merged:
            merged = False
            for a in walls_f:
                for b in walls_f:
                    if a is b or not (a[4] and b[4]):
                        continue
                    if ax == "x" and abs(a[2] - b[2]) < 0.1 and abs(a[3] - b[3]) < 0.1 and -0.05 < b[0] - a[1] < 1.0:
                        a[1] = b[1]; walls_f.remove(b); merged = True; break
                    if ax == "y" and abs(a[0] - b[0]) < 0.1 and abs(a[1] - b[1]) < 0.1 and -0.05 < b[2] - a[3] < 1.0:
                        a[3] = b[3]; walls_f.remove(b); merged = True; break
                if merged:
                    break
    f["walls"] = walls_f
    wb = [(*w[:4], 0, (low_h if w[4] else H)) for w in f["walls"]]
    # detected openings are gaps between walls: fill the wall below the sill and above the head (lintel)
    for o, c in zip(f["openings"], cuts):
        r = o["rect"]
        touching = [w for w in f["walls"] if w[0] <= r[1] + 0.3 and r[0] <= w[1] + 0.3 and w[2] <= r[3] + 0.3 and r[2] <= w[3] + 0.3]
        top = H if any(not w[4] for w in touching) or not touching else low_h
        if c[4] > 0:
            wb.append((*r, 0, c[4]))
        if c[5] < top:
            wb.append((*r, c[5], top))
    wb = disjoint(subtract_all(wb, cuts))
    mesh_from_boxes(f"walls_{k}", [(*b, "wall") for b in wb])
    if k == 0:          # a stone plinth along the outside faces of the ground storey's outer walls (not at doors)
        clad = plinth_boxes(f, cuts)
        if clad:
            mesh_from_boxes(f"plinth_clad_{k}", [(*b, "plinth_stone") for b in clad])
    parts = window_parts(wins)
    mesh_from_boxes(f"window_frames_{k}", [b for b in parts if b[6] == "frame"], bevel=0.005)
    mesh_from_boxes(f"glass_{k}", [b for b in parts if b[6] == "glass"])
    # door frames only: leaves of neighbouring doors swing into each other and hide side doors
    frames = []
    for o in door_list:
        x0, x1, y0, y1 = o["rect"]
        t = 0.25
        if o["axis"] == "x":
            frames += [(x0, x0 + t, y0, y1, 0, 7, "teak"), (x1 - t, x1, y0, y1, 0, 7, "teak"), (x0, x1, y0, y1, 7 - t, 7, "teak")]
        else:
            frames += [(x0, x1, y0, y0 + t, 0, 7, "teak"), (x0, x1, y1 - t, y1, 0, 7, "teak"), (x0, x1, y0, y1, 7 - t, 7, "teak")]
    mesh_from_boxes(f"door_frames_{k}", frames, bevel=0.004)
    # floors per zone (none over the stairwell coming up from below, nor over a void of an upper storey)
    fl = {}
    well = [(*r, -9, 99) for r in well_prev]
    slab, voids = upper_slab(k, well) if k else ([], [])
    water, wet_walk, blocked_areas, custom_objects, platforms = [], [], [], [], []
    for zn in f["rooms"]:
        if zn["type"] in WATER:            # built as water, not as a floor (water_parts)
            parts, deck = water_parts(zn, k)
            water += parts
            wet_walk += deck
            _report_zone(k, zn, "water_parts", [b for b in parts if b[6] == "coping"],
                         [b for b in parts if b[6] == "water"])
            continue
        if zn["type"] == "court":          # its own surface and markings (court_parts)
            water += court_parts(zn)
            _report_zone(k, zn, "court_parts")
            continue
        if zn["type"] == "custom" and LIBRARY.get(str(zn.get("area_type") or "")) and \
                LIBRARY[zn["area_type"]].get("source") == "creator agent":
            # the creator agent's asset for this area type, fitted to the area (its own floor, walkable)
            e = LIBRARY[zn["area_type"]]
            for r in zn["rects"]:
                if custom(dict(fn=zn["area_type"], box=r, args=[(r[0] + r[1]) / 2, (r[2] + r[3]) / 2, 0]),
                          os.path.join(LIB_DIR, e["browser"]), any_fn=True):
                    USED_KITS[zn["area_type"]] = USED_KITS.get(zn["area_type"], 0) + 1
            _report_zone(k, zn, f"creator kit {zn['area_type']}", zn["rects"])
            continue
        if zn["type"] == "custom":         # an area built from its spec (areaspec.py), or a labelled generic zone
            spec = areaspec.spec_for(zn.get("area_type") or zn.get("label"))
            for r in zn["rects"]:
                bxs, objs, walkable = areaspec.parts(spec, r)
                water += bxs
                if not walkable:
                    blocked_areas.append(r)
                elif spec and spec["height"]["mode"] == "raised":   # stood on: the walker climbs onto it (walk.js)
                    platforms.append((r, bxs[0][5]))     # the surface is parts()'s first box
                for part, ox_, oy_, rot in objs:
                    custom_objects.append((part, ox_, oy_, rot))
            _report_zone(k, zn, f"area spec {spec['id'] if spec and 'id' in spec else (zn.get('area_type') or 'generic')}",
                         zn["rects"])
            continue
        if zn["type"] == "parking":
            water += parking_parts(zn)
        m = FLOOR_MAT.get(zn["type"], "tile")
        built = [(*b[:4], -0.02, 0.0, m) for r in zn["rects"] for b in subtract_all([(*r, -0.02, 0.0)], well + voids)]
        fl.setdefault(m, []).extend(built)
        _report_zone(k, zn, f"floor {m}" + (" + parking_parts" if zn["type"] == "parking" else ""), built)
    for m, bs in fl.items():
        mesh_from_boxes(f"floor_{k}_{m}", bs)
    if water:     # the water planes apart: a transparent object is not baked, so the basin and decks must not share it
        clear = ("water", "fence")             # see-through: kept out of the bake, so in objects of their own
        solid_w = [b for b in water if b[6] not in clear]
        if solid_w:
            mesh_from_boxes(f"pool_{k}", solid_w)
        for m in clear:
            if any(b[6] == m for b in water):
                mesh_from_boxes(f"{m}_{k}", [b for b in water if b[6] == m])
    # the walker cannot enter water (except a dock's deck) or a lift / duct shaft
    closed = subtract_all([(*r, 0, 1) for zn in f["rooms"] if zn["type"] in WATER | SHAFT for r in zn["rects"]]
                          + [(*r, 0, 1) for r in blocked_areas], [(*q, 0, 1) for q in wet_walk])
    for part, px, py, rot in custom_objects:          # the spec's objects, from parts we already build
        if part == "plant":
            plant(px, py, rot)
        elif part == "outdoor_set":
            outdoor_set(px, py, rot)
        elif part == "car":
            car(px, py, rot)
        else:                                          # bench, lamp, post, flag: simple shapes
            dims = dict(bench=(2.5, 0.8, 1.5, "deck"), lamp=(0.3, 0.3, 9.0, "steel"), post=(0.4, 0.4, 4.0, "steel"),
                        flag=(0.2, 0.2, 16.0, "steel"))[part]
            mesh_from_boxes(f"{part}_{k}_{px:.0f}_{py:.0f}", [(px - dims[0] / 2, px + dims[0] / 2, py - dims[1] / 2, py + dims[1] / 2, 0, dims[2], dims[3])])
    # wall tiles to 7 ft in toilets
    # (the room's cells stop a little short of the wall face, so door holes are widened across for the tiles,
    # and edges shared by two slices of the same room are not walls)
    tiles = []
    door_holes = [(c[0] - 0.6, c[1] + 0.6, c[2], c[3], c[4], c[5]) if o["axis"] == "y" else
                  (c[0], c[1], c[2] - 0.6, c[3] + 0.6, c[4], c[5]) for o, c in zip(f["openings"], cuts)]
    for zn in f["rooms"]:
        if zn["type"] != "toilet":
            continue
        for r in zn["rects"]:
            x0, x1, y0, y1 = r
            tt = 0.03
            own = [(q[0] - 0.05, q[1] + 0.05, q[2] - 0.05, q[3] + 0.05, -1, 99) for q in zn["rects"] if q is not r]
            tiles += subtract_all([(x0, x1, y0, y0 + tt, 0, 7), (x0, x1, y1 - tt, y1, 0, 7),
                                   (x0, x0 + tt, y0, y1, 0, 7), (x1 - tt, x1, y0, y1, 0, 7)], own)
    if tiles:
        mesh_from_boxes(f"toilet_tiles_{k}", [(*b, "walltile") for b in disjoint(subtract_all(tiles, door_holes))])
    # slab under this storey (k >= 1, see upper_slab), with parapets where its edge drops away
    bb = bboxes[k]
    guards = []
    if k == 0 and BASE:
        # the storeys below are not drawn: a plain block under the outline, and this storey's floor is a slab on it
        mesh_from_boxes("plinth", [(bb[0] - 0.2, bb[1] + 0.2, bb[2] - 0.2, bb[3] + 0.2, -z - 0.6, -z - 0.02, "concrete")])
        mesh_from_boxes("storeys_below", [(*bb, -z - 0.02, -SLAB, "exterior")])
        slab = [(*bb, -SLAB, -0.02)]
        mesh_from_boxes(f"slab_{k}", [(*b[:4], -SLAB, -0.02, "ceiling") for b in slab])
        guards = edge_guards(f, slab, well)
        if guards:
            mesh_from_boxes(f"guards_{k}", [(*b, "exterior") for b in guards])
    elif k == 0:      # (open over pools, water and docks: they are sunk into it)
        wet = [(*r, -9, 99) for zn in f["rooms"] if zn["type"] in WATER for r in zn["rects"]]
        WET_GROUND.extend(wet)
        mesh_from_boxes("plinth", subtract_all([(bb[0] - 0.2, bb[1] + 0.2, bb[2] - 0.2, bb[3] + 0.2, -0.6, -0.02, "concrete")], wet))
    else:
        mesh_from_boxes(f"slab_{k}", [(*b[:4], -SLAB, -0.02, "ceiling") for b in slab])
        guards = edge_guards(f, slab, well)
        if guards:
            mesh_from_boxes(f"guards_{k}", [(*b, "exterior") for b in guards])
    # stairs rising from this storey
    sboxes, smeta = stair_parts(f, FFH)
    # a spiral stair (the detector or the review page marks it): wedge treads round a column instead of box flights;
    # the walker still climbs along its rectangle (meta.json)
    for s_ in f["stairs"]:
        if s_.get("shape") == "spiral":
            r_ = s_["rect"]
            sboxes = [b for b in sboxes if not (r_[0] - 0.1 <= b[0] and b[1] <= r_[1] + 0.1 and r_[2] - 0.1 <= b[2] and b[3] <= r_[3] + 0.1)]
            spiral_stair(f"spiral_{k}", r_, 0.0, FFH, steps=s_.get("steps"))
    spirals = [tuple(s_["rect"]) for s_ in f["stairs"] if s_.get("shape") == "spiral"]
    if sboxes or spirals:
        if sboxes:
            mesh_from_boxes(f"stairs_{k}", sboxes)
        stair_box_prev = bbox_of([b[:4] for b in sboxes] + spirals)
        # the floor above opens over a spiral stair's whole footprint (it climbs all round)
        well_prev = [b[:4] for b in sboxes if b[5] > FFH - HEADROOM] + spirals
    else:
        stair_box_prev, well_prev = None, []
    # furniture: none if the review page's "Furniture" box was unticked; hand-placed items win over the rules
    items = [] if plan.get("furnish") is False else f.get("items") or furnish.furnish_floor(f)
    for it in items:
        src = "failed"
        try:
            if custom(it):
                src = "own model"
            elif library_model(it):
                src = "library kit"
            elif it["fn"] in CALLS:
                CALLS[it["fn"]](*it["args"], **it["kw"])
                src = "built-in"
            else:
                src = "skipped"
                print("ITEM SKIPPED (library piece not built)", it["fn"], flush=True)
        except Exception as e:     # one bad item must not stop the build
            print("ITEM FAILED", it["fn"], e, flush=True)
        REPORT["items"].append(dict(floor=k, room=it.get("room", ""), fn=it["fn"], source=src))
    if items:
        curtains(f, items)
    # lifts: a landing door on the side facing the most open neighbour, a call panel beside it, and on the lowest
    # storey a cabin standing in the shaft (the shaft stays closed to the walker)
    for zn in f["rooms"]:
        if zn["type"] != "lift" or not zn["rects"]:
            continue
        x0, x1, y0, y1 = max(zn["rects"], key=lambda r: (r[1] - r[0]) * (r[3] - r[2]))
        t_ = 0.75
        def open_at(px, py):
            r2 = next((z for z in f["rooms"] if z is not zn and any(q[0] <= px <= q[1] and q[2] <= py <= q[3] for q in z["rects"])), None)
            return r2 is not None and r2["type"] not in WATER | SHAFT
        sides = {"S": ((x0 + x1) / 2, y0 - t_ - 1.5), "N": ((x0 + x1) / 2, y1 + t_ + 1.5), "W": (x0 - t_ - 1.5, (y0 + y1) / 2), "E": (x1 + t_ + 1.5, (y0 + y1) / 2)}
        side = next((sd for sd in "SNWE" if open_at(*sides[sd])), "S")
        dw = min(3.5, (x1 - x0 if side in "SN" else y1 - y0) - 0.6)
        c = (x0 + x1) / 2 if side in "SN" else (y0 + y1) / 2
        face = {"S": y0 - t_, "N": y1 + t_, "W": x0 - t_, "E": x1 + t_}[side]
        out = 1 if side in "NE" else -1
        f0, f1 = sorted((face, face + out * 0.08))
        g0, g1 = sorted((face, face + out * 0.12))
        if side in "SN":
            door = [(c - dw / 2, c, f0, f1, 0.0, 7.0, "steel"), (c, c + dw / 2, f0, f1, 0.0, 7.0, "steel"),
                    (c - dw / 2 - 0.25, c + dw / 2 + 0.25, g0, g1, 7.0, 7.4, "chrome"),
                    (c + dw / 2 + 0.5, c + dw / 2 + 0.85, g0, g1, 3.2, 3.9, "chrome"),
                    (c + dw / 2 + 0.6, c + dw / 2 + 0.75, g0 - 0.01, g1 + 0.01, 3.45, 3.6, "light")]
        else:
            door = [(f0, f1, c - dw / 2, c, 0.0, 7.0, "steel"), (f0, f1, c, c + dw / 2, 0.0, 7.0, "steel"),
                    (g0, g1, c - dw / 2 - 0.25, c + dw / 2 + 0.25, 7.0, 7.4, "chrome"),
                    (g0, g1, c + dw / 2 + 0.5, c + dw / 2 + 0.85, 3.2, 3.9, "chrome"),
                    (g0 - 0.01, g1 + 0.01, c + dw / 2 + 0.6, c + dw / 2 + 0.75, 3.45, 3.6, "light")]
        mesh_from_boxes(f"lift_door_{k}_{int(x0)}_{int(y0)}", door, coll="furniture")
        if k == 0:
            mesh_from_boxes(f"lift_cabin_{int(x0)}_{int(y0)}", lift_cabin(zn, (x0, x1, y0, y1), side),
                            coll="furniture")
    # lamps (emissive panel + area light for the bake) in roofed rooms
    for zn in f["rooms"]:
        if zn["type"] not in INDOOR and zn["type"] not in ("balcony", "parking", "stair"):
            continue
        x0, x1, y0, y1 = furnish.max_rect(zn["rects"]) or max(zn["rects"], key=lambda r: (r[1] - r[0]) * (r[3] - r[2]))
        if (x1 - x0) * (y1 - y0) < 6:
            continue
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if zn["type"] in DOWNLIGHT_ROOMS and min(x1 - x0, y1 - y0) >= 9:
            downlights(x0 + 1, x1 - 1, y0 + 1, y1 - 1)       # recessed lights in a grid (the bake keeps one lamp)
        else:
            ceiling_light(cx, cy, 0.7)
        LAMPS.append((cx, cy, z + H - 0.25, (x1 - x0) * (y1 - y0), zn["type"]))
    by_floor[k] = [o for o in new_objects(before) if not o.get("unbaked")]
    UNBAKED.extend(o for o in new_objects(before) if o.get("unbaked"))
    # walker data (metres): full-height and low walls block, and so do windows (the detector leaves a gap in the
    # wall at every window, so the wall built under a sill is not in f["walls"]); doors and plain openings do not
    F_ = lib.F
    m = lambda r: [round(v * F_, 3) for v in r[:4]]
    sills = [(*o["rect"], 0, 1) for o, c in zip(f["openings"], cuts) if c[4] > 0]
    META_FLOORS.append(dict(
        name=f.get("name", f"Floor {k}"), z=round(z * F_, 3), height=round(H * F_, 3),
        colliders=[m(b) for b in subtract_all([(*w[:4], 0, 1) for w in f["walls"]] + sills,
                                              [(c[0], c[1], c[2], c[3], 0, 1) for c in cuts if c[4] < 1])] + [m(b) for b in guards] + [m(b) for b in closed],
        # solid furniture, for the guided tour's route (web/tour.js) to go round
        furniture=[m(it["box"]) for it in items if it.get("solid", True) and it["box"][1] > it["box"][0]],
        # an upper storey can be walked on only where its slab is; the ground storey everywhere
        **({"floor": [m(b) for b in slab]} if k or BASE else {}),
        # what was built at each opening of the plan, in plan order: glazed with a sill (window), or cut to the
        # floor with a door frame (door / plain opening). tests/test_openings.mjs holds it against plan.json.
        openings=[dict(type=o["type"], built="window" if c[4] > 0 else "doorway", rect=m(o["rect"]),
                       sill=round(max(c[4], 0) * F_, 3), head=round(c[5] * F_, 3)) for o, c in zip(f["openings"], cuts)],
        rooms=[dict(label=zn.get("label") or zn["type"].title(), type=zn["type"], rects=[m(r) for r in zn["rects"]])
               for zn in f["rooms"] if zn["type"] not in ("duct",)],
        stairs=[dict(s, rect=m(s["rect"]), z0=round((z + s["z0"]) * F_, 3), z1=round((z + s["z1"]) * F_, 3),
                     **({"start": round(s["start"] * F_, 3)} if "start" in s else {})) for s in smeta],
        # raised areas one can walk on (a helipad, a stage): their top, in place of the floor under them
        **({"platforms": [dict(rect=m(r), z=round((z + top_) * F_, 3)) for r, top_ in platforms]} if platforms else {}),
    ))
    progress(5 + 25 * (k + 1) / NF, f"built {f.get('name', k)}")

# ------------------------------------------------------------------ roof + parapet + stair cabin (mumty)
top = (NF + BASE) * FFH
set_level(top)
before = set(bpy.data.objects)
bb = bboxes[-1]
holes = [(*r, -9, 99) for zn in floors[-1]["rooms"] if zn["type"] in OPEN_SKY for r in zn["rects"]]
well = [(*r, -9, 99) for r in well_prev]            # the top storey's stairs come up through the roof
mesh_from_boxes("roof", [(*b[:4], -SLAB, 0.0, "terrace") for b in boxes_minus((*bb, -SLAB, 0.0), holes + well)])
t = 0.33
mesh_from_boxes("parapet", [(*b, "exterior") for b in disjoint(subtract_all([      # (none along open courtyards)
    (bb[0], bb[1], bb[2], bb[2] + t, 0, 3.5), (bb[0], bb[1], bb[3] - t, bb[3], 0, 3.5),
    (bb[0], bb[0] + t, bb[2], bb[3], 0, 3.5), (bb[1] - t, bb[1], bb[2], bb[3], 0, 3.5)],
    [(h[0] - t, h[1] + t, h[2] - t, h[3] + t, -9, 99) for h in holes]))])
if stair_box_prev:   # the top storey's stairs reach the roof: a small cabin over them with a door
    x0, x1, y0, y1 = stair_box_prev
    walls_m = disjoint([(x0 - t, x1 + t, y0 - t, y0, 0, 8), (x0 - t, x1 + t, y1, y1 + t, 0, 8),
                        (x0 - t, x0, y0, y1, 0, 8), (x1, x1 + t, y0, y1, 0, 8)])
    cx = (x0 + x1) / 2
    walls_m = subtract_all(walls_m, [(cx - 1.5, cx + 1.5, y1 - 1, y1 + 1, -1, 7)])
    mesh_from_boxes("mumty", [(*b, "exterior") for b in walls_m] + [(x0 - t, x1 + t, y0 - t, y1 + t, 8, 8.5, "slab")])
by_floor[NF] = new_objects(before)

# ------------------------------------------------------------------ site: ground, road, trees, lamps
set_level(0)
before = set(bpy.data.objects)
X0, X1 = min(b[0] for b in bboxes), max(b[1] for b in bboxes)
Y0, Y1 = min(b[2] for b in bboxes), max(b[3] for b in bboxes)
mesh_from_boxes("ground", subtract_all([(X0 - 60, X1 + 60, Y0 - 12, Y1 + 60, -0.65, -0.62, "turf")], WET_GROUND))
mesh_from_boxes("road", [(X0 - 60, X1 + 60, Y0 - 34, Y0 - 12, -0.62, -0.6, "asphalt"),
                         (X0 - 60, X1 + 60, Y0 - 12, Y0 - 6, -0.62, -0.45, "footpath")])
mesh_from_boxes("apron", [(X0 - 0.2, X1 + 0.2, Y0 - 6, Y0 - 0.2, -0.62, -0.58, "pavers")])
site = new_objects(before)
for k, (tx, ty, sz) in enumerate(((X0 - 16, Y0 - 8.5, 1.0), (X1 + 16, Y0 - 8.5, 0.85), (X0 - 20, Y1 - 10, 1.2),
                                  (X1 + 22, Y1 - 4, 1.0), ((X0 + X1) / 2 + 20, Y0 - 40, 1.1), ((X0 + X1) / 2 - 25, Y0 - 42, 0.9))):
    tree(tx, ty, sz, seed=k + 1)
place("street_lamp_01", (X0 + X1) / 2 - 12, Y0 - 9.5, 90, collide=False)
trees = [o for o in new_objects(before) if o not in site] + UNBAKED
progress(32, "lighting")

# ------------------------------------------------------------------ lights + world
world = bpy.data.worlds.new("sky")
scene.world = world
world.use_nodes = True
wn = world.node_tree
env = wn.nodes.new("ShaderNodeTexEnvironment")
env.image = bpy.data.images.load(os.path.join(ASSETS, "hdri", "sky.hdr"))
wn.links.new(env.outputs["Color"], wn.nodes["Background"].inputs["Color"])
wn.nodes["Background"].inputs["Strength"].default_value = 1.0
# evening: the same sky darkened toward deep blue (a multiply node, factor 0 by day)
dusk = wn.nodes.new("ShaderNodeMixRGB")
dusk.blend_type = "MULTIPLY"
dusk.inputs["Fac"].default_value = 0.0
dusk.inputs["Color2"].default_value = (0.32, 0.42, 0.78, 1)
wn.links.new(env.outputs["Color"], dusk.inputs["Color1"])
wn.links.new(dusk.outputs["Color"], wn.nodes["Background"].inputs["Color"])

# the sun from a compass bearing (PLAN3D_SUN_BEARING: 225 = mid-afternoon from the south-west, north of the tropics)
# turned by the drawing's north arrow (floor north_deg, degrees clockwise from up the page; 0 without an arrow)
NORTH = float((floors[0].get("north_deg") if floors else 0) or 0)
SUN_BEARING = float(os.environ.get("PLAN3D_SUN_BEARING", "225") or 225)


def aim_sun(ob, bearing, elevation):
    b, e = math.radians(bearing + NORTH), math.radians(elevation)
    toward = Vector((math.sin(b) * math.cos(e), math.cos(b) * math.cos(e), math.sin(e)))
    ob.rotation_euler = (-toward).to_track_quat("-Z", "Y").to_euler()


sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy = 4.0
sun.data.angle = math.radians(1.5)
aim_sun(sun, SUN_BEARING, 52)
collection("lights").objects.link(sun)
lamps = []
for cx, cy, zz, a, typ in LAMPS:
    L = bpy.data.lights.new("lamp", "AREA")
    L.energy = (14 if typ in INDOOR else 8) * a * lib.F * lib.F
    L.size, L.shape = 0.6, "SQUARE"
    L.color = (1.0, 0.9, 0.78)
    o = bpy.data.objects.new("lamp", L)
    o.location = (cx * lib.F, cy * lib.F, zz * lib.F)
    collection("lights").objects.link(o)
    lamps.append(L)
# exterior lighting for the evening: warm wall-washers on the ground around the house, about every 4 m, off by day
washers = []
for (ax, ay, bx, by, nx, ny) in ((X0, Y0, X1, Y0, 0, -1), (X0, Y1, X1, Y1, 0, 1), (X0, Y0, X0, Y1, -1, 0), (X1, Y0, X1, Y1, 1, 0)):
    length = math.hypot(bx - ax, by - ay) * lib.F
    for k in range(max(1, int(length / 4.0))):
        t = (k + 0.5) / max(1, int(length / 4.0))
        L = bpy.data.lights.new("washer", "SPOT")
        L.energy, L.spot_size, L.spot_blend, L.color = 0.0, math.radians(70), 0.6, (1.0, 0.72, 0.45)
        o = bpy.data.objects.new("washer", L)
        o.location = ((ax + (bx - ax) * t) * lib.F + nx * 0.6, (ay + (by - ay) * t) * lib.F + ny * 0.6, 0.15)
        o.rotation_euler = (Vector((-nx * 0.35, -ny * 0.35, 1.0))).to_track_quat("-Z", "Y").to_euler()
        collection("lights").objects.link(o)
        washers.append(L)


def evening():
    """dusk: a dark blue sky, a low warm sun from the west, lamps up, the wall-washers on"""
    dusk.inputs["Fac"].default_value = 1.0
    wn.nodes["Background"].inputs["Strength"].default_value = 0.18
    sun.data.energy, sun.data.color = 1.2, (1.0, 0.62, 0.38)
    aim_sun(sun, 270, 6)
    for L in lamps:
        L.energy *= 1.4
    for L in washers:
        L.energy = 60.0


def day():
    dusk.inputs["Fac"].default_value = 0.0
    wn.nodes["Background"].inputs["Strength"].default_value = 1.0
    sun.data.energy, sun.data.color = 4.0, (1.0, 1.0, 1.0)
    aim_sun(sun, SUN_BEARING, 52)
    for L in lamps:
        L.energy /= 1.4
    for L in washers:
        L.energy = 0.0

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(JOB, "house.blend"))
progress(35, "model built")

# ------------------------------------------------------------------ bake + export
import bake  # noqa: E402

groups = {f"level_{k}": objs for k, objs in by_floor.items()}
groups["site"] = site
# a second set of light maps for the evening (the walkthrough's Day / Evening switch); PLAN3D_EVENING=0 skips it
EVENING = os.environ.get("PLAN3D_EVENING", "1") != "0"
res = bake.bake_and_export(groups, unbaked=trees, out=JOB, quality=QUALITY, do_bake=BAKE, progress=progress,
                           variants=[("evening", evening, day)] if EVENING else [])
SIZE_ERRORS = [e for z in REPORT["zones"] for e in z.get("errors", [])]
meta = dict(version=1, floors=META_FLOORS, roof_z=round(top * lib.F, 3), eye=1.6, kits=USED_KITS, scheme=SCHEME,
            size_errors=SIZE_ERRORS[:30],
            north_deg=NORTH, sun_bearing=SUN_BEARING,
            bounds=[round(v * lib.F, 3) for v in (X0, X1, Y0, Y1)], **res)
with open(os.path.join(JOB, "meta.json"), "w") as fh:
    json.dump(meta, fh)
with open(os.path.join(JOB, "build_report.json"), "w") as fh:
    json.dump(dict(REPORT, kits=USED_KITS, library_entries=len(LIBRARY)), fh)
progress(100, "done")
print("GEN OK", flush=True)
os._exit(0)
