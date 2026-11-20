"""Blender building blocks used by gen.py: materials, box meshes, furniture and fixtures (units: feet).
Textures and models come from ../assets (python3 fetch_assets.py)."""
import bpy, bmesh, json, math, os, sys
import numpy as np
import random
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))

ASSETS = os.path.join(os.path.dirname(HERE), "assets")
F = 0.3048  # feet -> metres
WALL_H = 10.0   # floor-to-ceiling, feet
LEVEL = 0.0     # z of the floor being furnished (feet); set with set_level() for upper storeys


def set_level(z):
    global LEVEL
    LEVEL = z

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"

# ---------------------------------------------------------------- materials
MATS = {}


def tex_node(nt, path, non_color=False):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = bpy.data.images.load(path, check_existing=True)
    if non_color:
        n.image.colorspace_settings.name = "Non-Color"
    return n


def _grey(img):
    """the photo's weave and shading without its colour (mean brightness 0.8), so a tint can set any colour"""
    if img.name + "_grey" in bpy.data.images:       # one copy per photo, however many colours use it
        return bpy.data.images[img.name + "_grey"]
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    lum = px[:, :3] @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    lum = np.clip(lum * (0.8 / max(float(lum.mean()), 1e-3)), 0, 1)
    out = bpy.data.images.new(img.name + "_grey", w, h)
    rgba = np.ones((w * h, 4), np.float32)
    rgba[:, :3] = lum[:, None]
    out.pixels.foreach_set(rgba.ravel())
    out.pack()
    return out


def _brushed():
    """brushed stainless steel: fine streaks along u (no such photo on Poly Haven)"""
    rnd = np.random.default_rng(7)
    n = 512
    rows = rnd.normal(0, 1, (n, 1)) * 0.035 + rnd.normal(0, 1, (n, n)) * 0.012
    k = np.ones(48, np.float32) / 48            # smear the speckle along u into streaks
    rows = np.array([np.convolve(np.tile(r, 2), k, "same")[n // 2:n // 2 + n] for r in rows])
    v = np.clip(0.72 + rows, 0, 1).astype(np.float32)
    img = bpy.data.images.new("brushed_steel", n, n)
    img.pixels.foreach_set(np.stack([v, v, v * 1.01, np.ones_like(v)], -1).clip(0, 1).ravel())
    img.pack()
    return img


def mat(name, color=(0.8, 0.8, 0.8), rough=0.5, metal=0.0, tex=None, tile=1.0, alpha=1.0,
        emit=0.0, tint=None, albedo=True, grey=False, image=None):
    """tile = metres covered by one texture repeat (UVs are written in metres / tile).
    grey: drop the photo's own colour so tint is the colour; image: a generated image as the albedo."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if tex:
        d = os.path.join(ASSETS, "textures", tex)
        if albedo and os.path.exists(os.path.join(d, "diff.jpg")):   # albedo=False: bump only (smooth paint)
            t = tex_node(nt, os.path.join(d, "diff.jpg"))
            if grey:
                t.image = _grey(t.image)
            if tint:  # multiply albedo by a tint colour
                mix = nt.nodes.new("ShaderNodeMix")
                mix.data_type = "RGBA"
                mix.blend_type = "MULTIPLY"
                mix.inputs["Factor"].default_value = 1.0
                nt.links.new(t.outputs["Color"], mix.inputs[6])
                mix.inputs[7].default_value = (*tint, 1)
                nt.links.new(mix.outputs[2], p.inputs["Base Color"])
            else:
                nt.links.new(t.outputs["Color"], p.inputs["Base Color"])
        if os.path.exists(os.path.join(d, "rough.jpg")):
            r = tex_node(nt, os.path.join(d, "rough.jpg"), True)
            nt.links.new(r.outputs["Color"], p.inputs["Roughness"])
        if os.path.exists(os.path.join(d, "nor.jpg")):
            n = tex_node(nt, os.path.join(d, "nor.jpg"), True)
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nt.links.new(n.outputs["Color"], nm.inputs["Color"])
            nt.links.new(nm.outputs["Normal"], p.inputs["Normal"])
    if image:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = image
        nt.links.new(t.outputs["Color"], p.inputs["Base Color"])
    if alpha < 1:
        p.inputs["Alpha"].default_value = alpha
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "BLENDED"
        if hasattr(m, "blend_method"):
            try:
                m.blend_method = "BLEND"
            except Exception:
                pass
    if emit:
        p.inputs["Emission Color"].default_value = (*color, 1)
        p.inputs["Emission Strength"].default_value = emit
    m["tile"] = tile
    MATS[name] = m
    return m


mat("wall", (0.86, 0.80, 0.70), 0.9, tex="white_plaster_02", tile=1.5, albedo=False)   # warm off-white paint
mat("wall_accent", rough=0.5, tex="american_walnut_veneer", tile=1.2, tint=(0.62, 0.42, 0.28))             # wood panel behind beds
mat("ceiling", (0.95, 0.94, 0.91), 0.95, tex="white_plaster_02", tile=2.0, albedo=False)
mat("exterior", (0.88, 0.78, 0.62), 0.95, tex="white_plaster_02", tile=2.5, albedo=False)
mat("slab", (0.6, 0.6, 0.58), 0.9)
mat("marble", tex="marble_01", tile=1.2)
mat("wood", tex="laminate_floor_02", tile=2.0)
mat("bathtile", tex="anti_skid_tiles", tile=0.6)
mat("walltile", tex="long_white_tiles", tile=0.9)
mat("terracotta", tex="terracotta_floor_tiles", tile=1.2)
mat("concrete", tex="concrete_floor", tile=2.0)
mat("grass", tex="leafy_grass", tile=1.5, tint=(0.55, 0.8, 0.4))
mat("granite", rough=0.15, tex="marble_01", tile=1.5, tint=(0.12, 0.11, 0.11))   # black marble slab
mat("stone_top", rough=0.2, tex="terrazzo_tiles", tile=0.9, grey=True, tint=(0.36, 0.35, 0.34))   # speckled granite worktop
mat("stone_wall", rough=0.2, tex="marble_01", tile=1.0, tint=(0.95, 0.93, 0.9))
mat("pebble_floor", rough=0.7, tex="dry_river_pebbles", tile=0.6)
mat("marble_top", rough=0.15, tex="marble_01", tile=1.0)
mat("stair", (0.62, 0.58, 0.52), 0.4, tex="granite_tile", tile=1.0)
mat("glass", (0.75, 0.85, 0.9), 0.05, alpha=0.18)
mat("frame", (0.92, 0.92, 0.92), 0.4)                 # uPVC/powder-coated window frames
mat("steel", (0.75, 0.75, 0.77), 0.25, 1.0)
mat("teak", rough=0.4, tex="black_walnut_veneer_01", tile=1.0, tint=(0.5, 0.3, 0.18))
mat("laminate_w", rough=0.4, tex="oak_veneer_01", tile=1.2)
mat("white_gloss", (0.93, 0.93, 0.92), 0.15)
mat("ceramic", (0.97, 0.97, 0.96), 0.08)
mat("sheet", rough=0.9, tex="stretch_poplin", tile=0.35, grey=True, tint=(1.0, 0.99, 0.97))
mat("duvet", rough=0.95, tex="waffle_pique_cotton", tile=0.3, grey=True, tint=(0.93, 0.9, 0.85))
mat("throw", rough=1.0, tex="knitted_fleece", tile=0.35, grey=True, tint=(0.62, 0.34, 0.24))
mat("velvet", rough=0.8, tex="velour_velvet", tile=0.5, grey=True, tint=(0.3, 0.42, 0.4))
mat("velvet_head", rough=0.8, tex="velour_velvet", tile=0.5, grey=True, tint=(0.62, 0.55, 0.48))
mat("jacquard", rough=0.9, tex="quatrefoil_jacquard_fabric", tile=0.35, grey=True, tint=(0.95, 0.72, 0.35))
mat("boucle", rough=1.0, tex="wool_boucle", tile=0.4, grey=True, tint=(0.95, 0.92, 0.86))
mat("fabric_blanket", rough=0.9, tex="floral_jacquard", tile=0.6, tint=(1.0, 0.75, 0.7))
mat("rug", rough=1.0, tex="hessian_380", tile=0.8, tint=(0.9, 0.75, 0.6))
mat("curtain", rough=0.9, tex="rough_linen", tile=0.6, grey=True, tint=(0.95, 0.9, 0.8))
mat("black", (0.02, 0.02, 0.02), 0.3)
mat("screen", (0.01, 0.01, 0.015), 0.05)
mat("light", (1.0, 0.95, 0.85), 0.5, emit=6.0)
mat("appliance", (0.8, 0.8, 0.82), 0.3, 0.8)
mat("steel_brushed", rough=0.3, metal=0.9, image=_brushed(), tile=0.6)

# ---------------------------------------------------------------- geometry helpers
COLL = {}


def collection(name):
    if name not in COLL:
        c = bpy.data.collections.new(name)
        scene.collection.children.link(c)
        COLL[name] = c
    return COLL[name]


def ring_band(name, cx, cy, r_in, r_out, a0, a1, z0, z1, mat, coll="arch"):
    """a curved band in feet (a curved wall, skirting, a cove): the ring sector between r_in and r_out from angle a0
    to a1 (degrees, plan axes), from z0 to z1. A whole circle (360 degrees) closes on itself."""
    import curves
    quads = curves.sector_quads(cx, cy, r_in, r_out, a0, a1)
    bm = bmesh.new()
    V = lambda p, z: bm.verts.new((p[0] * F, p[1] * F, z * F))
    full = a1 - a0 >= 359.9
    for i, (pi0, po0, po1, pi1) in enumerate(quads):
        b = [V(pi0, z0), V(po0, z0), V(po1, z0), V(pi1, z0)]
        t = [V(pi0, z1), V(po0, z1), V(po1, z1), V(pi1, z1)]
        bm.faces.new((b[3], b[2], b[1], b[0]))          # bottom
        bm.faces.new((t[0], t[1], t[2], t[3]))          # top
        bm.faces.new((b[1], b[2], t[2], t[1]))          # outer face
        bm.faces.new((b[3], b[0], t[0], t[3]))          # inner face
        if not full and i == 0:
            bm.faces.new((b[0], b[1], t[1], t[0]))      # start cap
        if not full and i == len(quads) - 1:
            bm.faces.new((b[2], b[3], t[3], t[2]))      # end cap
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(MATS[mat])
    ob = bpy.data.objects.new(name, me)
    collection(coll).objects.link(ob)
    return ob


def disc(name, cx, cy, r, z, mat, coll="arch", up=True):
    """a flat disc in feet at height z (a round room's floor or ceiling)"""
    import curves
    pts = curves.arc_points(cx, cy, r, 0, 360)[:-1]
    bm = bmesh.new()
    vs = [bm.verts.new((x * F, y * F, z * F)) for x, y in pts]
    bm.faces.new(vs if up else list(reversed(vs)))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(MATS[mat])
    ob = bpy.data.objects.new(name, me)
    collection(coll).objects.link(ob)
    return ob


def spiral_stair(name, rect, z0, rise, steps=None, turn=0.85, coll="arch"):
    """a spiral (helical) stair in feet: wedge treads round a central column inside rect, climbing `rise` from z0 in
    `turn` revolutions, with a helical handrail at the outer edge. -> the objects (treads, column, rail)"""
    x0, x1, y0, y1 = rect
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    R = max(1.5, min(x1 - x0, y1 - y0) / 2 - 0.1)
    rc = 0.3
    n = steps or max(10, round(rise / 0.62))
    da = 2 * math.pi * turn / n
    bm = bmesh.new()
    for i in range(n):
        a0, a1 = i * da, (i + 1) * da + 0.04
        zt = z0 + rise * (i + 1) / n
        ring = []
        for a in (a0, (a0 + a1) / 2, a1):
            ring.append((cx + R * math.cos(a), cy + R * math.sin(a)))
        pts = [(cx + rc * math.cos(a0), cy + rc * math.sin(a0))] + ring + [(cx + rc * math.cos(a1), cy + rc * math.sin(a1))]
        top = [bm.verts.new((px * F, py * F, zt * F)) for px, py in pts]
        bot = [bm.verts.new((px * F, py * F, (zt - 0.18) * F)) for px, py in pts]
        bm.faces.new(top)
        bm.faces.new(list(reversed(bot)))
        for k in range(len(pts)):
            j = (k + 1) % len(pts)
            bm.faces.new((bot[k], bot[j], top[j], top[k]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(MATS["stair"])
    treads = bpy.data.objects.new(name, me)
    collection(coll).objects.link(treads)
    col = bpy.data.meshes.new(f"{name}_column")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=rc * F, radius2=rc * F, depth=(rise + 3.2) * F)
    bm.to_mesh(col)
    bm.free()
    col.materials.append(MATS["steel"])
    column = bpy.data.objects.new(f"{name}_column", col)
    column.location = (cx * F, cy * F, (z0 + (rise + 3.2) / 2) * F)
    collection(coll).objects.link(column)
    cu = bpy.data.curves.new(f"{name}_rail", "CURVE")
    cu.dimensions, cu.bevel_depth, cu.bevel_resolution = "3D", 0.025, 3
    sp = cu.splines.new("POLY")
    m = n * 4
    sp.points.add(m)
    for i in range(m + 1):
        a = 2 * math.pi * turn * i / m
        sp.points[i].co = ((cx + (R - 0.1) * math.cos(a)) * F, (cy + (R - 0.1) * math.sin(a)) * F, (z0 + rise * i / m + 3.0) * F, 1)
    cu.materials.append(MATS["steel"])
    rail = bpy.data.objects.new(f"{name}_rail", cu)
    collection(coll).objects.link(rail)
    return [treads, column, rail]


def mesh_from_boxes(name, boxes, coll="arch", bevel=0.0, seg=2):
    """boxes: list of (x0,x1,y0,y1,z0,z1,matname) in FEET (object-local). One object, multi-material."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    mat_names = []
    for b in boxes:
        x0, x1, y0, y1, z0, z1, mn = b
        if x1 - x0 < 1e-4 or y1 - y0 < 1e-4 or z1 - z0 < 1e-4:
            continue
        if mn not in mat_names:
            mat_names.append(mn)
        mi = mat_names.index(mn)
        tile = MATS[mn]["tile"]
        v = [bm.verts.new((x * F, y * F, z * F)) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
        # v index = z*4 + y*2 + x
        quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
        for q in quads:
            try:
                f = bm.faces.new([v[i] for i in q])
            except ValueError:
                continue
            f.material_index = mi
            f.normal_update()
            n = f.normal
            ax = max(range(3), key=lambda i: abs(n[i]))
            a, c = [(1, 2), (0, 2), (0, 1)][ax]
            for lp in f.loops:
                co = lp.vert.co
                lp[uv].uv = (co[a] / tile, co[c] / tile)
    bm.to_mesh(me)
    bm.free()
    for mn in mat_names:
        me.materials.append(MATS[mn])
    ob = bpy.data.objects.new(name, me)
    ob.location.z = LEVEL * F
    collection(coll).objects.link(ob)
    if bevel:
        md = ob.modifiers.new("bevel", "BEVEL")
        md.width = bevel
        md.segments = seg
        md.limit_method = "ANGLE"
    return ob


def overlap(a, b):
    return all(a[2 * i] < b[2 * i + 1] - 1e-6 and b[2 * i] < a[2 * i + 1] - 1e-6 for i in range(3))


def subtract(a, b):
    """axis-aligned box difference a - b -> list of boxes (6-tuples)."""
    if not overlap(a, b):
        return [a]
    out, a = [], list(a)
    for ax in range(3):
        lo, hi = 2 * ax, 2 * ax + 1
        if a[lo] < b[lo]:
            p = a.copy(); p[hi] = b[lo]; out.append(tuple(p)); a[lo] = b[lo]
        if a[hi] > b[hi]:
            p = a.copy(); p[lo] = b[hi]; out.append(tuple(p)); a[hi] = b[hi]
    return out


def subtract_all(boxes, cutters):
    for c in cutters:
        boxes = [p for b in boxes for p in subtract(b, c)]
    return boxes


def disjoint(boxes):
    """remove overlaps so no two boxes share coincident faces (avoids z-fighting / black Cycles faces)."""
    out = []
    for b in boxes:
        out += subtract_all([b], list(out))
    return out


# self-check of the box difference
_t = subtract((0, 4, 0, 1, 0, 10), (1, 2, -1, 2, 0, 7))
_d = disjoint([(0, 2, 0, 1, 0, 1), (1, 3, 0, 1, 0, 1)])
assert abs(sum((b[1]-b[0])*(b[3]-b[2])*(b[5]-b[4]) for b in _d) - 3) < 1e-9, _d
assert abs(sum((b[1]-b[0])*(b[3]-b[2])*(b[5]-b[4]) for b in _t) - (40 - 7)) < 1e-9, _t

COLLIDERS = []   # (x0,x1,y0,y1) feet, 2D footprint blocking the walker
FURN = []        # (name, footprint) of furniture, for the doorway clearance check
# ---------------------------------------------------------------- furniture
PROTO = {}


def load_model(name):
    if name in PROTO:
        return PROTO[name]
    if not name.replace("_", "").isalnum():
        raise ValueError(f"bad model name {name!r}")
    path = os.path.join(ASSETS, "models", name, f"{name}_1k.gltf")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
    PROTO[name] = new
    return new


def place(name, x, y, rot=0, z=0.0, scale=1.0, collide=True):
    """x,y,z in feet; rot = degrees, 0 = model's default facing."""
    objs = load_model(name)
    root = bpy.data.objects.new(f"{name}_at_{x:.1f}_{y:.1f}", None)
    collection("furniture").objects.link(root)
    mapping = {}
    for o in objs:
        c = o.copy()  # shares mesh data -> glTF instancing
        mapping[o] = c
        collection("furniture").objects.link(c)
    for o, c in mapping.items():
        c.parent = mapping.get(o.parent, root)
    root.location = (x * F, y * F, (z + LEVEL) * F)
    root.rotation_euler = (0, 0, math.radians(rot))
    root.scale = (scale,) * 3
    if collide:
        bpy.context.view_layer.update()
        add_collider([c for c in mapping.values() if c.type == "MESH"])
    return root


def add_collider(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    if not pts:
        return
    # furniture does not block the walker; footprints are only used for the doorway clearance check
    FURN.append((objs[0].name, (min(p.x for p in pts) / F, max(p.x for p in pts) / F,
                                min(p.y for p in pts) / F, max(p.y for p in pts) / F)))


def group(name, boxes, x, y, rot=0, bevel=0.0, collide=True, z=0.0, seg=2):
    """procedural item: boxes in local feet, front faces -Y, origin at footprint centre."""
    ob = mesh_from_boxes(name, boxes, coll="furniture", bevel=bevel * F, seg=seg)
    ob.location = (x * F, y * F, (z + LEVEL) * F)
    ob.rotation_euler = (0, 0, math.radians(rot))
    if collide:
        bpy.context.view_layer.update()
        add_collider([ob])
    return ob


# rot convention for procedural items: 0 -> front faces -y, 90 -> +x, 180 -> +y, 270 -> -x
def bed(x, y, rot, w=5.0, l=6.6, blanket="throw", panel=None):
    """upholstered bed made up with sheet, duvet, a throw and pillows. blanket: material of the throw at the foot.
    panel: width of the wood panel on the wall behind the bed (default bed + 1.8 ft each side; 0 = none)"""
    hw = w / 2
    yb, yf = l / 2, -l / 2                      # head (back) at +y local
    hp = hw + 1.8 if panel is None else panel / 2
    if hp > 0:
        group("accent_panel", [(-hp, hp, yb - 0.03, yb, 0, WALL_H - 0.01, "wall_accent")],
              x, y, rot, collide=False)   # panel sits flush on the wall behind the headboard
    if blanket not in MATS:
        blanket = "throw"
    seed = round(x * 7 + y * 13)
    r = item("bed", x, y, rot)
    p_box(r, "bed_plinth", w - 0.5, l - 0.8, 0.3, "black", (0, -0.2, 0), bevel=0.01)
    p_box(r, "bed_base", w, l - 0.35, 0.75, "teak", (0, -0.175, 0.3), bevel=0.05)
    p_box(r, "headboard_back", w + 0.3, 0.15, 3.9, "teak", (0, yb - 0.1, 0), bevel=0.03)
    n = max(3, round((w + 0.3) / 0.9))          # channel-tufted upholstered headboard
    cw = (w + 0.3) / n
    for i in range(n):
        p_soft(r, "headboard", cw - 0.02, 0.4, 2.9, "velvet_head", (-(w + 0.3) / 2 + cw * (i + 0.5), yb - 0.37, 0.95),
               r=0.17)
    p_soft(r, "mattress", w - 0.15, l - 0.55, 0.75, "sheet", (0, -0.225, 1.05), r=0.12)
    p_drape(r, "duvet", -hw + 0.08, hw - 0.08, yf + 0.1, yb - 2.1, 1.86, 0.85, "duvet", "xXy", thick=0.06, seed=seed)
    p_soft(r, "duvet_fold", w - 0.1, 0.55, 0.3, "duvet", (0, yb - 2.1, 1.72), r=0.14)
    p_drape(r, "throw", -hw, hw, yf + 0.3, yf + 1.7, 1.94, 1.0, blanket, "xX", thick=0.04, seed=seed)
    pw, xs = (w - 0.6, (0,)) if w < 4 else (hw - 0.3, (-w / 4, w / 4))
    for px in xs:                                # sleeping pillows leaning on the headboard
        p_soft(r, "pillow", pw, 0.55, 1.35, "sheet", (px, yb - 0.95, 1.75), (-18, 0, 0), r=0.26)
    if w >= 4:                                   # cushions in front of them
        for k, s in enumerate((-1, 1)):
            p_soft(r, "cushion", 1.25, 0.4, 1.25, "jacquard", (s * (w / 4 - 0.1), yb - 1.45, 1.8), (-22, 0, s * 6), r=0.2)
        p_soft(r, "cushion", 1.1, 0.35, 0.8, "boucle", (0, yb - 1.6, 1.8), (-15, 0, 0), r=0.16)
    return done(r)


def wardrobe(x, y, rot, w=6.0, d=2.0, h=7.0):
    hw = w / 2
    b = [(-hw, hw, -d / 2 + 0.05, d / 2, 0, h, "laminate_w")]
    n = max(2, round(w / 1.5))
    for i in range(n):
        x0 = -hw + w * i / n
        b.append((x0 + 0.03, x0 + w / n - 0.03, -d / 2, -d / 2 + 0.05, 0.3, h - 0.05, "laminate_w"))
        hx = x0 + (w / n - 0.25 if i % 2 == 0 else 0.25)
        b.append((hx - 0.04, hx + 0.04, -d / 2 - 0.08, -d / 2, 3.0, 4.2, "steel"))
    group("wardrobe", b, x, y, rot, bevel=0.01)


def wall_cabinet(x0, x1, y0, y1):
    mesh_from_boxes("wall_cabinet", [(x0, x1, y0, y1, 5.0, 7.2, "laminate_w")], coll="furniture",
                    bevel=0.01 * F)


def fridge(x, y, rot):
    group("fridge", [(-1.15, 1.15, -1.0, 1.1, 0, 5.8, "appliance"),
                     (0.9, 0.98, -1.1, -1.0, 2.5, 4.5, "steel"), (0.9, 0.98, -1.1, -1.0, 4.7, 5.5, "steel"),
                     (-1.14, 1.14, -1.02, -1.0, 4.55, 4.6, "black")], x, y, rot, bevel=0.06)


def wc(x, y, rot):
    group("wc", [(-0.6, 0.6, -1.0, 0.5, 0, 1.3, "ceramic"), (-0.7, 0.7, 0.5, 1.15, 0, 2.6, "ceramic"),
                 (-0.65, 0.65, -1.05, 0.5, 1.3, 1.38, "white_gloss")], x, y, rot, bevel=0.15, seg=3)


def basin(x, y, rot):
    group("basin", [(-0.9, 0.9, -0.7, 0.6, 2.4, 2.85, "ceramic"), (-0.15, 0.15, -0.2, 0.6, 0, 2.4, "ceramic"),
                    (-0.05, 0.05, 0.25, 0.4, 2.85, 3.3, "steel"),
                    (-1.0, 1.0, 0.58, 0.62, 3.6, 6.0, "glass"), (-1.05, 1.05, 0.62, 0.66, 3.55, 6.05, "steel")],
          x, y, rot, bevel=0.05, collide=True)


def shower(x, y):
    group("shower", [(-0.04, 0.04, -0.04, 0.04, 0, 6.8, "steel"), (-0.35, 0.35, -0.35, 0.35, 6.7, 6.78, "steel")],
          x, y, 0, bevel=0.01, collide=False)


def tv(x, y, rot, z=3.2):
    group("tv", [(-2.0, 2.0, -0.05, 0.1, z, z + 2.3, "black"), (-1.95, 1.95, -0.07, -0.05, z + 0.05, z + 2.25, "screen")],
          x, y, rot, bevel=0.01, collide=False)


def rug(x0, x1, y0, y1, m="rug"):
    mesh_from_boxes("rug", [(x0, x1, y0, y1, 0, 0.04, m)], coll="furniture", bevel=0.01 * F)


def desk(x, y, rot):
    group("desk", [(-1.75, 1.75, -1.0, 1.0, 2.4, 2.55, "teak"), (-1.75, -1.6, -1.0, 1.0, 0, 2.4, "teak"),
                   (1.6, 1.75, -1.0, 1.0, 0, 2.4, "teak"), (0.3, 1.6, -0.9, 1.0, 1.4, 2.4, "teak")],
          x, y, rot, bevel=0.02)


def ceiling_light(x, y, s=0.9):
    mesh_from_boxes("ceiling_light", [(x - s, x + s, y - s, y + s, WALL_H - 0.08, WALL_H, "light")],
                    coll="furniture")


def downlights(x0, x1, y0, y1, step=5.5):
    """recessed downlights over a room: a grid about `step` feet apart, each a small glowing square in a white trim"""
    nx, ny = max(2, round((x1 - x0) / step)), max(2, round((y1 - y0) / step))
    boxes = []
    for i in range(nx):
        for j in range(ny):
            cx, cy = x0 + (i + 0.5) * (x1 - x0) / nx, y0 + (j + 0.5) * (y1 - y0) / ny
            boxes.append((cx - 0.3, cx + 0.3, cy - 0.3, cy + 0.3, WALL_H - 0.03, WALL_H, "white_gloss"))
            boxes.append((cx - 0.22, cx + 0.22, cy - 0.22, cy + 0.22, WALL_H - 0.05, WALL_H - 0.02, "light"))
    mesh_from_boxes("downlights", boxes, coll="furniture")




# ---------------------------------------------------------------- real fixtures: curved, bevelled meshes
# (items are assembled from parts under an empty; local feet, front faces -y at rot 0, back against +y)
mat("chrome", (0.92, 0.92, 0.94), 0.06, 1.0)
mat("mirror", (0.96, 0.96, 0.96), 0.0, 1.0)
mat("black_glass", (0.01, 0.01, 0.012), 0.04)
mat("brass", (0.85, 0.62, 0.28), 0.25, 1.0)
mat("cast_iron", (0.03, 0.03, 0.03), 0.55, 0.6)
mat("quartz", rough=0.12, tex="marble_01", tile=1.4, tint=(1.0, 0.98, 0.95))
mat("towel", rough=1.0, tex="cotton_jersey", tile=0.3, tint=(0.55, 0.62, 0.68))
mat("led", (1.0, 0.86, 0.66), 0.5, emit=8.0)
mat("plastic_white", (0.9, 0.9, 0.88), 0.35)
mat("water", (0.55, 0.7, 0.75), 0.02, alpha=0.5)
mat("blue_accent", (0.1, 0.35, 0.75), 0.3)


def _box_uv(bm, tile):
    """texture UVs in metres / tile, projected along each face's main axis (as mesh_from_boxes does)"""
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        f.normal_update()
        ax = max(range(3), key=lambda i: abs(f.normal[i]))
        a, c = [(1, 2), (0, 2), (0, 1)][ax]
        for lp in f.loops:
            lp[uv].uv = (lp.vert.co[a] / tile, lp.vert.co[c] / tile)


def _mesh_obj(name, bm, mn, parent, loc=(0, 0, 0), rot=(0, 0, 0), smooth=40, bevel=0.0, seg=3, solid=0.0, soft=0):
    """soft: subdivision levels after the bevel, for upholstery and pillows"""
    if not bm.loops.layers.uv:
        _box_uv(bm, MATS[mn]["tile"])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(MATS[mn])
    if smooth:
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(smooth))
    ob = bpy.data.objects.new(name, me)
    collection("furniture").objects.link(ob)
    ob.parent = parent
    ob.location = Vector(loc) * F
    ob.rotation_euler = [math.radians(a) for a in rot]
    if solid:
        md = ob.modifiers.new("solid", "SOLIDIFY")
        md.thickness = solid * F
    if bevel:
        md = ob.modifiers.new("bevel", "BEVEL")
        md.width, md.segments, md.limit_method = bevel * F, seg, "ANGLE"
        md.harden_normals = False
    if soft:
        md = ob.modifiers.new("soft", "SUBSURF")
        md.levels = md.render_levels = soft
    return ob


def p_soft(root, name, sx, sy, sz, mn, loc=(0, 0, 0), rot=(0, 0, 0), r=0.15):
    """upholstered block: a box with round edges r (feet), smoothed into a slightly puffy cushion"""
    return p_box(root, name, sx, sy, sz, mn, loc, rot, bevel=min(r, sx / 2.2, sy / 2.2, sz / 2.2), seg=2, soft=2,
                 smooth=180)


def p_drape(root, name, x0, x1, y0, y1, top, hang, mn, sides="xX y", thick=0.07, seed=0, step=0.12):
    """cloth lying on the rectangle x0..x1, y0..y1 at height top and falling over the edges named in sides
    (x = -x, X = +x, y = -y, Y = +y) by hang feet, with soft folds; local feet like p_box"""
    rnd = random.Random(seed)
    ex = [hang if "x" in sides else 0, hang if "X" in sides else 0, hang if "y" in sides else 0, hang if "Y" in sides else 0]
    us = [x0 - ex[0] + i * step for i in range(int((x1 - x0 + ex[0] + ex[1]) / step) + 1)]
    vs = [y0 - ex[2] + j * step for j in range(int((y1 - y0 + ex[2] + ex[3]) / step) + 1)]
    ph = [rnd.uniform(0, 6.3) for _ in range(4)]
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    grid = []
    for v in vs:
        row = []
        for u in us:
            dx, dy = max(0, x0 - u, u - x1), max(0, y0 - v, v - y1)
            drop = math.hypot(dx, dy)
            flare = 0.04 + 0.1 * drop                         # cloth stands off the edge a little more as it falls
            px = min(max(u, x0 - flare), x1 + flare)
            py = min(max(v, y0 - flare), y1 + flare)
            k = min(drop, 0.6) / 0.6                     # vertical folds: they vary along the edge, not down it
            px += 0.05 * k * math.sin(v * 3.1 + ph[0]) * (1 if u > x1 else -1 if u < x0 else 0)
            py += 0.05 * k * math.sin(u * 3.1 + ph[1]) * (1 if v > y1 else -1 if v < y0 else 0)
            pz = top - drop + (0.02 * math.sin(u * 2.3 + ph[2]) * math.sin(v * 1.9 + ph[3]) if drop == 0 else 0)
            row.append(bm.verts.new((px * F, py * F, pz * F)))
        grid.append(row)
    for j in range(len(vs) - 1):
        for i in range(len(us) - 1):
            f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            for lp, (a, b) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                lp[uv].uv = (us[a] * F / MATS[mn]["tile"], vs[b] * F / MATS[mn]["tile"])
    return _mesh_obj(name, bm, mn, root, smooth=80, solid=thick, soft=1)


def p_pleats(root, name, width, h, mn, loc=(0, 0, 0), rot=(0, 0, 0), depth=0.14, pitch=0.42):
    """curtain panel hanging from its top edge: width along local x (centred), pleated in y, bottom at z=0"""
    n = max(2, round(width / pitch * 8))
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    cols = []
    for i in range(n + 1):
        x = -width / 2 + width * i / n
        y = depth / 2 * math.sin(2 * math.pi * x / pitch)
        cols.append([bm.verts.new((x * F, (y + (depth * 0.4 * math.sin(x * 1.3) if z == 0 else 0)) * F, z * F))
                     for z in (0, h)])
    t = MATS[mn]["tile"]
    for i in range(n):
        f = bm.faces.new((cols[i][0], cols[i + 1][0], cols[i + 1][1], cols[i][1]))
        for lp, (a, b) in zip(f.loops, ((i, 0), (i + 1, 0), (i + 1, 1), (i, 1))):
            lp[uv].uv = ((-width / 2 + width * a / n) * 1.3 * F / t, b * h * F / t)
    return _mesh_obj(name, bm, mn, root, loc, rot, smooth=80, solid=0.03)


def _bm_xform(bm, scale=(1, 1, 1), lift=0.0):
    for v in bm.verts:
        v.co = Vector((v.co.x * scale[0], v.co.y * scale[1], v.co.z * scale[2] + lift))
    return bm


def p_cyl(root, name, r1, r2, h, mn, loc=(0, 0, 0), rot=(0, 0, 0), sx=1.0, sy=1.0, segs=48, **kw):
    """cone/cylinder, base at local z=0 before rotation; sx/sy squash the cross-section."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs, radius1=r1 * F, radius2=r2 * F,
                          depth=h * F)
    return _mesh_obj(name, _bm_xform(bm, (sx, sy, 1), h * F / 2), mn, root, loc, rot, **kw)


def p_box(root, name, sx, sy, sz, mn, loc=(0, 0, 0), rot=(0, 0, 0), bevel=0.02, seg=3, **kw):
    """box centred on x/y, base at z=0 (feet)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    kw.setdefault("smooth", 30)
    return _mesh_obj(name, _bm_xform(bm, (sx * F, sy * F, sz * F), sz * F / 2), mn, root, loc, rot,
                     bevel=bevel, seg=seg, **kw)


def p_frustum(root, name, w0, d0, w1, d1, h, mn, loc=(0, 0, 0), **kw):
    """tapered box: bottom w0 x d0, top w1 x d1 (feet), base at z=0."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        top = v.co.z > 0
        v.co = Vector((v.co.x * (w1 if top else w0) * F, v.co.y * (d1 if top else d0) * F, (v.co.z + 0.5) * h * F))
    return _mesh_obj(name, bm, mn, root, loc, smooth=0, **kw)


def p_bowl(root, name, r, depth, mn, loc=(0, 0, 0), sy=1.0, wall=0.04):
    """open bowl (lower half sphere), rim at local z=0."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=r * F)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > 1e-5], context="VERTS")
    _bm_xform(bm, (1, sy, depth / r))
    return _mesh_obj(name, bm, mn, root, loc, smooth=80, solid=wall)


def p_torus(root, name, R, r, mn, loc=(0, 0, 0), rot=(0, 0, 0), sy=1.0, u=48, v=16):
    bm = bmesh.new()
    rings = []
    for i in range(u):
        a = 2 * math.pi * i / u
        ring = []
        for j in range(v):
            b = 2 * math.pi * j / v
            d = R + r * math.cos(b)
            ring.append(bm.verts.new((d * math.cos(a) * F, d * math.sin(a) * sy * F, r * math.sin(b) * F)))
        rings.append(ring)
    for i in range(u):
        for j in range(v):
            a, b = rings[i], rings[(i + 1) % u]
            bm.faces.new((a[j], b[j], b[(j + 1) % v], a[(j + 1) % v]))
    return _mesh_obj(name, bm, mn, root, loc, rot, smooth=80)


def p_tube(root, name, pts, radius, mn):
    """swept round tube through local points (feet); used for taps, rails and hoses."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth, cu.bevel_resolution, cu.use_fill_caps = radius * F, 4, True
    sp = cu.splines.new("NURBS")
    sp.points.add(len(pts) - 1)
    for p, c in zip(sp.points, pts):
        p.co = (c[0] * F, c[1] * F, c[2] * F, 1)
    sp.use_endpoint_u, sp.order_u = True, min(4, len(pts))
    tmp = bpy.data.objects.new(name + "_crv", cu)
    scene.collection.objects.link(tmp)
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    me.materials.clear()
    me.materials.append(MATS[mn])
    me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    collection("furniture").objects.link(ob)
    ob.parent = root
    return ob


def item(name, x, y, rot=0, z=0.0):
    root = bpy.data.objects.new(name, None)
    collection("furniture").objects.link(root)
    root.location = (x * F, y * F, (z + LEVEL) * F)
    root.rotation_euler = (0, 0, math.radians(rot))
    return root


def done(root, collide=True):
    if collide:
        bpy.context.view_layer.update()
        add_collider([c for c in root.children_recursive if c.type == "MESH"])
    return root


def arc(c, r, a0, a1, n=10, plane="yz"):
    """points on a circular arc (degrees) around centre c in the given plane."""
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        u, v = r * math.cos(a), r * math.sin(a)
        pts.append((c[0], c[1] + u, c[2] + v) if plane == "yz" else (c[0] + u, c[1], c[2] + v))
    return pts


def wc2(x, y, rot):
    """floor-mounted one-piece EWC with closed soft-close lid, cistern, chrome flush and health faucet."""
    r = item("wc", x, y, rot)
    p_cyl(r, "wc_body", 0.42, 0.6, 1.22, "ceramic", (0, -0.2, 0), sy=1.38, bevel=0.06, seg=4)
    p_box(r, "wc_skirt", 1.05, 0.7, 1.22, "ceramic", (0, 0.5, 0), bevel=0.12, seg=4)
    p_cyl(r, "wc_seat", 0.62, 0.62, 0.07, "white_gloss", (0, -0.2, 1.22), sy=1.38, bevel=0.03)
    p_cyl(r, "wc_lid", 0.6, 0.6, 0.07, "white_gloss", (0, -0.17, 1.29), sy=1.36, bevel=0.03)
    p_box(r, "wc_cistern", 1.32, 0.55, 1.15, "ceramic", (0, 0.78, 1.25), bevel=0.14, seg=5)
    p_box(r, "wc_cistern_lid", 1.38, 0.6, 0.08, "ceramic", (0, 0.78, 2.4), bevel=0.03)
    p_cyl(r, "wc_flush", 0.11, 0.11, 0.03, "chrome", (0, 0.78, 2.48))
    # health faucet on the side wall-ish bracket with a coiled hose
    p_box(r, "hf_holder", 0.12, 0.08, 0.2, "chrome", (0.95, 0.98, 2.0), bevel=0.02)
    p_cyl(r, "hf_head", 0.05, 0.06, 0.45, "chrome", (0.95, 0.9, 1.95), rot=(15, 0, 0))
    p_tube(r, "hf_hose", [(0.95, 0.95, 1.95), (1.0, 0.9, 1.2), (0.9, 0.85, 0.6), (0.85, 0.95, 1.6),
                          (0.9, 1.0, 2.3)], 0.025, "chrome")
    return done(r)


def vanity(x, y, rot, w=2.6):
    """wall-hung vanity: laminate cabinet, quartz top, vessel basin, tall mixer, backlit mirror."""
    r = item("vanity", x, y, rot)
    d = 1.6
    p_box(r, "vanity_cab", w, d, 1.5, "laminate_w", (0, 0.05, 1.05), bevel=0.02)
    p_box(r, "vanity_groove", w - 0.1, 0.02, 0.04, "black", (0, 0.05 - d / 2 - 0.005, 2.25), bevel=0)
    p_box(r, "vanity_top", w + 0.1, d + 0.1, 0.12, "quartz", (0, 0.05, 2.55), bevel=0.02)
    p_bowl(r, "basin_bowl", 0.62, 0.5, "ceramic", (0, -0.1, 3.15), sy=0.82)
    p_cyl(r, "basin_drain", 0.06, 0.06, 0.01, "chrome", (0, -0.1, 2.68))
    p_cyl(r, "tap_base", 0.07, 0.07, 0.15, "chrome", (0, 0.55, 2.67))
    p_tube(r, "tap_spout", [(0, 0.55, 2.7), (0, 0.55, 3.55)] + arc((0, 0.35, 3.55), 0.2, 0, 160, 8)[1:] +
           [(0, 0.2, 3.35)], 0.045, "chrome")
    p_box(r, "tap_lever", 0.06, 0.25, 0.05, "chrome", (0.1, 0.5, 3.2), rot=(-20, 0, 0), bevel=0.01)
    p_box(r, "mirror_glow", w * 0.9 + 0.1, 0.03, 3.1, "led", (0, d / 2 + 0.02, 3.95), bevel=0)
    p_box(r, "mirror", w * 0.9, 0.06, 3.0, "mirror", (0, d / 2 - 0.02, 4.0), bevel=0.05)
    p_box(r, "soap_dish", 0.35, 0.25, 0.05, "black_glass", (w / 2 - 0.35, 0.4, 2.67), bevel=0.02)
    return done(r)


def shower2(x, y, rot, glass=None):
    """rain shower on a wall arm + concealed mixer + floor drain; glass = (x0,x1,y0,y1) world screen."""
    r = item("shower", x, y, rot)
    p_tube(r, "shower_arm", [(0, 0.0, 7.4), (0, -0.4, 7.4), (0, -0.9, 7.3), (0, -1.1, 7.15)], 0.05, "chrome")
    p_box(r, "shower_head", 0.85, 0.85, 0.05, "chrome", (0, -1.1, 7.05), bevel=0.02)
    p_cyl(r, "mixer_plate", 0.28, 0.28, 0.04, "chrome", (0, -0.09, 3.8), rot=(90, 0, 0))
    p_box(r, "mixer_lever", 0.06, 0.12, 0.4, "chrome", (0, -0.16, 3.75), bevel=0.02)
    p_box(r, "floor_drain", 0.4, 0.4, 0.015, "steel", (0, -1.1, 0.05), bevel=0)
    p_cyl(r, "hand_shower", 0.05, 0.07, 0.6, "chrome", (0.5, -0.15, 3.9), rot=(0, 0, 0))
    p_tube(r, "hand_hose", [(0.5, -0.15, 3.9), (0.55, -0.25, 2.8), (0.4, -0.2, 2.2), (0.3, -0.1, 3.6)], 0.025,
           "chrome")
    p_box(r, "shower_wall", 2.6, 0.04, 7.6, "stone_wall", (0, -0.07, 0), bevel=0)     # in front of the 0.03 ft wall tiles
    p_box(r, "shower_tray", 2.5, 2.5, 0.05, "pebble_floor", (0, -1.27, 0), bevel=0.005)
    done(r, collide=False)
    if glass:
        x0, x1, y0, y1 = glass
        mesh_from_boxes("shower_glass", [(x0, x1, y0, y1, 0.05, 6.8, "glass")], coll="furniture")
        mesh_from_boxes("shower_glass_trim", [(x0, x1, y0, y1, 6.8, 6.85, "chrome"),
                                              (x0, x1, y0, y1, 0.0, 0.05, "chrome")], coll="furniture")
    return r


def geyser(x, y, rot, z=6.4):
    r = item("geyser", x, y, rot, z=z)
    p_cyl(r, "geyser_tank", 0.5, 0.5, 1.7, "plastic_white", (-0.85, -0.55, 0.5), rot=(0, 90, 0), bevel=0.12,
          seg=4)
    p_box(r, "geyser_panel", 0.5, 0.05, 0.25, "blue_accent", (0, -1.04, 0.35), bevel=0.02)
    return done(r, collide=False)


def _doors(r, length, depth, z0, z1, handle_at, front_y, n=None):
    """shaker-ish door fronts with bar handles along local x; front_y = local y of the cabinet face."""
    n = n or max(1, round(length / 1.5))
    dw = length / n
    for i in range(n):
        cx = -length / 2 + dw * (i + 0.5)
        p_box(r, "door", dw - 0.04, 0.06, z1 - z0 - 0.04, "laminate_w", (cx, front_y - 0.03, z0 + 0.02), bevel=0.01)
        p_box(r, "door_panel", dw - 0.4, 0.02, z1 - z0 - 0.5, "laminate_w", (cx, front_y - 0.065, z0 + 0.25),
              bevel=0.005)
        hx = cx + (dw / 2 - 0.25 if i % 2 == 0 else -dw / 2 + 0.25)
        p_box(r, "handle", 0.05, 0.08, 0.7, "chrome", (hx, front_y - 0.1, handle_at - 0.35), bevel=0.015)


def kitchen_run(x0, x1, y0, y1, front, sink=None, hob=None, doors=True, dishwasher=None, oven=False):
    """base cabinets + granite top in world feet; front = side the cook stands ('-y','+y','+x','-x').
    sink / hob / dishwasher = position along the run (world x for runs along x, world y for runs along y)."""
    along_x = front in ("-y", "+y")
    L, Dp = (x1 - x0, y1 - y0) if along_x else (y1 - y0, x1 - x0)
    rot = {"-y": 0, "+x": 90, "+y": 180, "-x": 270}[front]
    r = item("kitchen_run", (x0 + x1) / 2, (y0 + y1) / 2, rot)
    flip = 1 if front in ("-y", "+x") else -1      # local x vs world axis direction after rotation
    c = (x0 + x1) / 2 if along_x else (y0 + y1) / 2

    def local(u):   # world coordinate along the run -> local x
        return (u - c) * flip

    p_box(r, "plinth", L, Dp - 0.3, 0.33, "black", (0, 0.15, 0), bevel=0)
    p_box(r, "carcass", L, Dp - 0.05, 2.42, "laminate_w", (0, 0.025, 0.33), bevel=0.005)
    if doors:
        _doors(r, L, Dp, 0.36, 2.72, 2.55, -Dp / 2 + 0.05)
    # granite top with a hole for the sink bowl
    top = [(-L / 2, L / 2, -Dp / 2 - 0.08, Dp / 2, 2.75, 2.9)]
    holes = []
    if sink is not None:
        sx = local(sink)
        holes.append((sx - 0.9, sx + 0.9, -0.55, 0.55, 2.0, 3.0))
    top = subtract_all(top, holes)
    for i, b in enumerate(top):
        p_box(r, "counter_top", b[1] - b[0], b[3] - b[2], 0.15, "stone_top",
              ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, 2.75), bevel=0.01)
    p_box(r, "backsplash", L, 0.04, 2.0, "walltile", (0, Dp / 2 - 0.02, 2.9), bevel=0)
    if sink is not None:
        sx = local(sink)
        for bx, by, w_, d_ in ((sx, -0.55, 1.8, 0.04), (sx, 0.55, 1.8, 0.04), (sx - 0.9, 0, 0.04, 1.1),
                               (sx + 0.9, 0, 0.04, 1.1)):
            p_box(r, "sink_wall", w_, d_, 0.7, "steel", (bx, by, 2.2), bevel=0)
        p_box(r, "sink_floor", 1.8, 1.1, 0.03, "steel", (sx, 0, 2.2), bevel=0)
        p_cyl(r, "sink_drain", 0.12, 0.12, 0.01, "cast_iron", (sx, 0, 2.235))
        p_box(r, "sink_rim", 1.95, 1.25, 0.02, "steel", (sx, 0, 2.9), bevel=0)
        p_box(r, "sink_rim_cut", 1.8, 1.1, 0.03, "steel", (sx, 0, 2.9), bevel=0)
        p_cyl(r, "faucet_base", 0.08, 0.08, 0.1, "chrome", (sx, 0.75, 2.9))
        p_tube(r, "faucet", [(sx, 0.75, 2.95), (sx, 0.75, 3.9)] + arc((sx, 0.45, 3.9), 0.3, 0, 170, 10)[1:] +
               [(sx, 0.15, 3.6)], 0.05, "chrome")
    if dishwasher is not None:      # integrated dishwasher: steel front proud of the doors, control strip on top
        dx = local(dishwasher)
        fy = -Dp / 2 - 0.02
        p_box(r, "dw_front", 1.95, 0.06, 2.3, "steel_brushed", (dx, fy, 0.38), bevel=0.02)
        p_box(r, "dw_strip", 1.95, 0.07, 0.22, "black_glass", (dx, fy, 2.5), bevel=0.01)
        p_box(r, "dw_led", 0.3, 0.01, 0.05, "led", (dx - 0.6, fy - 0.04, 2.58), bevel=0)
        p_tube(r, "dw_handle", [(dx - 0.7, fy - 0.12, 2.3), (dx + 0.7, fy - 0.12, 2.3)], 0.035, "chrome")
    if hob is not None and oven:    # a built-in oven under the hob: black glass door, steel handle and knobs strip
        hx = local(hob)
        fy = -Dp / 2 - 0.02
        p_box(r, "oven_front", 2.0, 0.07, 1.95, "black_glass", (hx, fy, 0.45), bevel=0.02)
        p_box(r, "oven_glass", 1.5, 0.02, 1.0, "glass", (hx, fy - 0.05, 0.8), bevel=0.01)
        p_box(r, "oven_strip", 2.0, 0.07, 0.3, "steel_brushed", (hx, fy, 2.4), bevel=0.01)
        p_tube(r, "oven_bar", [(hx - 0.8, fy - 0.14, 2.2), (hx + 0.8, fy - 0.14, 2.2)], 0.04, "chrome")
    if hob is not None:
        hx = local(hob)
        p_box(r, "hob_glass", 2.4, 1.5, 0.08, "black_glass", (hx, 0.05, 2.9), bevel=0.02)
        for k, bx in enumerate((-0.75, 0.0, 0.75)):
            rb = 0.22 if k != 1 else 0.28
            p_cyl(r, "burner", rb, rb * 0.9, 0.07, "brass", (hx + bx, 0.15, 2.98))
            p_cyl(r, "burner_cap", rb * 0.6, rb * 0.5, 0.05, "cast_iron", (hx + bx, 0.15, 3.05))
            for a in (0, 45, 90, 135):
                p_box(r, "pan_support", 0.06, rb * 2 + 0.25, 0.08, "cast_iron", (hx + bx, 0.15, 3.0),
                      rot=(0, 0, a), bevel=0.01)
            p_cyl(r, "knob", 0.07, 0.07, 0.07, "chrome", (hx + bx, -0.6, 2.98))
    return done(r)


def kitchen_island(x0, x1, y0, y1, stools=None):
    """a kitchen island in world feet: base cabinets on the cook's side, a white marble top that overhangs 0.9 ft on
    the stools' side (stools = '+y', '-y', '+x' or '-x'; None: no overhang), and three pendant lights over it"""
    along_x = x1 - x0 >= y1 - y0
    L, Dp = (x1 - x0, y1 - y0) if along_x else (y1 - y0, x1 - x0)
    r = item("kitchen_island", (x0 + x1) / 2, (y0 + y1) / 2, 0 if along_x else 90)
    # local +y is world +y when along x; turned 90 degrees it is world -x
    side = {"+y": 1, "-y": -1, "-x": 1, "+x": -1}.get(stools, 0) if stools else 0
    over = 0.9 if side else 0.0
    body = Dp - over
    cy = -side * over / 2
    p_box(r, "plinth", L - 0.3, body - 0.3, 0.33, "black", (0, cy, 0), bevel=0)
    p_box(r, "carcass", L - 0.1, body - 0.05, 2.42, "laminate_w", (0, cy, 0.33), bevel=0.005)
    _doors(r, L - 0.1, body, 0.36, 2.72, 2.55, cy - side * (body / 2 - 0.05) if side else -body / 2 + 0.05)
    p_box(r, "island_top", L, Dp, 0.15, "marble_top", (0, 0, 2.75), bevel=0.02)
    for k in (-1, 0, 1):            # pendants: a cord from the ceiling and a glowing shade over the top
        px = k * L / 3.2
        p_cyl(r, "pendant_cord", 0.015, 0.015, WALL_H - 6.6, "black", (px, 0, 6.6))
        p_cyl(r, "pendant_shade", 0.45, 0.2, 0.5, "black", (px, 0, 6.1), segs=32)
        p_cyl(r, "pendant_bulb", 0.3, 0.3, 0.04, "led", (px, 0, 6.08), segs=24)
    return done(r)


ART = [("art_terracotta", (0.62, 0.27, 0.16)), ("art_ochre", (0.78, 0.55, 0.18)), ("art_navy", (0.08, 0.13, 0.28)),
       ("art_sage", (0.45, 0.53, 0.42)), ("art_rose", (0.78, 0.52, 0.5)), ("art_charcoal", (0.12, 0.12, 0.13))]
for _n, _c in ART:
    mat(_n, _c, 0.85)
mat("art_ground", (0.86, 0.82, 0.74), 0.9)


def wall_mirror(x0, x1, y0, y1, front):
    """a full-length mirror in a thin brass frame, 0.4 to 6.6 ft up (dressing rooms, C1)"""
    along_x = front in ("-y", "+y")
    L, Dp = (x1 - x0, y1 - y0) if along_x else (y1 - y0, x1 - x0)
    rot = {"-y": 0, "+x": 90, "+y": 180, "-x": 270}[front]
    r = item("wall_mirror", (x0 + x1) / 2, (y0 + y1) / 2, rot)
    z0, h = 0.4, 6.2
    p_box(r, "mirror_frame", L, Dp, h, "brass", (0, 0, z0), bevel=0.01)
    p_box(r, "mirror", L - 0.12, 0.02, h - 0.12, "mirror", (0, -Dp / 2 - 0.006, z0 + 0.06), bevel=0)
    return r


def wall_art(x0, x1, y0, y1, front, seed=0):
    """a framed colour-field canvas on a wall, centred 5.3 ft up: two soft blocks of colour on a warm ground, from
    a fixed palette chosen by `seed` (the same house always gets the same pictures)"""
    along_x = front in ("-y", "+y")
    L, Dp = (x1 - x0, y1 - y0) if along_x else (y1 - y0, x1 - x0)
    rot = {"-y": 0, "+x": 90, "+y": 180, "-x": 270}[front]
    r = item("wall_art", (x0 + x1) / 2, (y0 + y1) / 2, rot)
    h = min(3.5, 0.75 * L)
    z0 = 5.3 - h / 2
    p_box(r, "art_frame", L, Dp, h, "teak", (0, 0, z0), bevel=0.01)
    face = -Dp / 2 - 0.004
    p_box(r, "art_canvas", L - 0.2, 0.01, h - 0.2, "art_ground", (0, face, z0 + 0.1), bevel=0)
    a, b = ART[seed % len(ART)][0], ART[(seed // len(ART) + 1 + seed) % len(ART)][0]
    if a == b:
        b = ART[(seed + 3) % len(ART)][0]
    inner_w, inner_h = L - 0.6, h - 0.6
    p_box(r, "art_block_top", inner_w, 0.01, inner_h * 0.55, a, (0, face - 0.005, z0 + 0.3 + inner_h * 0.45), bevel=0)
    p_box(r, "art_block_low", inner_w, 0.01, inner_h * 0.38, b, (0, face - 0.005, z0 + 0.3), bevel=0)
    return done(r, collide=False)


def bar_stool(x, y, rot):
    """a counter stool: round black seat on a chrome column and base, with a foot ring"""
    r = item("bar_stool", x, y, rot)
    p_cyl(r, "stool_base", 0.6, 0.55, 0.05, "chrome", (0, 0, 0), segs=32)
    p_cyl(r, "stool_column", 0.08, 0.08, 2.0, "chrome", (0, 0, 0.05), segs=16)
    p_cyl(r, "stool_ring", 0.5, 0.5, 0.04, "chrome", (0, 0, 0.9), segs=32)
    p_cyl(r, "stool_seat", 0.6, 0.62, 0.18, "black", (0, 0, 2.0), segs=32, bevel=0.03)
    return done(r, collide=False)


def wall_cab2(x0, x1, y0, y1, front, z0=4.9, z1=7.2):
    along_x = front in ("-y", "+y")
    L, Dp = (x1 - x0, y1 - y0) if along_x else (y1 - y0, x1 - x0)
    rot = {"-y": 0, "+x": 90, "+y": 180, "-x": 270}[front]
    r = item("wall_cabinet", (x0 + x1) / 2, (y0 + y1) / 2, rot)
    p_box(r, "wall_carcass", L, Dp - 0.05, z1 - z0, "laminate_w", (0, 0.025, z0), bevel=0.005)
    _doors(r, L, Dp, z0, z1, z0 + 0.55, -Dp / 2 + 0.05)
    p_box(r, "under_led", L - 0.2, 0.05, 0.02, "led", (0, -Dp / 2 + 0.3, z0 - 0.02), bevel=0)
    return done(r, collide=False)


def chimney(x, y, rot):
    """kitchen hood: steel pyramid + black glass skirt + flue box up to the ceiling."""
    r = item("chimney", x, y, rot)
    p_frustum(r, "hood", 2.5, 1.5, 0.95, 0.85, 0.9, "steel", (0, -0.6, 5.05), bevel=0.01)
    p_box(r, "hood_skirt", 2.5, 1.5, 0.2, "black_glass", (0, -0.6, 4.85), bevel=0.01)
    p_box(r, "flue", 0.9, 0.8, WALL_H - 5.9, "steel", (0, -0.55, 5.9), bevel=0.01)
    return done(r, collide=False)


def fridge2(x, y, rot):
    """brushed steel French-door fridge with a freezer drawer"""
    r = item("fridge", x, y, rot)
    p_box(r, "fridge_body", 2.3, 2.1, 5.8, "steel_brushed", (0, 0.05, 0), bevel=0.08, seg=3)
    p_box(r, "fridge_gap", 2.2, 0.05, 5.6, "black", (0, -1.0, 0.1), bevel=0)
    for s in (-1, 1):
        p_box(r, "fridge_door", 1.12, 0.14, 3.6, "steel_brushed", (s * 0.575, -1.05, 2.15), bevel=0.05, seg=3)
        p_tube(r, "fridge_handle", [(s * 0.1, -1.25, 2.9), (s * 0.1, -1.25, 5.0)], 0.04, "chrome")
    p_box(r, "freezer_drawer", 2.27, 0.14, 1.95, "steel_brushed", (0, -1.05, 0.15), bevel=0.05, seg=3)
    p_tube(r, "freezer_handle", [(-0.7, -1.25, 1.85), (0.7, -1.25, 1.85)], 0.04, "chrome")
    p_box(r, "fridge_display", 0.45, 0.02, 0.6, "black_glass", (-0.55, -1.13, 4.2), bevel=0.01)
    p_box(r, "fridge_led", 0.25, 0.01, 0.06, "led", (-0.55, -1.145, 4.55), bevel=0)
    return done(r)


def oven_stack(x, y, rot):
    """tall built-in housing (laminate) with a microwave over an oven and a warming drawer below, in black glass and
    steel: the oven tower of the reference kitchens (docs/reference/appliances/kitchen)"""
    r = item("oven_stack", x, y, rot)
    p_box(r, "tower_body", 2.0, 2.0, 7.2, "laminate_w", (0, 0.0, 0), bevel=0.01)
    fy = -1.02
    p_box(r, "warmer", 1.9, 0.06, 0.55, "black_glass", (0, fy, 1.0), bevel=0.02)
    p_box(r, "oven_door", 1.9, 0.08, 1.95, "black_glass", (0, fy, 1.7), bevel=0.02)
    p_box(r, "oven_window", 1.4, 0.02, 1.0, "glass", (0, fy - 0.05, 2.1), bevel=0.01)
    p_box(r, "oven_panel", 1.9, 0.08, 0.3, "steel_brushed", (0, fy, 3.65), bevel=0.01)
    p_box(r, "oven_display", 0.5, 0.01, 0.12, "led", (0, fy - 0.05, 3.74), bevel=0)
    p_tube(r, "oven_handle", [(-0.75, fy - 0.15, 3.45), (0.75, fy - 0.15, 3.45)], 0.04, "chrome")
    p_box(r, "micro_door", 1.9, 0.08, 1.15, "black_glass", (0, fy, 4.2), bevel=0.02)
    p_box(r, "micro_window", 1.25, 0.02, 0.7, "glass", (-0.2, fy - 0.05, 4.42), bevel=0.01)
    p_box(r, "micro_panel", 0.35, 0.02, 0.8, "steel_brushed", (0.72, fy - 0.05, 4.37), bevel=0.01)
    p_tube(r, "micro_handle", [(0.45, fy - 0.15, 4.35), (0.45, fy - 0.15, 5.15)], 0.035, "chrome")
    _doors(r, 2.0, 2.0, 5.55, 7.15, 5.8, -1.0, n=2)
    return done(r)


def washer2(x, y, rot):
    """front-loading washing machine: porthole door with a steel drum behind tinted glass, detergent drawer, dial"""
    r = item("washing_machine", x, y, rot)
    p_box(r, "wm_body", 2.0, 1.9, 2.75, "white_gloss", (0, 0, 0.05), bevel=0.1, seg=3)
    for sx in (-1, 1):
        for sy in (-1, 1):
            p_cyl(r, "wm_foot", 0.08, 0.08, 0.06, "black", (sx * 0.8, sy * 0.75, 0), segs=12)
    p_box(r, "wm_seam", 1.98, 0.02, 0.02, "plastic_white", (0, -0.955, 2.25), bevel=0)
    p_cyl(r, "wm_drum", 0.5, 0.5, 0.01, "steel_brushed", (0, -0.952, 1.2), rot=(90, 0, 0))
    p_cyl(r, "wm_drum_hub", 0.18, 0.18, 0.012, "cast_iron", (0, -0.958, 1.2), rot=(90, 0, 0), segs=24)
    p_torus(r, "wm_bezel", 0.6, 0.08, "plastic_white", (0, -0.97, 1.2), rot=(90, 0, 0))
    p_torus(r, "wm_ring", 0.52, 0.05, "chrome", (0, -1.03, 1.2), rot=(90, 0, 0))
    p_cyl(r, "wm_glass", 0.5, 0.42, 0.1, "glass", (0, -0.97, 1.2), rot=(90, 0, 0))
    p_box(r, "wm_handle", 0.1, 0.06, 0.35, "chrome", (0.52, -1.07, 1.05), bevel=0.02)
    p_box(r, "wm_drawer", 0.6, 0.04, 0.32, "plastic_white", (-0.6, -0.97, 2.32), bevel=0.02)
    p_box(r, "wm_drawer_grip", 0.3, 0.02, 0.05, "black", (-0.6, -0.995, 2.45), bevel=0)
    p_box(r, "wm_display", 0.45, 0.02, 0.22, "black_glass", (0.1, -0.965, 2.37), bevel=0.01)
    p_box(r, "wm_digits", 0.2, 0.01, 0.06, "led", (0.1, -0.978, 2.45), bevel=0)
    p_cyl(r, "wm_dial", 0.15, 0.13, 0.08, "chrome", (0.65, -0.95, 2.48), rot=(90, 0, 0), segs=24)
    return done(r)


def puja_mandir(x, y, rot, w=3.6):
    """wooden mandir unit: storage base, back panel, pillars and a stepped shikhara canopy."""
    r = item("mandir", x, y, rot)
    p_box(r, "mandir_base", w, 1.5, 2.4, "teak", (0, 0, 0), bevel=0.03)
    _doors(r, w, 1.5, 0.15, 2.3, 1.9, -0.75, n=2)
    p_box(r, "mandir_back", w, 0.15, 4.2, "teak", (0, 0.68, 2.4), bevel=0.02)
    p_box(r, "mandir_led", w - 0.4, 0.03, 3.6, "led", (0, 0.58, 2.6), bevel=0)
    for s in (-1, 1):
        p_cyl(r, "mandir_pillar", 0.1, 0.1, 3.6, "brass", (s * (w / 2 - 0.2), -0.55, 2.4))
    p_box(r, "mandir_lintel", w + 0.1, 1.5, 0.25, "teak", (0, 0, 6.0), bevel=0.03)
    for k, f in enumerate((0.88, 0.72, 0.55)):
        p_box(r, "mandir_step", w * f, 1.2, 0.25, "teak", (0, 0.05, 6.25 + 0.25 * k), bevel=0.02)
    p_cyl(r, "shikhara", w * 0.26, 0.08, 1.4, "brass", (0, 0.05, 7.0), segs=8)
    return done(r)

