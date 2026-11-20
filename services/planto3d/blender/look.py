"""The "Lantern house" look for High stills and tours (PATCHES 57), ported from the style handover in
docs/reference/style/villa_look_handover (scripts/lantern_lib.py, lantern_more.py, post.py; the scripts in
scripts/history were not run). Used by cinema.py with --look lantern.

    import look
    look.apply(scene, mode="evening" | "day", sun_bearing=deg, north_deg=deg)   # sky, materials, render settings
    look.finish(png_in, jpg_out)                                                   # bloom, S-curve, vignette, grain

What is ported, and what is ours:
- sunset_sky: the handover's evening gradient with the band of last light toward the west (its colours and
  ramp positions); day_sky: Blender's sky texture with a sun at the house's sun bearing (ours).
- materials: Limestone, Paving, Plaster, Water and Glass builders with the handover's colours and textures,
  swapped in for our exterior walls, paving, plinth, coping, water and glass by material name.
- render settings: Cycles with adaptive sampling (noise threshold 0.02), OpenImageDenoise, 8 bounces
  (diffuse 4, glossy 4, transmission 8, transparent 24), indirect clamp 6, Blackman-Harris 1.5 px, AgX with
  Medium High Contrast; on the GPU when there is one (the handover rendered on a CPU).
- finish: post.py's bloom (luma above 0.72, two blurs at 0.6 % and 3 % of the width, screen blend), gentle
  S-curve, -10 % vignette outside 35 % of the radius, fine grain and light sharpening, in NumPy only
  (Blender's Python has NumPy, not OpenCV): the Gaussian blurs are three box blurs.

The handover's gotcha (a module-level cache of procedural textures that does not survive a scene reset) is
handled here: `_cache` is cleared at the start of every apply().
"""

import math

import bpy

_cache = {}


# ------------------------------------------------------------------ node helpers (handover's Tree)


def srgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def rgba(h, a=1.0):
    return (*srgb(h), a)


def _sock(coll, names):
    for nm in [names] if isinstance(names, str) else names:
        if nm in coll:
            return coll[nm]
    raise KeyError(names)


def setv(node, names, value):
    _sock(node.inputs, names).default_value = value


class Tree:
    def __init__(self, owner):
        try:
            owner.use_nodes = True
        except Exception:
            pass
        self.t = owner.node_tree
        self.t.nodes.clear()

    def n(self, kind, **props):
        node = self.t.nodes.new(kind)
        for k, v in props.items():
            setattr(node, k, v)
        return node

    def l(self, a, b):  # noqa: E743
        self.t.links.new(a, b)

    def coord(self, which="Object"):
        return self.n("ShaderNodeTexCoord").outputs[which]

    def mapping(self, vec, scale=(1, 1, 1)):
        m = self.n("ShaderNodeMapping")
        setv(m, "Scale", scale)
        self.l(vec, m.inputs["Vector"])
        return m.outputs["Vector"]

    def noise(self, vec, scale=5.0, detail=3.0, rough=0.5):
        nd = self.n("ShaderNodeTexNoise")
        setv(nd, "Scale", scale)
        setv(nd, "Detail", detail)
        setv(nd, "Roughness", rough)
        self.l(vec, nd.inputs["Vector"])
        return nd.outputs["Fac"] if "Fac" in nd.outputs else nd.outputs[0]

    def ramp(self, fac, stops):
        r = self.n("ShaderNodeValToRGB")
        els = r.color_ramp.elements
        while len(els) < len(stops):
            els.new(0.5)
        for el, (pos, col) in zip(els, stops):
            el.position = pos
            el.color = (col, col, col, 1) if isinstance(col, (int, float)) else col
        self.l(fac, r.inputs["Fac"])
        return r.outputs["Color"]

    def math(self, op, a, b=None, clamp=False):
        m = self.n("ShaderNodeMath", operation=op)
        m.use_clamp = clamp
        for i, v in enumerate([a, b]):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                m.inputs[i].default_value = v
            else:
                self.l(v, m.inputs[i])
        return m.outputs[0]

    def mix(self, fac, a, b, blend="MIX"):
        m = self.n("ShaderNodeMix", data_type="RGBA", blend_type=blend)
        ins = [s for s in m.inputs if s.type == "RGBA"]
        fac_in = [s for s in m.inputs if s.type == "VALUE"][0]
        for s, v in ((fac_in, fac), (ins[0], a), (ins[1], b)):
            if hasattr(v, "node"):
                self.l(v, s)
            else:
                s.default_value = v
        return [s for s in m.outputs if s.type == "RGBA"][0]

    def bump(self, height, strength=0.3, distance=0.02, normal=None):
        b = self.n("ShaderNodeBump")
        setv(b, "Strength", strength)
        setv(b, "Distance", distance)
        self.l(height, b.inputs["Height"])
        if normal is not None:
            self.l(normal, b.inputs["Normal"])
        return b.outputs["Normal"]

    def xyz(self, vec):
        s = self.n("ShaderNodeSeparateXYZ")
        self.l(vec, s.inputs[0])
        return s.outputs[0], s.outputs[1], s.outputs[2]

    def combine(self, x=0.0, y=0.0, z=0.0):
        c = self.n("ShaderNodeCombineXYZ")
        for i, v in enumerate((x, y, z)):
            if isinstance(v, (int, float)):
                c.inputs[i].default_value = v
            else:
                self.l(v, c.inputs[i])
        return c.outputs[0]

    def principled(self, color=None, rough=0.5, metallic=0.0):
        p = self.n("ShaderNodeBsdfPrincipled")
        if color is not None:
            self.put(p, "Base Color", color)
        self.put(p, "Roughness", rough)
        self.put(p, "Metallic", metallic)
        return p

    def put(self, node, names, v):
        s = _sock(node.inputs, names)
        if hasattr(v, "node"):
            self.l(v, s)
        else:
            s.default_value = v

    def out(self, shader):
        o = self.n("ShaderNodeOutputMaterial")
        self.l(shader, o.inputs["Surface"])
        return o


def _brick(t, uv, width, height, mortar, mortar_col):
    b = t.n("ShaderNodeTexBrick")
    b.offset = 0.5
    for k, v in (("Scale", 1.0), ("Brick Width", width), ("Row Height", height), ("Mortar Size", mortar),
                 ("Mortar Smooth", 0.15), ("Color1", (0.86, 0.86, 0.86, 1)), ("Color2", (1, 1, 1, 1)),
                 ("Mortar", (mortar_col, mortar_col, mortar_col, 1))):
        try:
            setv(b, k, v)
        except KeyError:
            pass
    t.l(uv, b.inputs["Vector"])
    return b


# ------------------------------------------------------------------ materials (handover colours)


def limestone(m, base="#cdbb9d", dark="#b39f7f", light="#dccdb2", panel=(1.2, 0.6), rough=0.62):
    """honed sand-coloured stone cladding in 1.2 x 0.6 m panels with fine joints (lantern_lib.mat_limestone)"""
    t = Tree(m)
    pos = t.coord()
    x, y, z = t.xyz(pos)
    brick = _brick(t, t.combine(t.math("ADD", x, y), z, 0.0), panel[0], panel[1], 0.004, 0.25)
    cloud = t.noise(pos, 0.55, 5, 0.55)
    veins = t.noise(t.mapping(pos, (0.6, 0.6, 5.0)), 2.2, 6, 0.65)
    col = t.ramp(cloud, [(0.3, rgba(dark)), (0.5, rgba(base)), (0.72, rgba(light))])
    col = t.mix(t.math("MULTIPLY", t.ramp(veins, [(0.45, 0.0), (0.62, 1.0)]), 0.18), col, rgba(dark))
    col = t.mix(1.0, col, brick.outputs["Color"], "MULTIPLY")
    p = t.principled(col, rough)
    t.put(p, "Roughness", t.math("ADD", t.math("MULTIPLY", t.noise(pos, 3.0, 3, 0.5), 0.25), rough - 0.12))
    n1 = t.bump(t.noise(pos, 60.0, 3, 0.6), 0.12, 0.004)
    t.l(t.bump(t.math("SUBTRACT", 1.0, brick.outputs["Fac"]), 0.5, 0.004, n1), p.inputs["Normal"])
    t.out(p.outputs[0])


def paving(m, base="#b7ab95", slab=1.2, rough=0.24):
    """large semi-polished stone slabs that carry the light (lantern_lib.mat_paving)"""
    t = Tree(m)
    pos = t.coord()
    x, y, _ = t.xyz(pos)
    brick = _brick(t, t.combine(x, y, 0.0), slab * 2, slab, 0.005, 0.18)
    col = t.ramp(t.noise(pos, 0.9, 5, 0.6), [(0.3, rgba("#a19580")), (0.55, rgba(base)), (0.8, rgba("#c8bda8"))])
    col = t.mix(1.0, col, brick.outputs["Color"], "MULTIPLY")
    p = t.principled(col, rough)
    t.put(p, "Roughness", t.math("ADD", t.math("MULTIPLY", t.noise(pos, 1.7, 4, 0.6), 0.3), rough - 0.1))
    n1 = t.bump(t.noise(pos, 30.0, 3, 0.6), 0.05, 0.003)
    t.l(t.bump(t.math("SUBTRACT", 1.0, brick.outputs["Fac"]), 0.5, 0.004, n1), p.inputs["Normal"])
    t.out(p.outputs[0])


def plaster(m, color="#efe5d3", rough=0.85):
    t = Tree(m)
    p = t.principled(rgba(color), rough)
    t.l(t.bump(t.noise(t.coord(), 40.0, 4, 0.6), 0.05, 0.01), p.inputs["Normal"])
    t.out(p.outputs[0])


def water(m, color="#04090c", ripple=0.075, scale=2.6):
    """still dark water: a mirror with very small ripples (lantern_lib.mat_water)"""
    t = Tree(m)
    pos = t.coord()
    p = t.principled(rgba(color), 0.015)
    setv(p, "IOR", 1.33)
    h = t.math("ADD", t.noise(t.mapping(pos, (1.0, 0.45, 1.0)), scale, 3, 0.55),
               t.math("MULTIPLY", t.noise(pos, scale * 6.0, 2, 0.5), 0.25))
    t.l(t.bump(h, ripple, 0.1), p.inputs["Normal"])
    t.out(p.outputs[0])


def glass(m, tint="#eef4f2"):
    """clear straight through, mirror reflection weighted by Fresnel (lantern_lib.mat_glass)"""
    t = Tree(m)
    fres = t.n("ShaderNodeFresnel")
    setv(fres, "IOR", 1.5)
    tr = t.n("ShaderNodeBsdfTransparent")
    setv(tr, "Color", rgba(tint))
    refl = t.principled((1, 1, 1, 1), 0.0, 1.0)
    mix = t.n("ShaderNodeMixShader")
    t.l(fres.outputs[0], mix.inputs[0])
    t.l(tr.outputs[0], mix.inputs[1])
    t.l(refl.outputs[0], mix.inputs[2])
    t.out(mix.outputs[0])


# our material name (prefix) -> the look's material
SWAPS = [
    (("exterior", "facade"), lambda m: limestone(m)),
    (("plinth_stone",), lambda m: limestone(m, base="#8f8270", dark="#776b5b", light="#a39785")),
    (("coping",), lambda m: limestone(m, base="#dccdb2", dark="#cdbb9d", light="#e8dcc6", panel=(0.9, 0.3))),
    (("pavers", "terrace", "footpath"), lambda m: paving(m)),
    (("plaster", "interior_wall", "ceiling"), lambda m: plaster(m)),
    (("water", "pool_water"), lambda m: water(m)),
    (("glass",), lambda m: glass(m)),
]


def restyle():
    """swap our materials for the look's, by name; returns the names changed"""
    done = []
    for m in bpy.data.materials:
        base = m.name.split(".")[0]
        for prefixes, build in SWAPS:
            if base.startswith(prefixes) and not base.endswith(("_baked", "_glow")):
                build(m)
                done.append(m.name)
                break
    return done


# ------------------------------------------------------------------ skies


def sunset_sky(scene, strength=1.6, west=(1.0, 0.0), glow=2.2):
    """the handover's clear evening sky with a thin band of last light on the western horizon"""
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    t = Tree(scene.world)
    x, y, z = t.xyz(t.coord("Generated"))
    base = t.ramp(t.math("ADD", t.math("MULTIPLY", z, 0.5), 0.5), [
        (0.00, rgba("#101a26")), (0.49, rgba("#16222e")), (0.505, rgba("#9cc0de")), (0.54, rgba("#5a92cf")),
        (0.62, rgba("#2f68b4")), (0.80, rgba("#163f80")), (1.00, rgba("#0c2a5e"))])
    length = t.math("SQRT", t.math("ADD", t.math("MULTIPLY", x, x), t.math("MULTIPLY", y, y)))
    toward = t.math("DIVIDE", t.math("ADD", t.math("MULTIPLY", x, west[0]), t.math("MULTIPLY", y, west[1])),
                    t.math("MAXIMUM", length, 0.001))
    az = t.math("POWER", t.math("MAXIMUM", toward, 0.0), 3.0)
    band = t.ramp(z, [(0.0, 0.0), (0.003, 1.0), (0.09, 0.75), (0.32, 0.0)])
    warm = t.ramp(z, [(0.0, rgba("#ffcf7a")), (0.045, rgba("#ff9c46")), (0.13, rgba("#e2705c")),
                      (0.3, rgba("#6a78b8"))])
    fac = t.math("MULTIPLY", az, band, clamp=True)
    col = t.mix(fac, base, warm)
    bg = t.n("ShaderNodeBackground")
    t.l(col, bg.inputs["Color"])
    t.l(t.math("ADD", strength, t.math("MULTIPLY", fac, glow)), bg.inputs["Strength"])
    o = t.n("ShaderNodeOutputWorld")
    t.l(bg.outputs[0], o.inputs["Surface"])


def day_sky(scene, sun_bearing=200.0, north_deg=0.0, elevation=38.0):
    """a clear day: Blender's sky texture and a sun at the house's sun bearing (degrees from north, clockwise)"""
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    t = Tree(scene.world)
    sky = t.n("ShaderNodeTexSky")
    rot = math.radians(90 - (sun_bearing + north_deg))       # world +x is east, +y north (plan up)
    for k, v in (("sun_elevation", math.radians(elevation)), ("sun_rotation", rot), ("altitude", 0.0),
                 ("sun_disc", True)):
        try:
            setattr(sky, k, v)
        except Exception:
            pass
    bg = t.n("ShaderNodeBackground")
    setv(bg, "Strength", 0.35)
    t.l(sky.outputs[0], bg.inputs["Color"])
    o = t.n("ShaderNodeOutputWorld")
    t.l(bg.outputs[0], o.inputs["Surface"])
    sun = bpy.data.lights.new("look_sun", "SUN")
    sun.energy, sun.angle, sun.color = 4.0, math.radians(0.6), (1.0, 0.96, 0.9)
    ob = bpy.data.objects.new("look_sun", sun)
    ob.rotation_euler = (math.radians(90 - elevation), 0, rot + math.pi / 2)
    scene.collection.objects.link(ob)
    return ob


def wall_washers(scene, bounds, height=2.7, pitch=3.5, watts=180.0):
    """the handover's facade downlights (Wash0-3): warm 3800 K spots just outside every outer face, aimed down
    at the wall, every `pitch` metres. bounds = (x0, x1, y0, y1) of the house in metres."""
    x0, x1, y0, y1 = bounds
    made = 0
    for side, (a0, a1, fixed, dx, dy) in {"S": (x0, x1, y0, 0, -1), "N": (x0, x1, y1, 0, 1),
                                          "W": (y0, y1, x0, -1, 0), "E": (y0, y1, x1, 1, 0)}.items():
        n = max(1, int((a1 - a0) / pitch))
        for i in range(n):
            u = a0 + (i + 0.5) * (a1 - a0) / n
            loc = (u, fixed + dy * 0.35, height) if dx == 0 else (fixed + dx * 0.35, u, height)
            L = bpy.data.lights.new(f"wash_{side}{i}", "SPOT")
            L.energy, L.color = watts, (1.0, 0.62, 0.33)
            L.spot_size, L.spot_blend, L.shadow_soft_size = math.radians(58), 0.6, 0.03
            try:
                L.visible_camera = False
            except Exception:
                pass
            ob = bpy.data.objects.new(L.name, L)
            ob.location = loc
            # straight down, tipped 12 degrees toward the wall
            tip = math.radians(12)
            ob.rotation_euler = (tip * dy, -tip * dx, 0.0) if dx == 0 else (tip * dy, -tip * dx, 0.0)
            scene.collection.objects.link(ob)
            made += 1
    return made


# ------------------------------------------------------------------ render settings


def cycles(scene, samples=96, time_limit=480):
    """Cycles as the handover set it, on the GPU when there is one; time_limit (s) caps one still (safety)"""
    scene.render.engine = "CYCLES"
    c = scene.cycles
    prefs = bpy.context.preferences.addons["cycles"].preferences
    c.device = "CPU"
    for kind in ("METAL", "OPTIX", "CUDA", "HIP", "ONEAPI"):
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
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.02
    c.use_denoising = True
    try:
        c.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces = 8, 4, 4
    c.transmission_bounces, c.transparent_max_bounces = 8, 24
    c.caustics_reflective = c.caustics_refractive = False
    c.sample_clamp_indirect = 6.0
    try:
        c.time_limit = time_limit
        c.filter_type, c.filter_width = "BLACKMAN_HARRIS", 1.5
    except Exception:
        pass
    vs = scene.view_settings
    vs.view_transform = "AgX"
    vs.look = "AgX - Medium High Contrast"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "16"
    return c.device


def white_balance(scene, kelvin):
    try:
        scene.view_settings.use_white_balance = kelvin is not None
        if kelvin:
            scene.view_settings.white_balance_temperature = kelvin
    except Exception:
        pass


def apply(scene, mode="evening", sun_bearing=200.0, north_deg=0.0, bounds=None):
    """sky, materials and colour for one of the two looks; returns what was swapped"""
    _cache.clear()          # the handover's texture-cache fix: nothing cached survives a rebuild
    swapped = restyle()
    if mode == "day":
        for o in list(scene.objects):
            if o.type == "LIGHT" and o.data.type == "SUN":
                bpy.data.objects.remove(o)
        day_sky(scene, sun_bearing, north_deg)
        white_balance(scene, 5600)
    else:
        west = (math.cos(math.radians(-north_deg) + math.pi), math.sin(math.radians(-north_deg) + math.pi))
        sunset_sky(scene, west=west)
        white_balance(scene, 4700)
        if bounds:
            wall_washers(scene, bounds)
    return swapped


# ------------------------------------------------------------------ finishing (post.py in NumPy)


def _box(a, r, axis):
    import numpy as np
    if r < 1:
        return a
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis)
    n = a.shape[axis]
    hi = np.take(c, range(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, range(0, n), axis=axis)
    return (hi - lo) / (2 * r + 1)


def _gauss(a, sigma):
    """three box blurs ~ a Gaussian of this sigma (pixels)"""
    r = max(1, int(round((math.sqrt(12 * sigma * sigma / 3 + 1) - 1) / 2)))
    for _ in range(3):
        a = _box(_box(a, r, 0), r, 1)
    return a


def finish(src, dst, bloom=0.2, vignette=0.1, grain=0.006, seed=1, quality=92):
    """the handover's post.py on one render (16-bit PNG in, JPEG out)"""
    import numpy as np
    img = bpy.data.images.load(src, check_existing=False)
    img.colorspace_settings.name = "Non-Color"              # the file's own values, no colour conversion
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    rgb = px.reshape(h, w, 4)[:, :, :3].copy()                 # display-referred (the PNG is AgX output)
    luma = rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    bright = rgb * np.clip((luma - 0.72) / 0.28, 0, 1)[..., None]
    small = bright[::4, ::4]                                    # the wide blur on a quarter-size copy
    wide = _gauss(small, w * 0.03 / 4)
    wide = np.repeat(np.repeat(wide, 4, 0), 4, 1)[:h, :w]
    glow = 0.6 * _gauss(bright, w * 0.006) + 0.4 * wide
    out = np.clip(1.0 - (1.0 - rgb) * (1.0 - bloom * glow), 0, 1)
    out = out - 0.06 * (out - out * out * (3 - 2 * out))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r2 = ((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2
    out = out * (1.0 - vignette * np.clip(r2 - 0.35, 0, None) / 1.65)[..., None]
    out = out + np.random.default_rng(seed).normal(0, grain, (h, w, 1)).astype(np.float32)
    out = out + 0.25 * (out - _gauss(out, 1.0))
    out = np.clip(out, 0, 1)
    res = bpy.data.images.new("finished", w, h, alpha=False, float_buffer=False)
    res.colorspace_settings.name = "Non-Color"              # before the pixels: changing it later clears them
    flat = np.concatenate([out, np.ones((h, w, 1), np.float32)], axis=2).reshape(-1)
    res.pixels.foreach_set(flat.astype(np.float32))
    res.update()
    res.filepath_raw = dst
    res.file_format = "JPEG"
    try:
        res.save(quality=quality)
    except TypeError:                                            # older Blender: no quality argument
        res.save()
    bpy.data.images.remove(img)
    bpy.data.images.remove(res)
