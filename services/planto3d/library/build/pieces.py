"""Furniture, appliances and fixtures in the house style (style.py), built to a given size in metres.

Convention (the same as PlanTo3D's builders and gen.custom): centred on the origin, standing on z = 0, the front
facing -Y and the back at +Y. Each builder returns its objects. PIECES maps a name (PlanTo3D's catalogue name where
there is one) to (builder, default size (w, d, h), room types it serves, kind)."""
import math

from style import box, disc, lathe, pillow, rod, soft_box, potted_plant, mesh


def _legs(name, w, d, h, M, mat="Walnut", r=0.02, inset=0.06):
    return [rod(f"{name}_leg{k}", (sx * (w / 2 - inset), sy * (d / 2 - inset), 0), (sx * (w / 2 - inset), sy * (d / 2 - inset), h), r, M[mat])
            for k, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)))]


# ------------------------------------------------------------------ living
def sofa(M, w=2.4, d=0.95, h=0.82, fabric="Linen"):
    """a deep three-seat sofa: plinth, seat cushions, back cushions, arms and scatter pillows"""
    o = [box("sofa_plinth", (-w / 2, w / 2), (-d / 2, d / 2), (0.0, 0.12), M["Walnut"], bevel=0.01)]
    arm = 0.16
    o.append(soft_box("sofa_base", (-w / 2, w / 2), (-d / 2, d / 2), (0.12, 0.42), M[fabric], r=0.05))
    n = max(2, round((w - 2 * arm) / 0.75))
    sw = (w - 2 * arm) / n
    for k in range(n):
        x0 = -w / 2 + arm + k * sw
        o.append(soft_box(f"sofa_seat{k}", (x0 + 0.01, x0 + sw - 0.01), (-d / 2 + 0.02, d / 2 - 0.2), (0.42, 0.52), M[fabric], r=0.05))
        o.append(soft_box(f"sofa_back{k}", (x0 + 0.01, x0 + sw - 0.01), (d / 2 - 0.24, d / 2 - 0.02), (0.42, h), M[fabric], r=0.07))
    for s in (-1, 1):
        o.append(soft_box(f"sofa_arm{s}", (s * w / 2 - (arm if s > 0 else 0), s * w / 2 + (0 if s > 0 else arm)), (-d / 2, d / 2), (0.12, 0.64), M[fabric], r=0.05))
    for k, (x, mat) in enumerate(((-w / 2 + 0.45, "Clay"), (w / 2 - 0.45, "Sage"), (-w / 2 + 0.75, "LinenWhite"))):
        o.append(pillow(f"sofa_pillow{k}", (x, d / 2 - 0.3, 0.7), (0.45, 0.14, 0.42), M[mat]))
    return o


def armchair(M, w=0.8, d=0.8, h=0.78):
    """a lounge chair: timber side frame, seat and back cushions (the handover's lounge_chair)"""
    o = []
    for s in (-1, 1):
        o.append(box(f"arm_frame{s}", (s * w / 2 - 0.03, s * w / 2 + 0.03), (-d / 2, d / 2), (0.0, 0.6), M["Oak"], bevel=0.008))
    o.append(soft_box("arm_seat", (-w / 2 + 0.03, w / 2 - 0.03), (-d / 2 + 0.03, d / 2 - 0.08), (0.28, 0.44), M["LinenWhite"], r=0.05))
    o.append(soft_box("arm_back", (-w / 2 + 0.03, w / 2 - 0.03), (d / 2 - 0.2, d / 2), (0.3, h), M["LinenWhite"], r=0.06))
    o.append(pillow("arm_pillow", (0, d / 2 - 0.25, 0.58), (0.38, 0.12, 0.32), M["Clay"]))
    return o


def coffee_table(M, w=1.2, d=0.7, h=0.38):
    o = [box("coffee_top", (-w / 2, w / 2), (-d / 2, d / 2), (h - 0.04, h), M["MarbleWhite"], bevel=0.008),
         box("coffee_base", (-w / 2 + 0.15, w / 2 - 0.15), (-d / 2 + 0.12, d / 2 - 0.12), (0.0, h - 0.04), M["Walnut"], bevel=0.005)]
    o.append(lathe("coffee_bowl", (w * 0.2, 0, h), [(0, 0), (0.06, 0.005), (0.12, 0.05), (0.13, 0.06)], M["Brass"]))
    o += [box(f"coffee_book{k}", (-w * 0.3, -w * 0.3 + 0.24), (-0.12, 0.08), (h + k * 0.03, h + (k + 1) * 0.03), M[m])
          for k, m in enumerate(("Charcoal", "Clay", "LinenWhite"))]
    return o


def side_table(M, w=0.5, d=0.5, h=0.55):
    o = [lathe("side_top", (0, 0, h - 0.03), [(0, 0), (w / 2, 0), (w / 2, 0.03), (0, 0.03)], M["Walnut"]),
         rod("side_stem", (0, 0, 0), (0, 0, h - 0.03), 0.025, M["Brass"]), disc("side_foot", (0, 0, 0.005), w * 0.35, M["Brass"])]
    o += table_lamp(M, at=(0, 0, h))
    return o


def table_lamp(M, at=(0, 0, 0), h=0.5, r=0.16):
    x, y, z = at
    return [lathe("lamp_base", (x, y, z), [(0, 0), (0.07, 0), (0.09, h * 0.35), (0.03, h * 0.6), (0, h * 0.6)], M["Ceramic"]),
            lathe("lamp_shade", (x, y, z + h * 0.55), [(r, 0), (r * 0.75, h * 0.45)], M["Shade"])]


def floor_lamp(M, w=0.45, d=0.45, h=1.6):
    return [disc("flamp_foot", (0, 0, 0.01), 0.16, M["DarkMetal"]), rod("flamp_pole", (0, 0, 0), (0, 0, h - 0.3), 0.012, M["Brass"]),
            lathe("flamp_shade", (0, 0, h - 0.35), [(0.22, 0), (0.16, 0.35)], M["Shade"])]


def tv_unit(M, w=2.0, d=0.45, h=0.5):
    """a low walnut media unit with a black screen above it"""
    o = [box("tv_cab", (-w / 2, w / 2), (-d / 2, d / 2), (0.08, h), M["Walnut"], bevel=0.006),
         box("tv_plinth", (-w / 2 + 0.05, w / 2 - 0.05), (-d / 2 + 0.05, d / 2 - 0.05), (0.0, 0.08), M["DarkMetal"])]
    sw = min(1.65, w * 0.8)
    o.append(box("tv_screen", (-sw / 2, sw / 2), (d / 2 - 0.06, d / 2 - 0.02), (h + 0.35, h + 0.35 + sw * 0.5625), M["CeramicDark"], bevel=0.004))
    return o


def rug(M, w=2.4, d=1.7, h=0.012):
    return [box("rug", (-w / 2, w / 2), (-d / 2, d / 2), (0.0, h), M["Rug"])]


def plant(M, w=0.6, d=0.6, h=1.3, leaves=600):
    return potted_plant("plant", (0, 0, 0), M, h=h, leaves=leaves)


# ------------------------------------------------------------------ dining
def chair(M, x=0.0, y=0.0, rot=0.0, name="chair"):
    """a dining chair, its back toward +Y before turning by rot (radians) about its own centre"""
    w, d = 0.46, 0.5
    o = _legs(name, w, d, 0.45, M, "Walnut", 0.018) + [
        soft_box(f"{name}_seat", (-w / 2, w / 2), (-d / 2, d / 2), (0.43, 0.5), M["Linen"], r=0.03),
        box(f"{name}_back", (-w / 2 + 0.02, w / 2 - 0.02), (d / 2 - 0.04, d / 2), (0.5, 0.9), M["Walnut"], bevel=0.008)]
    for ob in o:          # built round the origin: turn the mesh there, then move it into place
        _turn(ob, 0.0, 0.0, rot)
        ob.location = (x, y, 0.0)
    return o


def _turn(ob, cx, cy, rot):
    """turn an object (whose mesh is in world coordinates) by rot about (cx, cy)"""
    if not rot:
        return
    c, s = math.cos(rot), math.sin(rot)
    for v in ob.data.vertices:
        x, y = v.co.x - cx, v.co.y - cy
        v.co.x, v.co.y = cx + c * x - s * y, cy + s * x + c * y


def dining_set(M, w=2.2, d=1.9, h=0.75):
    """a table for 6 to 10 (by length) with chairs on both long sides and at the ends when it is long enough"""
    tl, td = max(1.4, w - 0.9), max(0.85, min(1.1, d - 0.95))
    o = [box("dining_top", (-tl / 2, tl / 2), (-td / 2, td / 2), (h - 0.04, h), M["Oak"], bevel=0.008)]
    o += _legs("dining", tl, td, h - 0.04, M, "Walnut", 0.03, 0.12)
    per = max(2, int(tl // 0.62))
    for k in range(per):
        x = -tl / 2 + (k + 0.5) * tl / per
        o += chair(M, x, -td / 2 - 0.12, math.pi, f"chair_s{k}") + chair(M, x, td / 2 + 0.12, 0.0, f"chair_n{k}")
    if per >= 4:
        o += chair(M, -tl / 2 - 0.12, 0, math.pi / 2, "chair_w") + chair(M, tl / 2 + 0.12, 0, -math.pi / 2, "chair_e")
    return o


def sideboard(M, w=1.8, d=0.45, h=0.8):
    o = [box("sb_body", (-w / 2, w / 2), (-d / 2, d / 2), (0.12, h), M["Walnut"], bevel=0.006)]
    o += _legs("sb", w, d, 0.12, M, "Brass", 0.012, 0.08)
    o.append(lathe("sb_vase", (w * 0.25, 0, h), [(0, 0), (0.07, 0), (0.1, 0.18), (0.04, 0.36), (0, 0.36)], M["Ceramic"]))
    return o


def pendant_cluster(M, w=1.6, d=0.4, h=3.0, n=3, drop=1.1):
    """cone pendants over a table (the handover's brass cones with a bulb inside); h = ceiling height"""
    o = []
    for k in range(n):
        x = -w / 2 + (k + 0.5) * w / n
        o += [rod(f"pend_cord{k}", (x, 0, h - drop + 0.3), (x, 0, h), 0.004, M["DarkMetal"]),
              lathe(f"pend_cone{k}", (x, 0, h - drop), [(0.18, 0), (0.14, 0.12), (0.03, 0.3)], M["Brass"]),
              lathe(f"pend_bulb{k}", (x, 0, h - drop + 0.02), [(0, 0), (0.045, 0.03), (0.04, 0.08), (0, 0.1)], M["Bulb"])]
    return o


# ------------------------------------------------------------------ bedroom
def bed(M, w=1.8, d=2.1, h=1.1, fabric="LinenWhite"):
    """a low bed with an upholstered headboard against the wall (+Y), linen, pillows and a throw"""
    o = [box("bed_frame", (-w / 2, w / 2), (-d / 2, d / 2 - 0.08), (0.0, 0.3), M["Walnut"], bevel=0.01),
         soft_box("bed_mattress", (-w / 2 + 0.03, w / 2 - 0.03), (-d / 2 + 0.03, d / 2 - 0.1), (0.3, 0.52), M[fabric], r=0.06),
         soft_box("bed_head", (-w / 2 - 0.05, w / 2 + 0.05), (d / 2 - 0.1, d / 2), (0.0, h), M["Leather"], r=0.03),
         soft_box("bed_throw", (-w / 2 + 0.01, w / 2 - 0.01), (-d / 2 + 0.02, -d / 2 + 0.6), (0.5, 0.56), M["Clay"], r=0.03)]
    for k, x in enumerate((-w / 4, w / 4)):
        o.append(pillow(f"bed_pillow{k}", (x, d / 2 - 0.35, 0.62), (w / 2 - 0.12, 0.3, 0.16), M["LinenWhite"]))
    return o


def nightstand(M, w=0.5, d=0.42, h=0.5):
    o = [box("ns_body", (-w / 2, w / 2), (-d / 2, d / 2), (0.08, h), M["Walnut"], bevel=0.005)]
    o += _legs("ns", w, d, 0.08, M, "Brass", 0.01, 0.05) + table_lamp(M, (0, 0.05, h), 0.42, 0.13)
    return o


def wardrobe(M, w=1.8, d=0.6, h=2.4):
    """full-height wardrobe: oak doors with slim brass pulls"""
    o = [box("wr_body", (-w / 2, w / 2), (-d / 2, d / 2), (0.0, h), M["Oak"], bevel=0.004)]
    n = max(2, round(w / 0.5))
    for k in range(1, n):
        x = -w / 2 + k * w / n
        o.append(box(f"wr_gap{k}", (x - 0.003, x + 0.003), (-d / 2 - 0.004, -d / 2 + 0.01), (0.05, h - 0.05), M["DarkMetal"]))
        o.append(rod(f"wr_pull{k}", (x - 0.03, -d / 2 - 0.03, h * 0.4), (x - 0.03, -d / 2 - 0.03, h * 0.6), 0.008, M["Brass"]))
    return o


def dresser(M, w=1.2, d=0.45, h=0.8):
    o = [box("dr_body", (-w / 2, w / 2), (-d / 2, d / 2), (0.1, h), M["Oak"], bevel=0.005)] + _legs("dr", w, d, 0.1, M, "Walnut", 0.015, 0.05)
    o.append(box("dr_mirror", (-w * 0.3, w * 0.3), (d / 2 - 0.02, d / 2), (h + 0.1, h + 0.9), M["Mirror"]))
    return o


def desk(M, w=1.4, d=0.65, h=0.75):
    o = [box("desk_top", (-w / 2, w / 2), (-d / 2, d / 2), (h - 0.03, h), M["Oak"], bevel=0.004)] + _legs("desk", w, d, h - 0.03, M, "DarkMetal", 0.015, 0.04)
    o += chair(M, 0, -d / 2 - 0.2, math.pi, "desk_chair") + table_lamp(M, (w / 2 - 0.2, d / 4, h), 0.4, 0.12)
    return o


# ------------------------------------------------------------------ bathroom
def wc2(M, w=0.4, d=0.65, h=0.8):
    return [lathe("wc_bowl", (0, -0.08, 0), [(0.16, 0), (0.19, 0.25), (0.2, 0.4), (0.0, 0.4)], M["Ceramic"]),
            box("wc_cistern", (-0.19, 0.19), (d / 2 - 0.18, d / 2), (0.0, h), M["Ceramic"], bevel=0.02),
            box("wc_seat", (-0.19, 0.19), (-0.3, 0.12), (0.4, 0.42), M["WhiteLacquer"], bevel=0.01)]


def vanity(M, w=1.0, d=0.5, h=0.85):
    """a floating walnut vanity with a stone top, a basin, a brass tap and a mirror with a glowing ring"""
    o = [box("van_cab", (-w / 2, w / 2), (-d / 2, d / 2), (0.35, h - 0.03), M["Walnut"], bevel=0.005),
         box("van_top", (-w / 2, w / 2), (-d / 2, d / 2), (h - 0.03, h), M["MarbleCream"], bevel=0.004),
         lathe("van_basin", (0, -0.02, h), [(0.0, 0.0), (0.16, 0.0), (0.2, 0.12), (0.21, 0.13)], M["Ceramic"]),
         rod("van_tap", (0, d / 2 - 0.08, h), (0, d / 2 - 0.08, h + 0.25), 0.012, M["Brass"]),
         rod("van_spout", (0, d / 2 - 0.08, h + 0.25), (0, d / 2 - 0.2, h + 0.25), 0.01, M["Brass"])]
    o += [lathe("van_mirror", (0, 0, 0), [(0, 0), (0.33, 0), (0.33, 0.01), (0, 0.01)], M["Mirror"], segs=48),
          lathe("van_ring", (0, 0, 0), [(0.33, 0), (0.35, 0), (0.35, 0.008), (0.33, 0.008)], M["MirrorRing"], segs=48)]
    for ob in o[-2:]:
        ob.rotation_euler = (math.pi / 2, 0, 0)
        ob.location = (0, d / 2, h + 0.8)
    return o


def shower2(M, w=1.0, d=1.0, h=2.1):
    """a walk-in shower: stone tray, a fluted glass screen on the open side, a brass rain head"""
    return [box("sh_tray", (-w / 2, w / 2), (-d / 2, d / 2), (0.0, 0.04), M["MarbleCream"]),
            box("sh_glass", (-w / 2, w / 2 - 0.3), (-d / 2, -d / 2 + 0.01), (0.04, h), M["FlutedGlass"]),
            box("sh_glass_frame", (-w / 2, w / 2 - 0.3), (-d / 2 - 0.005, -d / 2 + 0.015), (h - 0.02, h), M["Brass"]),
            rod("sh_arm", (0, d / 2, h + 0.1), (0, d / 2 - 0.3, h + 0.1), 0.012, M["Brass"]),
            disc("sh_head", (0, d / 2 - 0.3, h + 0.08), 0.12, M["Brass"])]


def bathtub(M, w=1.7, d=0.8, h=0.6):
    """a freestanding oval stone tub (super-ellipse) with a floor-standing brass filler"""
    verts, faces = [], []
    seg, rings = 48, [(1.0, 0.0), (1.0, h), (0.88, h), (0.86, 0.12)]
    for i in range(seg):
        a = 2 * math.pi * i / seg
        cx, cy = math.copysign(abs(math.cos(a)) ** 0.6, math.cos(a)), math.copysign(abs(math.sin(a)) ** 0.6, math.sin(a))
        for k, (s, z) in enumerate(rings):
            verts.append((cx * w / 2 * s, cy * d / 2 * s, z))
    n = len(rings)
    for i in range(seg):
        j = (i + 1) % seg
        for k in range(n - 1):
            faces.append((i * n + k, j * n + k, j * n + k + 1, i * n + k + 1))
    faces.append(tuple(i * n + n - 1 for i in range(seg))[::-1])
    return [mesh("tub", verts, faces, M["Ceramic"], True), rod("tub_filler", (w / 2 + 0.15, 0, 0), (w / 2 + 0.15, 0, 0.95), 0.015, M["Brass"]),
            rod("tub_spout", (w / 2 + 0.15, 0, 0.95), (w / 2 - 0.05, 0, 0.95), 0.012, M["Brass"])]


def towel_rail(M, w=0.6, d=0.1, h=1.2):
    o = [rod(f"tr_bar{k}", (-w / 2, 0, 0.6 + 0.15 * k), (w / 2, 0, 0.6 + 0.15 * k), 0.01, M["Brass"]) for k in range(4)]
    o += [rod(f"tr_post{s}", (s * w / 2, 0, 0.55), (s * w / 2, 0, h), 0.012, M["Brass"]) for s in (-1, 1)]
    o.append(box("tr_towel", (-w / 2 + 0.05, w / 2 - 0.05), (-0.02, 0.02), (0.65, 1.05), M["Towel"]))
    return o


# ------------------------------------------------------------------ kitchen and laundry appliances
def fridge2(M, w=0.9, d=0.72, h=1.85):
    return [box("fr_body", (-w / 2, w / 2), (-d / 2, d / 2), (0.0, h), M["Chrome"], bevel=0.01),
            box("fr_split", (-0.003, 0.003), (-d / 2 - 0.004, -d / 2 + 0.01), (0.65, h - 0.02), M["DarkMetal"]),
            rod("fr_h1", (-0.05, -d / 2 - 0.04, 0.9), (-0.05, -d / 2 - 0.04, 1.5), 0.012, M["DarkMetal"]),
            rod("fr_h2", (0.05, -d / 2 - 0.04, 0.9), (0.05, -d / 2 - 0.04, 1.5), 0.012, M["DarkMetal"])]


def oven_tower(M, w=0.6, d=0.6, h=2.2):
    """a tall cabinet with a built-in oven and a microwave above it"""
    return [box("ov_cab", (-w / 2, w / 2), (-d / 2, d / 2), (0.0, h), M["Oak"], bevel=0.004),
            box("ov_oven", (-w / 2 + 0.02, w / 2 - 0.02), (-d / 2 - 0.01, -d / 2 + 0.02), (0.75, 1.35), M["DarkMetal"]),
            box("ov_glass", (-w / 2 + 0.06, w / 2 - 0.06), (-d / 2 - 0.015, -d / 2), (0.8, 1.2), M["CeramicDark"]),
            box("ov_micro", (-w / 2 + 0.02, w / 2 - 0.02), (-d / 2 - 0.01, -d / 2 + 0.02), (1.42, 1.8), M["DarkMetal"])]


def dishwasher(M, w=0.6, d=0.6, h=0.85):
    return [box("dw_body", (-w / 2, w / 2), (-d / 2, d / 2), (0.0, h), M["Chrome"], bevel=0.004),
            rod("dw_handle", (-w / 2 + 0.06, -d / 2 - 0.03, h - 0.08), (w / 2 - 0.06, -d / 2 - 0.03, h - 0.08), 0.01, M["DarkMetal"])]


def coffee_machine(M, w=0.32, d=0.4, h=0.42):
    return [box("cm_body", (-w / 2, w / 2), (-d / 2, d / 2), (0.0, h), M["DarkMetal"], bevel=0.02),
            box("cm_front", (-w / 2 + 0.04, w / 2 - 0.04), (-d / 2 - 0.01, -d / 2 + 0.01), (0.12, 0.3), M["Chrome"]),
            lathe("cm_cup", (0, -d / 2 + 0.08, 0.03), [(0, 0), (0.035, 0), (0.04, 0.07), (0, 0.07)], M["Ceramic"])]


def washer2(M, w=0.6, d=0.6, h=0.85, name="wm"):
    return [box(f"{name}_body", (-w / 2, w / 2), (-d / 2, d / 2), (0.0, h), M["WhiteLacquer"], bevel=0.015),
            lathe(f"{name}_door", (0, -d / 2 - 0.02, 0.42), [(0.0, 0), (0.2, 0), (0.2, 0.03), (0.0, 0.03)], M["Chrome"])]


def dryer(M, w=0.6, d=0.6, h=0.85):
    return washer2(M, w, d, h, "dry")


# ------------------------------------------------------------------ puja, prayer, majlis
def puja_mandir(M, w=1.1, d=0.45, h=2.0):
    """a white marble mandir: a stepped base, two shelves for idols, a canopy (shikhara) with a warm glow, brass diyas,
    a bell and an aarti thali. Kept calm: no decorative clutter beyond the ritual objects"""
    o = [box("mandir_base", (-w / 2, w / 2), (-d / 2, d / 2), (0.0, 0.45), M["MarbleWhite"], bevel=0.01),
         box("mandir_step", (-w / 2 + 0.08, w / 2 - 0.08), (-d / 2 - 0.1, -d / 2), (0.0, 0.18), M["MarbleWhite"], bevel=0.01),
         box("mandir_back", (-w / 2, w / 2), (d / 2 - 0.05, d / 2), (0.45, h * 0.82), M["MarbleWhite"]),
         box("mandir_shelf", (-w / 2 + 0.05, w / 2 - 0.05), (-d / 2 + 0.05, d / 2), (0.98, 1.02), M["MarbleWhite"], bevel=0.005)]
    for s in (-1, 1):
        o.append(box(f"mandir_pillar{s}", (s * w / 2 - 0.06 * (s > 0), s * w / 2 + 0.06 * (s < 0)), (-d / 2, -d / 2 + 0.08), (0.45, h * 0.82), M["MarbleWhite"], bevel=0.005))
    o.append(lathe("mandir_shikhara", (0, 0, h * 0.82), [(w / 2, 0), (w * 0.38, h * 0.08), (w * 0.12, h * 0.16), (0.02, h * 0.18), (0, h * 0.18)], M["MarbleWhite"], segs=8))
    o.append(box("mandir_glow", (-w / 2 + 0.08, w / 2 - 0.08), (d / 2 - 0.06, d / 2 - 0.05), (1.05, h * 0.78), M["Lantern"]))
    for k, x in enumerate((-w * 0.3, w * 0.3)):
        o.append(lathe(f"diya{k}", (x, -d / 2 + 0.12, 0.45), [(0, 0), (0.035, 0.0), (0.045, 0.02), (0.0, 0.025)], M["Brass"]))
        o.append(lathe(f"diya_flame{k}", (x, -d / 2 + 0.12, 0.47), [(0, 0), (0.008, 0.01), (0, 0.035)], M["Bulb"]))
    o.append(lathe("thali", (0, -d / 2 + 0.14, 0.45), [(0, 0), (0.13, 0), (0.15, 0.015)], M["Brass"]))
    o.append(lathe("bell", (w * 0.38, 0, 1.02), [(0, 0.12), (0.03, 0.1), (0.05, 0.0), (0.0, 0.0)], M["Brass"]))
    return o


def puja_mat(M, w=1.2, d=0.8, h=0.01):
    return [box("puja_mat", (-w / 2, w / 2), (-d / 2, d / 2), (0.0, h), M["Clay"])]


def prayer_rug(M, w=0.7, d=1.2, h=0.01):
    """a prayer rug, its head toward +Y (the builder turns +Y to face the qibla)"""
    return [box("pr_rug", (-w / 2, w / 2), (-d / 2, d / 2), (0.0, h), M["Rug"]),
            box("pr_band", (-w / 2 + 0.06, w / 2 - 0.06), (d / 2 - 0.3, d / 2 - 0.22), (h, h + 0.002), M["Clay"])]


def prayer_niche(M, w=0.9, d=0.12, h=2.1):
    """a mihrab niche set into the qibla wall (+Y): a pointed arch outline in stone with a soft light inside"""
    o = [box("niche_back", (-w / 2, w / 2), (d / 2 - 0.02, d / 2), (0.0, h * 0.8), M["LimestoneBeige"])]
    for s in (-1, 1):
        o.append(box(f"niche_jamb{s}", (s * w / 2 - 0.08 * (s > 0), s * w / 2 + 0.08 * (s < 0)), (-d / 2, d / 2), (0.0, h * 0.75), M["Limestone"]))
    o.append(lathe("niche_arch", (0, 0, h * 0.75), [(w / 2, 0), (w * 0.3, h * 0.12), (0.02, h * 0.2), (0, h * 0.2)], M["Limestone"], segs=4))
    o.append(box("niche_light", (-w / 2 + 0.1, w / 2 - 0.1), (d / 2 - 0.03, d / 2 - 0.02), (h * 0.7, h * 0.72), M["CoveSoft"]))
    return o


def quran_stand(M, w=0.45, d=0.32, h=0.3):
    """a rehal: two crossed wooden boards"""
    o = []
    for s in (-1, 1):
        ob = box(f"rehal{s}", (-w / 2, w / 2), (-0.005, 0.005), (0.0, h), M["Walnut"], bevel=0.004)
        ob.rotation_euler = (s * 0.5, 0, 0)
        o.append(ob)
    return o


def majlis_seat(M, w=3.0, d=0.8, h=0.75):
    """low floor seating along a wall: a firm base cushion, back cushions and armrest bolsters (+Y is the wall)"""
    o = [soft_box("mj_base", (-w / 2, w / 2), (-d / 2, d / 2), (0.0, 0.2), M["Velvet"], r=0.04),
         box("mj_trim", (-w / 2, w / 2), (-d / 2 - 0.005, -d / 2 + 0.01), (0.04, 0.16), M["Brass"])]
    n = max(1, round(w / 0.7))
    for k in range(n):
        x = -w / 2 + (k + 0.5) * w / n
        o.append(pillow(f"mj_back{k}", (x, d / 2 - 0.12, 0.45), (w / n - 0.04, 0.2, 0.5), M["Velvet"]))
    o += [pillow(f"mj_bolster{s}", (s * (w / 2 - 0.12), 0, 0.3), (0.2, d - 0.1, 0.2), M["Clay"]) for s in (-1, 1)]
    return o


def incense_burner(M, w=0.25, d=0.25, h=0.35):
    return [lathe("bakhoor", (0, 0, 0), [(0.08, 0), (0.05, 0.08), (0.06, 0.16), (0.1, 0.22), (0.11, 0.26), (0.0, 0.26)], M["Brass"]),
            lathe("bakhoor_lid", (0, 0, 0.26), [(0.1, 0), (0.05, 0.06), (0.01, 0.09), (0, 0.09)], M["Brass"])]


def chandelier(M, w=0.9, d=0.9, h=3.0, drop=0.9):
    """a ring chandelier of glowing globes; h = ceiling height"""
    o = [rod("ch_rod", (0, 0, h - drop), (0, 0, h), 0.01, M["Brass"]),
         lathe("ch_ring", (0, 0, h - drop), [(w / 2 - 0.02, 0), (w / 2, 0), (w / 2, 0.02), (w / 2 - 0.02, 0.02)], M["Brass"])]
    for k in range(8):
        a = 2 * math.pi * k / 8
        o.append(lathe(f"ch_globe{k}", (w / 2 * math.cos(a), w / 2 * math.sin(a), h - drop + 0.02),
                       [(0, 0), (0.06, 0.03), (0.07, 0.08), (0.04, 0.13), (0, 0.14)], M["Bulb"]))
    return o


# ------------------------------------------------------------------ foyer, study, gym, cinema, outdoor
def console(M, w=1.4, d=0.38, h=0.8):
    o = [box("con_top", (-w / 2, w / 2), (-d / 2, d / 2), (h - 0.04, h), M["MarbleVeined"], bevel=0.004)] + _legs("con", w, d, h - 0.04, M, "Brass", 0.012, 0.03)
    o.append(lathe("con_mirror", (0, 0, 0), [(0, 0), (0.45, 0), (0.45, 0.01), (0, 0.01)], M["Mirror"], segs=48))
    o[-1].rotation_euler = (math.pi / 2, 0, 0)
    o[-1].location = (0, d / 2, h + 0.7)
    return o


def shoe_cabinet(M, w=1.2, d=0.38, h=1.0):
    return [box("shoe_cab", (-w / 2, w / 2), (-d / 2, d / 2), (0.1, h), M["WhiteLacquer"], bevel=0.004)] + _legs("shoe", w, d, 0.1, M, "Brass", 0.01, 0.04)


def bookshelf(M, w=1.6, d=0.35, h=2.2):
    o = [box("bs_side0", (-w / 2, -w / 2 + 0.03), (-d / 2, d / 2), (0, h), M["Walnut"]), box("bs_side1", (w / 2 - 0.03, w / 2), (-d / 2, d / 2), (0, h), M["Walnut"])]
    for k in range(6):
        z = 0.05 + k * (h - 0.1) / 5
        o.append(box(f"bs_shelf{k}", (-w / 2, w / 2), (-d / 2, d / 2), (z, z + 0.03), M["Walnut"]))
        if k < 5:
            o.append(box(f"bs_books{k}", (-w / 2 + 0.08, w / 2 * 0.3), (-d / 2 + 0.05, d / 2 - 0.05), (z + 0.03, z + 0.3), M[("Clay", "Sage", "Charcoal", "Linen", "LinenWhite")[k]]))
    return o


def treadmill(M, w=0.85, d=1.9, h=1.4):
    return [box("tm_deck", (-w / 2, w / 2), (-d / 2, d / 2), (0.05, 0.22), M["Charcoal"], bevel=0.02),
            rod("tm_post0", (-w / 2 + 0.05, -d / 2 + 0.2, 0.2), (-w / 2 + 0.05, -d / 2 + 0.3, h), 0.025, M["DarkMetal"]),
            rod("tm_post1", (w / 2 - 0.05, -d / 2 + 0.2, 0.2), (w / 2 - 0.05, -d / 2 + 0.3, h), 0.025, M["DarkMetal"]),
            box("tm_console", (-w / 2, w / 2), (-d / 2 + 0.2, -d / 2 + 0.45), (h - 0.05, h + 0.05), M["DarkMetal"], bevel=0.01)]


def weight_bench(M, w=0.5, d=1.3, h=0.45):
    return [soft_box("wb_pad", (-w / 2 + 0.1, w / 2 - 0.1), (-d / 2, d / 2), (h - 0.08, h), M["Leather"], r=0.03)] + _legs("wb", w - 0.2, d, h - 0.08, M, "DarkMetal", 0.02, 0.05)


def cinema_seats(M, w=3.6, d=2.4, h=1.0, rows=2):
    """tiered rows of reclining seats (each row 1.2 m deep, the back row on a 0.3 m riser)"""
    o = []
    for r in range(rows):
        y0 = -d / 2 + r * d / rows
        z0 = 0.3 * r
        if r:
            o.append(box(f"cin_riser{r}", (-w / 2, w / 2), (y0, y0 + d / rows), (0.0, z0), M["Charcoal"]))
        n = max(1, int(w // 0.9))
        for k in range(n):
            x = -w / 2 + (k + 0.5) * w / n
            o.append(soft_box(f"cin_seat{r}_{k}", (x - 0.38, x + 0.38), (y0 + 0.1, y0 + 0.9), (z0, z0 + 0.45), M["Leather"], r=0.05))
            o.append(soft_box(f"cin_back{r}_{k}", (x - 0.38, x + 0.38), (y0 + 0.75, y0 + 0.95), (z0 + 0.3, z0 + h), M["Leather"], r=0.05))
    return o


def lounger(M, w=0.7, d=2.0, h=0.45):
    o = [box("lo_frame", (-w / 2, w / 2), (-d / 2, d / 2), (0.15, 0.3), M["Oak"], bevel=0.01),
         soft_box("lo_pad", (-w / 2 + 0.03, w / 2 - 0.03), (-d / 2 + 0.03, d / 2 - 0.6), (0.3, 0.38), M["LinenWhite"], r=0.03)]
    back = soft_box("lo_back", (-w / 2 + 0.03, w / 2 - 0.03), (d / 2 - 0.62, d / 2 - 0.02), (0.3, 0.38), M["LinenWhite"], r=0.03)
    back.rotation_euler = (0.6, 0, 0)
    return o + [back] + _legs("lo", w, d, 0.15, M, "Oak", 0.02, 0.05)


def outdoor_sofa(M, w=2.0, d=0.85, h=0.7):
    return sofa(M, w, d, h, "LinenWhite")


def planter(M, w=0.8, d=0.8, h=1.4, leaves=700):
    o = potted_plant("planter", (0, 0, 0), M, h=h, leaves=leaves)
    return o


PIECES = {
    # name: (builder, default size w, d, h in metres, room types, kind)
    "sofa": (sofa, (2.4, 0.95, 0.82), ("living", "cinema"), "furniture"),
    "armchair": (armchair, (0.8, 0.8, 0.78), ("living", "bedroom", "study"), "furniture"),
    "coffee_table": (coffee_table, (1.2, 0.7, 0.38), ("living",), "furniture"),
    "side_table": (side_table, (0.5, 0.5, 0.55), ("living", "bedroom"), "furniture"),
    "floor_lamp": (floor_lamp, (0.45, 0.45, 1.6), ("living", "bedroom", "study"), "lighting"),
    "tv_unit": (tv_unit, (2.0, 0.45, 0.5), ("living", "bedroom"), "furniture"),
    "rug": (rug, (2.4, 1.7, 0.012), ("living", "bedroom", "dining", "majlis"), "furniture"),
    "plant": (plant, (0.6, 0.6, 1.3), ("living", "foyer", "dining", "bedroom", "balcony", "garden"), "furniture"),
    "dining_set": (dining_set, (2.2, 1.9, 0.75), ("dining",), "furniture"),
    "sideboard": (sideboard, (1.8, 0.45, 0.8), ("dining", "living"), "furniture"),
    "pendant_cluster": (pendant_cluster, (1.6, 0.4, 3.0), ("dining", "kitchen"), "lighting"),
    "bed": (bed, (1.8, 2.1, 1.1), ("bedroom",), "furniture"),
    "nightstand": (nightstand, (0.5, 0.42, 0.5), ("bedroom",), "furniture"),
    "wardrobe": (wardrobe, (1.8, 0.6, 2.4), ("bedroom", "dress"), "furniture"),
    "dresser": (dresser, (1.2, 0.45, 0.8), ("bedroom", "dress"), "furniture"),
    "desk": (desk, (1.4, 0.65, 0.75), ("study", "bedroom"), "furniture"),
    "wc2": (wc2, (0.4, 0.65, 0.8), ("toilet",), "fixture"),
    "vanity": (vanity, (1.0, 0.5, 0.85), ("toilet",), "fixture"),
    "shower2": (shower2, (1.0, 1.0, 2.1), ("toilet",), "fixture"),
    "bathtub": (bathtub, (1.7, 0.8, 0.6), ("toilet",), "fixture"),
    "towel_rail": (towel_rail, (0.6, 0.1, 1.2), ("toilet",), "fixture"),
    "fridge2": (fridge2, (0.9, 0.72, 1.85), ("kitchen",), "appliance"),
    "oven_tower": (oven_tower, (0.6, 0.6, 2.2), ("kitchen",), "appliance"),
    "dishwasher": (dishwasher, (0.6, 0.6, 0.85), ("kitchen",), "appliance"),
    "coffee_machine": (coffee_machine, (0.32, 0.4, 0.42), ("kitchen",), "appliance"),
    "washer2": (washer2, (0.6, 0.6, 0.85), ("wash",), "appliance"),
    "dryer": (dryer, (0.6, 0.6, 0.85), ("wash",), "appliance"),
    "puja_mandir": (puja_mandir, (1.1, 0.45, 2.0), ("puja",), "furniture"),
    "puja_mat": (puja_mat, (1.2, 0.8, 0.01), ("puja",), "furniture"),
    "prayer_rug": (prayer_rug, (0.7, 1.2, 0.01), ("prayer",), "furniture"),
    "prayer_niche": (prayer_niche, (0.9, 0.12, 2.1), ("prayer",), "fixture"),
    "quran_stand": (quran_stand, (0.45, 0.32, 0.3), ("prayer",), "furniture"),
    "majlis_seat": (majlis_seat, (3.0, 0.8, 0.75), ("majlis",), "furniture"),
    "incense_burner": (incense_burner, (0.25, 0.25, 0.35), ("majlis",), "furniture"),
    "chandelier": (chandelier, (0.9, 0.9, 3.0), ("majlis", "foyer", "dining"), "lighting"),
    "console": (console, (1.4, 0.38, 0.8), ("foyer",), "furniture"),
    "shoe_cabinet": (shoe_cabinet, (1.2, 0.38, 1.0), ("foyer",), "furniture"),
    "bookshelf": (bookshelf, (1.6, 0.35, 2.2), ("study", "living"), "furniture"),
    "treadmill": (treadmill, (0.85, 1.9, 1.4), ("gym",), "furniture"),
    "weight_bench": (weight_bench, (0.5, 1.3, 0.45), ("gym",), "furniture"),
    "cinema_seats": (cinema_seats, (3.6, 2.4, 1.0), ("cinema",), "furniture"),
    "lounger": (lounger, (0.7, 2.0, 0.45), ("pool", "garden", "balcony"), "furniture"),
    "outdoor_sofa": (outdoor_sofa, (2.0, 0.85, 0.7), ("balcony", "garden"), "furniture"),
    "planter": (planter, (0.8, 0.8, 1.4), ("garden", "balcony", "foyer"), "furniture"),
}
