"""The house style for the asset library: materials, light rigs, colour management and shape helpers, ported from the
team's "Lantern house" handover (docs/reference/style/villa_look_handover, team-made and procedural). The values
(colours, strengths, temperatures, roughness, pitches) are the handover's defaults; the code is ours and works for any
size. Units are metres, Z up. Blender 5.3 (bpy) only: no images, no add-ons.

    import style; M = style.Materials()      # every material by name, made on first use
    style.room_light(...), style.washer(...), style.cove(...), style.downlights(...), style.colour_management(scene, ...)
"""
import math

import bpy
from mathutils import Vector


# ------------------------------------------------------------------ colour
def srgb(h):
    """'#rrggbb' -> linear RGB (Blender shader colours are linear)"""
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def rgba(h, a=1.0):
    return (*srgb(h), a)


def scaled(h, k):
    return (*[min(1.0, c * k) for c in srgb(h)], 1.0)


# ------------------------------------------------------------------ node building
class Nodes:
    """a small helper over a material's node tree"""

    def __init__(self, mat):
        mat.use_nodes = True
        self.t = mat.node_tree
        self.t.nodes.clear()

    def new(self, kind, **props):
        n = self.t.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, a, b):
        self.t.links.new(a, b)

    def set(self, node, name, value):
        node.inputs[name].default_value = value

    def put(self, node, name, v):
        if hasattr(v, "node"):
            self.link(v, node.inputs[name])
        else:
            node.inputs[name].default_value = v

    def pos(self):
        return self.new("ShaderNodeTexCoord").outputs["Object"]

    def xyz(self, v):
        s = self.new("ShaderNodeSeparateXYZ")
        self.link(v, s.inputs[0])
        return s.outputs

    def vec(self, x=0.0, y=0.0, z=0.0):
        c = self.new("ShaderNodeCombineXYZ")
        for i, v in enumerate((x, y, z)):
            self.put(c, i, v) if hasattr(v, "node") else self.set(c, i, v)
        return c.outputs[0]

    def scale(self, v, s):
        m = self.new("ShaderNodeMapping")
        self.set(m, "Scale", s)
        self.link(v, m.inputs["Vector"])
        return m.outputs["Vector"]

    def noise(self, v, scale, detail=3.0, rough=0.5):
        n = self.new("ShaderNodeTexNoise")
        self.set(n, "Scale", scale)
        self.set(n, "Detail", detail)
        self.set(n, "Roughness", rough)
        self.link(v, n.inputs["Vector"])
        return n.outputs["Fac"]

    def ramp(self, fac, stops):
        r = self.new("ShaderNodeValToRGB")
        els = r.color_ramp.elements
        while len(els) < len(stops):
            els.new(0.5)
        for el, (p, c) in zip(els, stops):
            el.position = p
            el.color = (c, c, c, 1) if isinstance(c, (int, float)) else c
        self.link(fac, r.inputs["Fac"])
        return r.outputs["Color"]

    def math(self, op, a, b=None):
        m = self.new("ShaderNodeMath", operation=op)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if hasattr(v, "node"):
                self.link(v, m.inputs[i])
            else:
                m.inputs[i].default_value = v
        return m.outputs[0]

    def mix(self, fac, a, b, blend="MIX"):
        m = self.new("ShaderNodeMix", data_type="RGBA", blend_type=blend)
        f = [s for s in m.inputs if s.type == "VALUE"][0]
        ca, cb = [s for s in m.inputs if s.type == "RGBA"][:2]
        for s, v in ((f, fac), (ca, a), (cb, b)):
            self.link(v, s) if hasattr(v, "node") else setattr(s, "default_value", v)
        return [s for s in m.outputs if s.type == "RGBA"][0]

    def bump(self, h, strength, distance, normal=None):
        b = self.new("ShaderNodeBump")
        self.set(b, "Strength", strength)
        self.set(b, "Distance", distance)
        self.link(h, b.inputs["Height"])
        if normal is not None:
            self.link(normal, b.inputs["Normal"])
        return b.outputs["Normal"]

    def brick(self, v, width, height, mortar, c1=0.86, mortar_c=0.25, smooth=0.2):
        b = self.new("ShaderNodeTexBrick")
        b.offset = 0.5
        for k, val in (("Scale", 1.0), ("Brick Width", width), ("Row Height", height), ("Mortar Size", mortar),
                       ("Mortar Smooth", smooth), ("Bias", 0.0), ("Color1", (c1, c1, c1, 1)), ("Color2", (1, 1, 1, 1)),
                       ("Mortar", (mortar_c, mortar_c, mortar_c, 1))):
            self.set(b, k, val)
        self.link(v, b.inputs["Vector"])
        return b

    def principled(self, color, rough=0.5, metallic=0.0):
        p = self.new("ShaderNodeBsdfPrincipled")
        self.put(p, "Base Color", color)
        self.put(p, "Roughness", rough)
        self.set(p, "Metallic", metallic)
        return p

    def out(self, shader):
        o = self.new("ShaderNodeOutputMaterial")
        self.link(shader, o.inputs["Surface"])


# ------------------------------------------------------------------ materials (handover values as defaults)
def _new(name):
    m = bpy.data.materials.new(name)
    return m, Nodes(m)


def mat_simple(name, color, rough=0.5, metallic=0.0, bump_scale=None, bump=0.15):
    m, t = _new(name)
    p = t.principled(rgba(color), rough, metallic)
    if bump_scale:
        t.link(t.bump(t.noise(t.pos(), bump_scale, 4, 0.6), bump, 0.01), p.inputs["Normal"])
    t.out(p.outputs[0])
    return m


def mat_tiles(name, base, dark, light, panel=(1.2, 0.6), wall=True, rough=0.62, joint=0.004, joint_c=0.25,
              veins=0.18, vein_scale=2.2):
    """stone or porcelain cladding in panels with thin joints (the handover's Limestone recipe, generalised):
    two noise layers vary the colour, a third varies the roughness per panel; wall=True lays joints on walls"""
    m, t = _new(name)
    pos = t.pos()
    x, y, z = t.xyz(pos)
    uv = t.vec(t.math("ADD", x, y), z) if wall else t.vec(x, y)
    br = t.brick(uv, panel[0], panel[1], joint, mortar_c=joint_c)
    cloud = t.noise(pos, 0.55, 5, 0.55)
    vein = t.noise(t.scale(pos, (0.6, 0.6, 5.0)), vein_scale, 6, 0.65)
    col = t.ramp(cloud, [(0.3, rgba(dark)), (0.5, rgba(base)), (0.72, rgba(light))])
    col = t.mix(t.math("MULTIPLY", t.ramp(vein, [(0.45, 0.0), (0.62, 1.0)]), veins), col, rgba(dark))
    col = t.mix(1.0, col, br.outputs["Color"], "MULTIPLY")
    p = t.principled(col, rough)
    t.put(p, "Roughness", t.math("ADD", t.math("MULTIPLY", t.noise(pos, 3.0, 3, 0.5), 0.25), rough - 0.12))
    n1 = t.bump(t.noise(pos, 60.0, 3, 0.6), 0.12, 0.004)
    t.link(t.bump(t.math("SUBTRACT", 1.0, br.outputs["Fac"]), 0.5, 0.004, n1), p.inputs["Normal"])
    t.out(p.outputs[0])
    return m


def mat_floor_slabs(name, base="#b7ab95", slab=1.2, rough=0.24, dark="#a19580", light="#c8bda8"):
    """large honed floor slabs, reflective enough to carry the lights (the handover's Paving)"""
    m, t = _new(name)
    pos = t.pos()
    x, y, _ = t.xyz(pos)
    br = t.brick(t.vec(x, y), slab * 2, slab, 0.005, c1=0.84, mortar_c=0.18, smooth=0.1)
    col = t.ramp(t.noise(pos, 0.9, 5, 0.6), [(0.3, rgba(dark)), (0.55, rgba(base)), (0.8, rgba(light))])
    p = t.principled(t.mix(1.0, col, br.outputs["Color"], "MULTIPLY"), rough)
    t.put(p, "Roughness", t.math("ADD", t.math("MULTIPLY", t.noise(pos, 1.7, 4, 0.6), 0.3), rough - 0.1))
    n1 = t.bump(t.noise(pos, 30.0, 3, 0.6), 0.05, 0.003)
    t.link(t.bump(t.math("SUBTRACT", 1.0, br.outputs["Fac"]), 0.5, 0.004, n1), p.inputs["Normal"])
    t.out(p.outputs[0])
    return m


def mat_concrete(name="Concrete", base="#8d8a84"):
    m, t = _new(name)
    pos = t.pos()
    col = t.ramp(t.noise(pos, 0.8, 5, 0.6), [(0.3, rgba("#7c7973")), (0.55, rgba(base)), (0.8, rgba("#9c9992"))])
    stain = t.noise(t.scale(pos, (3.0, 3.0, 0.35)), 1.6, 4, 0.6)
    col = t.mix(t.math("MULTIPLY", t.ramp(stain, [(0.5, 0.0), (0.75, 1.0)]), 0.22), col, rgba("#6b6862"))
    w = t.new("ShaderNodeTexWave", wave_type="BANDS", bands_direction="Z", wave_profile="SAW")
    t.set(w, "Scale", 1.3)
    t.set(w, "Distortion", 0.4)
    t.link(pos, w.inputs["Vector"])
    p = t.principled(col, 0.72)
    t.link(t.bump(w.outputs["Fac"], 0.25, 0.004, t.bump(t.noise(pos, 45.0, 3, 0.6), 0.15, 0.004)), p.inputs["Normal"])
    t.out(p.outputs[0])
    return m


def mat_metal(name, color, rough=0.24, var=0.2, var_scale=9.0):
    """brass / copper / bronze / chrome: metallic, roughness broken up by noise"""
    m, t = _new(name)
    p = t.principled(rgba(color), rough, 1.0)
    t.put(p, "Roughness", t.math("ADD", t.math("MULTIPLY", t.noise(t.pos(), var_scale, 3, 0.5), var), rough))
    t.out(p.outputs[0])
    return m


def mat_glass(name="Glass", tint="#eef4f2"):
    """clear straight through, a mirror weighted by Fresnel (not refractive: fast and clear)"""
    m, t = _new(name)
    fr = t.new("ShaderNodeFresnel")
    t.set(fr, "IOR", 1.5)
    tr = t.new("ShaderNodeBsdfTransparent")
    t.set(tr, "Color", rgba(tint))
    rf = t.principled((1, 1, 1, 1), 0.0, 1.0)
    mx = t.new("ShaderNodeMixShader")
    t.link(fr.outputs[0], mx.inputs[0])
    t.link(tr.outputs[0], mx.inputs[1])
    t.link(rf.outputs[0], mx.inputs[2])
    t.out(mx.outputs[0])
    m.blend_method = "BLEND" if hasattr(m, "blend_method") else None
    return m


def mat_fluted_glass(name="FlutedGlass", ribs_per_m=45.0, axis="Y"):
    """ribbed (fluted) glass: lets light through, blurs what is behind it"""
    m, t = _new(name)
    p = t.principled((0.9, 0.95, 0.93, 1), 0.08)
    t.set(p, "Transmission Weight", 1.0)
    t.set(p, "IOR", 1.48)
    x, y, _ = t.xyz(t.pos())
    ribs = t.math("SINE", t.math("MULTIPLY", y if axis == "Y" else x, ribs_per_m * 2 * math.pi))
    t.link(t.bump(ribs, 1.0, 0.02), p.inputs["Normal"])
    t.out(p.outputs[0])
    return m


def mat_screen(name="Screen", pitch=0.24, base="#cbb999", axis="X"):
    """perforated stone lattice (jaali / mashrabiya): diamond openings with small squares between, cut in the shader
    so light passes through. axis = the horizontal direction the screen runs along"""
    m, t = _new(name)
    pos = t.pos()
    x, y, z = t.xyz(pos)
    u, v = t.math("DIVIDE", x if axis == "X" else y, pitch), t.math("DIVIDE", z, pitch)

    def cell(val, shift=0.0):
        return t.math("ABSOLUTE", t.math("SUBTRACT", t.math("FRACT", t.math("ADD", val, shift)), 0.5))

    hole = t.math("MAXIMUM", t.math("LESS_THAN", t.math("ADD", cell(u), cell(v)), 0.33),
                  t.math("LESS_THAN", t.math("MAXIMUM", cell(u, 0.5), cell(v, 0.5)), 0.085))
    col = t.ramp(t.noise(pos, 0.7, 4, 0.55), [(0.3, rgba("#b4a07f")), (0.55, rgba(base)), (0.8, rgba("#d9cab0"))])
    p = t.principled(col, 0.6)
    t.link(t.bump(t.noise(pos, 50.0, 3, 0.6), 0.12, 0.004), p.inputs["Normal"])
    tr = t.new("ShaderNodeBsdfTransparent")
    mx = t.new("ShaderNodeMixShader")
    t.link(hole, mx.inputs[0])
    t.link(p.outputs[0], mx.inputs[1])
    t.link(tr.outputs[0], mx.inputs[2])
    t.out(mx.outputs[0])
    return m


def mat_water(name="Water", color="#04090c", ripple=0.075, scale=2.6):
    """the handover's still water ("MirrorWater"), or with a body colour ("Water", "PoolWater"): the colour of the
    water body and what is under it, so water reads as water by day, by evening and in a colour bake (the browser
    model), with the sharp rippled reflection on top. The handover's near-black value only works as a mirror for a
    lit house across it; in a small view it reads as a hole."""
    m, t = _new(name)
    pos = t.pos()
    p = t.principled(rgba(color), 0.015)
    t.set(p, "IOR", 1.33)
    h = t.math("ADD", t.noise(t.scale(pos, (1.0, 0.45, 1.0)), scale, 3, 0.55),
               t.math("MULTIPLY", t.noise(pos, scale * 6, 2, 0.5), 0.25))
    t.link(t.bump(h, ripple, 0.1), p.inputs["Normal"])
    t.out(p.outputs[0])
    return m


def mat_emit(name, kelvin=2900, strength=10.0):
    """a light-emitting surface: Blackbody colour (cove 3100 K / 34, downlight 3000 K / 30, bulb 2700 K / 120,
    shade 2700 K / 14, lantern 2500 K / 22 in the handover)"""
    m, t = _new(name)
    bb = t.new("ShaderNodeBlackbody")
    t.set(bb, "Temperature", kelvin)
    e = t.new("ShaderNodeEmission")
    t.link(bb.outputs[0], e.inputs["Color"])
    t.set(e, "Strength", strength)
    t.out(e.outputs[0])
    return m


def mat_fabric(name, color, rough=0.9, scale=220.0):
    m, t = _new(name)
    pos = t.pos()
    weave = t.noise(t.scale(pos, (1.0, 1.0, 0.25)), scale, 2, 0.5)
    col = t.mix(t.math("MULTIPLY", t.noise(pos, 3.0, 3, 0.5), 0.25), rgba(color), scaled(color, 0.8))
    p = t.principled(col, rough)
    t.set(p, "Sheen Weight", 0.35)
    t.link(t.bump(weave, 0.25, 0.002), p.inputs["Normal"])
    t.out(p.outputs[0])
    return m


def mat_wood(name, base="#5c3d27", dark="#3e2818", rough=0.42, axis="X"):
    m, t = _new(name)
    stretch = {"X": (0.6, 14.0, 14.0), "Y": (14.0, 0.6, 14.0), "Z": (14.0, 14.0, 0.6)}[axis]
    grain = t.noise(t.scale(t.pos(), stretch), 3.0, 6, 0.6)
    p = t.principled(t.ramp(grain, [(0.3, rgba(dark)), (0.6, rgba(base)), (0.8, scaled(base, 1.35))]), rough)
    t.link(t.bump(grain, 0.08, 0.002), p.inputs["Normal"])
    t.out(p.outputs[0])
    return m


def mat_planks(name, base="#a98558", dark="#8a6a43", width=0.14, rough=0.4):
    """floor boards or decking: long planks with thin gaps and a colour per plank"""
    m, t = _new(name)
    pos = t.pos()
    x, y, _ = t.xyz(pos)
    br = t.brick(t.vec(x, y), width * 14, width, 0.0025, c1=0.8, mortar_c=0.15, smooth=0.05)
    grain = t.noise(t.scale(pos, (0.5, 12.0, 12.0)), 3.0, 6, 0.6)
    col = t.ramp(grain, [(0.3, rgba(dark)), (0.6, rgba(base)), (0.85, scaled(base, 1.25))])
    p = t.principled(t.mix(1.0, col, br.outputs["Color"], "MULTIPLY"), rough)
    t.link(t.bump(t.math("SUBTRACT", 1.0, br.outputs["Fac"]), 0.4, 0.003, t.bump(grain, 0.06, 0.002)), p.inputs["Normal"])
    t.out(p.outputs[0])
    return m


def mat_marble(name, base="#f1ede6", vein="#9a948a", vein_amount=0.55, rough=0.12, scale=1.4):
    """polished marble: a warped noise turned into thin veins over a soft ground"""
    m, t = _new(name)
    pos = t.pos()
    warp = t.noise(pos, scale, 8, 0.7)
    v = t.math("ABSOLUTE", t.math("SUBTRACT", t.math("FRACT", t.math("MULTIPLY", warp, 6.0)), 0.5))
    veins = t.ramp(v, [(0.0, 1.0), (0.06, 0.0)])
    col = t.mix(t.math("MULTIPLY", t.mix(1.0, veins, (1, 1, 1, 1), "MULTIPLY"), vein_amount), rgba(base), rgba(vein))
    p = t.principled(col, rough)
    t.out(p.outputs[0])
    return m


def mat_terrazzo(name="Terrazzo", base="#e7e0d4", chips=("#b9a68a", "#6d6a64", "#d8c7ad"), rough=0.3):
    m, t = _new(name)
    pos = t.pos()
    col = rgba(base)
    for k, c in enumerate(chips):
        vo = t.new("ShaderNodeTexVoronoi")
        t.set(vo, "Scale", 22.0 + 9 * k)
        t.link(t.scale(pos, (1, 1, 1)), vo.inputs["Vector"])
        dot = t.math("LESS_THAN", vo.outputs["Distance"], 0.16)
        col = t.mix(dot, col, rgba(c))
    t.out(t.principled(col, rough).outputs[0])
    return m


def mat_leaf(name, top, rough=0.45, translucent=0.35):
    m, t = _new(name)
    col = t.mix(t.noise(t.pos(), 1.3, 2, 0.5), scaled(top, 0.7), rgba(top))
    p = t.principled(col, rough)
    tl = t.new("ShaderNodeBsdfTranslucent")
    t.link(col, tl.inputs["Color"])
    mx = t.new("ShaderNodeMixShader")
    mx.inputs[0].default_value = translucent
    t.link(p.outputs[0], mx.inputs[1])
    t.link(tl.outputs[0], mx.inputs[2])
    t.out(mx.outputs[0])
    return m


def mat_gravel(name="Gravel", base="#8f8674"):
    m, t = _new(name)
    pos = t.pos()
    vo = t.new("ShaderNodeTexVoronoi")
    t.set(vo, "Scale", 55.0)
    t.link(pos, vo.inputs["Vector"])
    p = t.principled(t.mix(t.noise(pos, 40.0, 2, 0.5), scaled(base, 0.6), scaled(base, 1.25)), 0.85)
    t.link(t.bump(vo.outputs["Distance"], 0.8, 0.02), p.inputs["Normal"])
    t.out(p.outputs[0])
    return m


def mat_art(name, palette, seed=0):
    """an abstract canvas: soft layered colour fields with a canvas-weave bump"""
    m, t = _new(name)
    pos = t.pos()
    shift = t.new("ShaderNodeMapping")
    t.set(shift, "Location", (seed * 3.1, seed * 1.7, seed * 2.3))
    t.link(pos, shift.inputs["Vector"])
    f = t.noise(shift.outputs[0], 1.6, 4, 0.55)
    stops = [(i / max(1, len(palette) - 1) * 0.6 + 0.2, rgba(c)) for i, c in enumerate(palette)]
    p = t.principled(t.ramp(f, stops), 0.8)
    t.link(t.bump(t.noise(pos, 260.0, 2, 0.5), 0.15, 0.001), p.inputs["Normal"])
    t.out(p.outputs[0])
    return m


# the library's material set: the handover's values first, then the additions asked for
RECIPES = {
    # handover
    "Limestone": lambda n: mat_tiles(n, "#cdbb9d", "#b39f7f", "#dccdb2"),
    "DarkStone": lambda n: mat_tiles(n, "#8e8473", "#766c5c", "#a0968a"),
    "Paving": lambda n: mat_floor_slabs(n),
    "Plaster": lambda n: mat_simple(n, "#efe5d3", 0.85, bump_scale=40, bump=0.05),
    "Ceiling": lambda n: mat_simple(n, "#f3ede2", 0.9),
    "Concrete": lambda n: mat_concrete(n),
    "Walnut": lambda n: mat_wood(n, "#5c3d27", "#3e2818", 0.42),
    "Oak": lambda n: mat_wood(n, "#a98558", "#8a6a43", 0.5),
    "FloorOak": lambda n: mat_planks(n, "#a98558", "#8a6a43", 0.14, 0.4),
    "Deck": lambda n: mat_planks(n, "#7d6046", "#5e4632", 0.14, 0.55),
    "Glass": lambda n: mat_glass(n),
    "FlutedGlass": lambda n: mat_fluted_glass(n),
    "Brass": lambda n: mat_metal(n, "#b08d57", 0.24),
    "Bronze": lambda n: mat_metal(n, "#4b3a27", 0.26, 0.2, 6.0),
    "DarkMetal": lambda n: mat_metal(n, "#1c1a18", 0.5, 0.05),
    "Chrome": lambda n: mat_metal(n, "#f2f4f4", 0.04, 0.02),
    "Mirror": lambda n: mat_metal(n, "#f2f4f4", 0.0, 0.0),
    "Linen": lambda n: mat_fabric(n, "#d9cfbc"),
    "LinenWhite": lambda n: mat_fabric(n, "#ece6d9"),
    "Clay": lambda n: mat_fabric(n, "#a8644a"),
    "Sage": lambda n: mat_fabric(n, "#8d957c"),
    "Charcoal": lambda n: mat_fabric(n, "#4a4a47"),
    "Rug": lambda n: mat_fabric(n, "#cbbfa8", scale=90.0),
    "Towel": lambda n: mat_fabric(n, "#ece6d9", scale=60.0),
    "Leather": lambda n: mat_simple(n, "#8a5a36", 0.42, bump_scale=120, bump=0.08),
    "Curtain": lambda n: mat_leaf(n, "#e6dcc8", 0.85, 0.45),
    "Ceramic": lambda n: mat_simple(n, "#ece6dc", 0.3),
    "CeramicDark": lambda n: mat_simple(n, "#3a3734", 0.38),
    "Screen": lambda n: mat_screen(n),
    "Water": lambda n: mat_water(n, "#1c4643"),             # a pond, a fountain: deep green-teal
    "PoolWater": lambda n: mat_water(n, "#3f9db0", 0.05),  # a pool over pale tile
    "MirrorWater": lambda n: mat_water(n),                 # the handover's dark mirror (hero shots across water)
    "OliveLeaf": lambda n: mat_leaf(n, "#6f7d58", 0.45, 0.3),
    "PalmLeaf": lambda n: mat_leaf(n, "#3f5a2e", 0.45, 0.3),
    "Bark": lambda n: mat_simple(n, "#4a3d30", 0.9, bump_scale=8, bump=0.8),
    "Gravel": lambda n: mat_gravel(n),
    "Cove": lambda n: mat_emit(n, 3100, 34),
    "CoveSoft": lambda n: mat_emit(n, 3100, 12),
    "Downlight": lambda n: mat_emit(n, 3000, 30),
    "Bulb": lambda n: mat_emit(n, 2700, 120),
    "Shade": lambda n: mat_emit(n, 2700, 14),
    "Lantern": lambda n: mat_emit(n, 2500, 22),
    "MirrorRing": lambda n: mat_emit(n, 3000, 16),
    "Art1": lambda n: mat_art(n, ("#e9e1d3", "#a8644a", "#5d6a5c"), 1),
    "Art2": lambda n: mat_art(n, ("#efe7da", "#8d957c", "#3b4b5e"), 2),
    "Art3": lambda n: mat_art(n, ("#f2ebdf", "#c9a46a", "#7a4b38"), 3),
    # additions
    "LimestoneBeige": lambda n: mat_tiles(n, "#d8c8a8", "#c2b08e", "#e6d9bf", panel=(0.9, 0.45)),
    "MarbleWhite": lambda n: mat_marble(n, "#f3f0ea", "#a7a29a", 0.5),
    "MarbleCream": lambda n: mat_marble(n, "#ece2cf", "#b49d78", 0.45),
    "MarbleVeined": lambda n: mat_marble(n, "#eeeae4", "#4d4a46", 0.75, scale=1.0),
    "Porcelain": lambda n: mat_floor_slabs(n, "#ddd6ca", slab=1.2, rough=0.18, dark="#d0c8bb", light="#e8e2d8"),
    "Terrazzo": lambda n: mat_terrazzo(n),
    "OutdoorStone": lambda n: mat_floor_slabs(n, "#a99c86", slab=0.6, rough=0.6, dark="#94887a", light="#bcae96"),
    "Grass": lambda n: mat_leaf(n, "#5b6e3d", 0.8, 0.15),
    "Velvet": lambda n: mat_fabric(n, "#5a4a5e", 0.75, 300.0),
    "WhiteLacquer": lambda n: mat_simple(n, "#f2efe9", 0.25),
    "PoolTile": lambda n: mat_tiles(n, "#7fb6c8", "#6aa3b6", "#94c5d4", panel=(0.1, 0.1), wall=True, rough=0.2, joint=0.01, joint_c=0.8, veins=0.0),
}


class Materials(dict):
    """materials by name, made on first use"""

    def __missing__(self, name):
        if name not in RECIPES:
            raise KeyError(f"no recipe for material {name!r}")
        m = bpy.data.materials.get(name) or RECIPES[name](name)
        self[name] = m
        return m


# ------------------------------------------------------------------ meshes
def link(ob, coll=None):
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def mesh(name, verts, faces, mat=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    if mat is not None:
        me.materials.append(mat)
    return link(ob)


def box(name, x, y, z, mat=None, bevel=0.0):
    """an axis-aligned box from ranges x=(x0, x1), y=(y0, y1), z=(z0, z1)"""
    (x0, x1), (y0, y1), (z0, z1) = x, y, z
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    ob = mesh(name, v, f, mat)
    if bevel > 0:
        md = ob.modifiers.new("bevel", "BEVEL")
        md.width, md.segments, md.limit_method = bevel, 2, "ANGLE"
    return ob


def soft_box(name, x, y, z, mat=None, r=0.04, levels=2):
    """an upholstered block: rounded by bevel plus subdivision"""
    ob = box(name, x, y, z, mat)
    b = ob.modifiers.new("bevel", "BEVEL")
    b.width, b.segments, b.limit_method = r, 3, "ANGLE"
    s = ob.modifiers.new("subd", "SUBSURF")
    s.levels = s.render_levels = levels if levels else 1
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def lathe(name, center, profile, mat=None, segs=32, smooth=True):
    """a surface of revolution about the vertical axis; profile [(radius, height), ...] bottom to top"""
    cx, cy, cz = center
    verts, faces = [], []
    n = len(profile)
    for k in range(segs):
        a = 2 * math.pi * k / segs
        for r, h in profile:
            verts.append((cx + r * math.cos(a), cy + r * math.sin(a), cz + h))
    for k in range(segs):
        k2 = (k + 1) % segs
        for i in range(n - 1):
            faces.append((k * n + i, k2 * n + i, k2 * n + i + 1, k * n + i + 1))
    return mesh(name, verts, faces, mat, smooth)


def rod(name, p0, p1, r, mat=None, sides=12):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    q = d.to_track_quat("Z", "Y")
    verts, faces = [], []
    for k in range(sides):
        a = 2 * math.pi * k / sides
        off = q @ Vector((r * math.cos(a), r * math.sin(a), 0))
        verts += [tuple(p0 + off), tuple(p1 + off)]
    for k in range(sides):
        k2 = (k + 1) % sides
        faces.append((2 * k, 2 * k2, 2 * k2 + 1, 2 * k + 1))
    return mesh(name, verts, faces, mat, True)


def disc(name, center, r, mat=None, segs=24):
    cx, cy, cz = center
    verts = [(cx + r * math.cos(2 * math.pi * k / segs), cy + r * math.sin(2 * math.pi * k / segs), cz) for k in range(segs)]
    return mesh(name, verts, [tuple(range(segs))], mat)


def pillow(name, center, size, mat=None, rot_z=0.0):
    """a plump cushion: a flattened subdivided box"""
    cx, cy, cz = center
    w, d, h = size
    ob = soft_box(name, (cx - w / 2, cx + w / 2), (cy - d / 2, cy + d / 2), (cz - h / 2, cz + h / 2), mat, r=min(w, d, h) * 0.45, levels=2)
    ob.rotation_euler[2] = rot_z
    return ob


def curtain(name, x, z, y, mat=None, waves_per_m=4.0, depth=0.06):
    """a pleated sheet facing -Y between x=(x0, x1) and z=(z0, z1) at y"""
    (x0, x1), (z0, z1) = x, z
    n = max(8, int((x1 - x0) * waves_per_m * 8))
    verts, faces = [], []
    for i in range(n + 1):
        u = x0 + (x1 - x0) * i / n
        dy = depth * math.sin(2 * math.pi * waves_per_m * (u - x0))
        verts += [(u, y + dy, z0), (u, y + dy, z1)]
    for i in range(n):
        faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    return mesh(name, verts, faces, mat, True)


def potted_plant(name, at, M, h=1.1, leaves=400, seed=1):
    """a planter with a bushy olive-like crown: a lathe pot, a stem and leaf quads scattered round the crown.
    leaves sets the detail (render: 2000+, browser: a few hundred)"""
    import random
    rnd = random.Random(seed)
    x, y, z = at
    pot_h = 0.32 * h
    parts = [lathe(f"{name}_pot", (x, y, z), [(0.0, 0.0), (0.16 * h, 0.0), (0.2 * h, pot_h * 0.85), (0.19 * h, pot_h), (0.0, pot_h)], M["Ceramic"]),
             rod(f"{name}_stem", (x, y, z + pot_h), (x, y, z + h * 0.62), 0.012 * h, M["Bark"])]
    cz, rad = z + h * 0.72, h * 0.28
    verts, faces = [], []
    for k in range(leaves):
        u, v = rnd.uniform(-1, 1), rnd.uniform(0, 2 * math.pi)
        rr = rad * rnd.uniform(0.35, 1.0)
        px, py, pz = x + rr * math.sqrt(1 - u * u) * math.cos(v), y + rr * math.sqrt(1 - u * u) * math.sin(v), cz + rr * u * 0.8
        a, s = rnd.uniform(0, math.pi), 0.035 * h
        b = len(verts)
        verts += [(px, py, pz), (px + s * math.cos(a), py + s * math.sin(a), pz + s * 0.3),
                  (px + s * 1.6 * math.cos(a + 0.2), py + s * 1.6 * math.sin(a + 0.2), pz + s * 0.15)]
        faces.append((b, b + 1, b + 2))
    parts.append(mesh(f"{name}_leaves", verts, faces, M["OliveLeaf"]))
    return parts


# ------------------------------------------------------------------ lights (handover rigs)
def _light(name, kind, loc, watts, color, **props):
    data = bpy.data.lights.new(name, kind)
    data.energy = watts
    data.color = color
    for k, v in props.items():
        setattr(data, k, v)
    ob = link(bpy.data.objects.new(name, data))
    ob.location = loc
    ob.visible_camera = False
    return ob


WARM = (1.0, 0.8, 0.62)         # ≈ 5000 K in the handover's room lights; evening rigs use the warmer ones below
EVENING = (1.0, 0.72, 0.47)     # ≈ 3000 K
WASH = (1.0, 0.62, 0.33)        # ≈ 3800 K wall washers and uplights (as in the handover)
DAYLIGHT = (1.0, 0.97, 0.94)


def room_light(name, loc, size, watts, M, color=WARM):
    """a soft ceiling light: lights the room, unseen directly and in reflections; a small glowing disc marks it"""
    ob = _light(name, "AREA", loc, watts, color, shape="RECTANGLE", size=size[0], size_y=size[1])
    ob.visible_glossy = False
    disc(f"{name}_fitting", (loc[0], loc[1], loc[2] + 0.04), 0.06, M["Downlight"])
    return ob


def washer(name, at, toward, watts, M, cone=62.0, color=WASH):
    """a recessed downlight grazing a wall (spot, 3 cm radius) with its visible disc"""
    ob = _light(name, "SPOT", at, watts, color, spot_size=math.radians(cone), spot_blend=0.6, shadow_soft_size=0.03)
    ob.rotation_euler = (Vector(toward) - Vector(at)).to_track_quat("-Z", "Y").to_euler()
    disc(f"{name}_disc", (at[0], at[1], at[2] + 0.01), 0.045, M["Downlight"])
    return ob


def cove(name, x, y, z, M, soft=False):
    """a cove strip hidden in a ceiling recess: an emissive bar (Cove 3100 K / 34, CoveSoft 12)"""
    return box(name, x, y, z, M["CoveSoft" if soft else "Cove"])


def downlights(name, x0, x1, y0, y1, ceiling, M, step=1.6, watts=18.0, color=EVENING):
    """recessed downlights on a grid about `step` m apart: spot lights with a visible disc each"""
    nx, ny = max(1, round((x1 - x0) / step)), max(1, round((y1 - y0) / step))
    out = []
    for i in range(nx):
        for j in range(ny):
            cx, cy = x0 + (i + 0.5) * (x1 - x0) / nx, y0 + (j + 0.5) * (y1 - y0) / ny
            ob = _light(f"{name}_{i}_{j}", "SPOT", (cx, cy, ceiling - 0.02), watts, color, spot_size=math.radians(70),
                        spot_blend=0.5, shadow_soft_size=0.03)
            disc(f"{name}_{i}_{j}_disc", (cx, cy, ceiling - 0.005), 0.05, M["Downlight"])
            out.append(ob)
    return out


def colour_management(scene, exposure=-0.1, kelvin=4700.0):
    """the handover's look: AgX, Medium High Contrast, per-shot exposure and white balance"""
    vs = scene.view_settings
    vs.view_transform = "AgX"
    vs.look = "AgX - Medium High Contrast"
    vs.exposure = exposure
    vs.gamma = 1.0
    if kelvin and hasattr(vs, "use_white_balance"):
        vs.use_white_balance = True
        vs.white_balance_temperature = kelvin


def cycles(scene, samples=72, res=(1920, 1080), device="GPU"):
    """the handover's Cycles settings (adaptive 0.02, OIDN, bounces 8/4/4/8/24, clamp indirect 6, Blackman-Harris)"""
    scene.render.engine = "CYCLES"
    c = scene.cycles
    c.samples, c.use_adaptive_sampling, c.adaptive_threshold = samples, True, 0.02
    c.use_denoising = True
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces, c.transmission_bounces, c.transparent_max_bounces = 8, 4, 4, 8, 24
    c.caustics_reflective = c.caustics_refractive = False
    c.sample_clamp_indirect, c.sample_clamp_direct = 6.0, 0.0
    c.pixel_filter_type, c.filter_width = "BLACKMAN_HARRIS", 1.5
    scene.render.resolution_x, scene.render.resolution_y = res
    if device == "GPU":
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("METAL", "OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                if any(d.type == kind for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = d.type == kind
                    c.device = "GPU"
                    break
            except (TypeError, ValueError):
                continue


def day_sky(scene, strength=1.0, sun_deg=(52.0, 0.0, 35.0), sun=3.2):
    """the day preset: a pale-blue sky gradient over warm ground and a sun lamp (5600 K-ish), elevation and azimuth
    in degrees; pair with colour_management(scene, -0.45, 5600)"""
    import math
    w = scene.world or bpy.data.worlds.new("World")
    scene.world = w
    t = Nodes(w)
    gen = t.new("ShaderNodeTexCoord").outputs["Generated"]
    _, _, z = t.xyz(gen)
    col = t.ramp(z, [(0.49, rgba("#8a8274")), (0.5, rgba("#dde9f2")), (0.6, rgba("#a9c9e6")), (1.0, rgba("#5d93cf"))])
    bg = t.new("ShaderNodeBackground")
    t.link(col, bg.inputs["Color"])
    t.set(bg, "Strength", strength)
    o = t.new("ShaderNodeOutputWorld")
    t.link(bg.outputs[0], o.inputs["Surface"])
    if sun:
        d = bpy.data.lights.get("day_sun") or bpy.data.lights.new("day_sun", "SUN")
        d.energy, d.color, d.angle = sun, (1.0, 0.96, 0.9), math.radians(1.5)
        o_sun = bpy.data.objects.get("day_sun") or bpy.data.objects.new("day_sun", d)
        if o_sun.name not in scene.collection.objects:
            scene.collection.objects.link(o_sun)
        o_sun.rotation_euler = (math.radians(90 - sun_deg[0]), math.radians(sun_deg[1]), math.radians(sun_deg[2]))
    return w


def evening_sky(scene, strength=1.6):
    """a simplified version of the handover's sunset gradient: near-black below the horizon, pale blue at it, deep
    blue overhead"""
    w = scene.world or bpy.data.worlds.new("World")
    scene.world = w
    t = Nodes(w)
    gen = t.new("ShaderNodeTexCoord").outputs["Generated"]
    _, _, z = t.xyz(gen)
    col = t.ramp(z, [(0.49, rgba("#101a26")), (0.5, rgba("#9cc0de")), (0.56, rgba("#5a92cf")), (0.7, rgba("#2f68b4")),
                     (0.85, rgba("#163f80")), (1.0, rgba("#0c2a5e"))])
    bg = t.new("ShaderNodeBackground")
    t.link(col, bg.inputs["Color"])
    t.set(bg, "Strength", strength)
    o = t.new("ShaderNodeOutputWorld")
    t.link(bg.outputs[0], o.inputs["Surface"])
    return w
