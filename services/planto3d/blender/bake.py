"""Bake lighting into lightmaps and export a light web model.
Each group of objects (one storey, the site) is joined into one mesh, gets a second UV map ('lm') packed by
Smart UV Project, and Cycles bakes direct + indirect diffuse light (no albedo) into it. The browser multiplies its
normal textures by this light map, so it needs no real-time lights or shadows - cheap on any GPU.
Light maps are stored as sRGB-encoded (light / max) WebP; meta.json carries max per map."""
import math, os
import bpy
import numpy as np

SRGB = lambda x: np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(np.maximum(x, 0), 1 / 2.4) - 0.055)


def _gpu(scene):
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dev in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
        try:
            prefs.compute_device_type = dev
            prefs.get_devices()
            if any(d.type == dev for d in prefs.devices):
                for d in prefs.devices:
                    d.use = True
                scene.cycles.device = "GPU"
                return dev
        except Exception:
            continue
    scene.cycles.device = "CPU"
    return "CPU"


def _transparent(ob):
    for m in ob.data.materials if ob.type == "MESH" else []:
        if m and m.use_nodes:
            p = m.node_tree.nodes.get("Principled BSDF")
            if p and p.inputs["Alpha"].default_value < 0.99:
                return True
    return False


def _flatten(objs):
    """bake modifiers into mesh data, make data single-user; -> list of mesh objects"""
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for ob in objs:
        if ob.type != "MESH" or ob.name not in bpy.data.objects or not ob.users_collection:
            continue     # (imported model templates are kept outside the scene - not part of the house)
        if ob.modifiers:
            me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
            ob.modifiers.clear()
            ob.data = me
        elif ob.data.users > 1:
            ob.data = ob.data.copy()
        out.append(ob)
    return out


def _join(name, objs):
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    target = objs[0]
    coll = target.users_collection[0]
    for o in objs:
        o.select_set(True)
    vl.objects.active = target
    # keep world transforms: clear parents first
    for o in objs:
        if o.parent:
            mw = o.matrix_world.copy()
            o.parent = None
            o.matrix_world = mw
    with bpy.context.temp_override(active_object=target, selected_editable_objects=objs, selected_objects=objs):
        bpy.ops.object.join()
    target.name = name
    return target


def _surface_area(ob):
    mw = ob.matrix_world
    s = abs(mw.determinant()) ** (2 / 3)
    return sum(p.area for p in ob.data.polygons) * s


def _clean(ob):
    """weld box pieces, drop back-to-back faces hidden inside walls, merge coplanar faces (fewer light map seams)"""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    bm.faces.ensure_lookup_table()
    seen, dead = {}, set()
    for f in bm.faces:
        c = f.calc_center_median()
        key = (round(c.x, 3), round(c.y, 3), round(c.z, 3), round(f.calc_area(), 4))
        g = seen.get(key)
        if g is not None and g.normal.dot(f.normal) < -0.99:
            dead.update((g, f))
        else:
            seen[key] = f
    bmesh.ops.delete(bm, geom=list(dead), context="FACES")
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.5), verts=bm.verts, edges=bm.edges, delimit={"MATERIAL"})
    bm.to_mesh(ob.data)
    bm.free()


def _unwrap(ob):
    _clean(ob)
    me = ob.data
    if "UVMap" not in me.uv_layers:
        me.uv_layers.new(name="UVMap")
    lm = me.uv_layers.new(name="lm")
    me.uv_layers["UVMap"].active_render = True
    me.uv_layers.active = lm
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    ob.select_set(True)
    vl.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    kw = dict(angle_limit=math.radians(66), island_margin=0.003, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    try:
        bpy.ops.uv.smart_project(margin_method="FRACTION", **kw)
    except TypeError:
        bpy.ops.uv.smart_project(**kw)
    bpy.ops.object.mode_set(mode="OBJECT")


def _cool_down(progress, limit=78, resume=65):
    """laptop GPUs overheat on long bakes: pause between bakes while the GPU is hot"""
    import subprocess, time
    def temp():
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
                                 capture_output=True, text=True, timeout=5).stdout
            return max(int(v) for v in out.split())
        except Exception:
            return 0
    t = temp()
    if t >= limit:
        progress(None, f"GPU at {t}C - cooling down")
        while temp() > resume:
            time.sleep(5)


def _texture_size(area_m2, texel_m):
    px = math.sqrt(area_m2 / 0.55) / texel_m     # ~55% of the atlas is covered by islands
    for s in (512, 1024, 2048, 4096):
        if px <= s:
            return s
    return 4096


def _bake(ob, size, samples):
    img = bpy.data.images.new(f"lm_{ob.name}", size, size, alpha=True, float_buffer=True)
    nodes = []
    for m in ob.data.materials:
        if not m or not m.use_nodes:
            continue
        nt = m.node_tree
        for n in nt.nodes:
            n.select = False
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = img
        n.select = True
        nt.nodes.active = n
        nodes.append((nt, n))
    sc = bpy.context.scene
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    ob.select_set(True)
    vl.objects.active = ob
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT"}, margin=6, use_clear=True,
                        target="IMAGE_TEXTURES")
    for nt, n in nodes:
        nt.nodes.remove(n)
    return img


def _encode(img, path):
    """denoise (masked blur inside islands), normalise, sRGB-encode, save WebP -> max light value"""
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    rgb, a = px[..., :3], (px[..., 3] > 0.5).astype(np.float32)

    def blur(x):          # 5-tap separable binomial blur
        k = np.array([1, 4, 6, 4, 1], np.float32) / 16
        x = sum(np.roll(x, i - 2, axis=0) * k[i] for i in range(5))
        return sum(np.roll(x, i - 2, axis=1) * k[i] for i in range(5))
    # island-edge texels bake from inside the neighbouring geometry and come out dark (the faint seams):
    # replace a 2-texel rim of every island with light grown outwards from its interior
    shrink = lambda m: m * np.roll(m, 1, 0) * np.roll(m, -1, 0) * np.roll(m, 1, 1) * np.roll(m, -1, 1)
    core = shrink(shrink(a))
    for _ in range(3):
        cn, cd = blur(rgb * core[..., None]), blur(core)[..., None]
        rim = (a > 0.5) & (core < 0.5) & (cd[..., 0] > 0.02)
        rgb = np.where(rim[..., None], cn / np.maximum(cd, 1e-6), rgb)
        core = np.maximum(core, rim.astype(np.float32))
    num = blur(rgb * a[..., None])
    den = blur(a)[..., None]
    sm = np.where(den > 0.05, num / np.maximum(den, 1e-6), rgb)
    lum = sm[..., 0] * 0.2126 + sm[..., 1] * 0.7152 + sm[..., 2] * 0.0722
    vals = lum[a > 0.5]
    mx = float(np.percentile(vals, 99.5)) if vals.size else 1.0
    mx = max(mx, 1e-3)
    enc = SRGB(np.clip(sm / mx, 0, 1))
    out = np.concatenate([enc, np.ones((h, w, 1), np.float32)], axis=2)
    o = bpy.data.images.new(os.path.basename(path), w, h, alpha=False)
    o.colorspace_settings.name = "Non-Color"
    o.pixels.foreach_set(out.astype(np.float32).ravel())
    o.filepath_raw = path
    o.file_format = "WEBP"
    try:
        o.save(filepath=path, quality=90)
    except TypeError:
        o.save()
    return mx


def bake_and_export(groups, unbaked, out, quality="high", do_bake=True, progress=print):
    scene = bpy.context.scene
    dev = _gpu(scene)
    print("bake device", dev, flush=True)
    scene.cycles.max_bounces = 6
    scene.cycles.diffuse_bounces = 4
    texel = 0.02 if quality == "high" else 0.045
    samples = 256 if quality == "high" else 64
    baked, keep, lightmaps, lmax = [], [], {}, {}
    n = len(groups)
    if do_bake:      # every light map's size before the first bake: the server's time-left estimate (server.py)
        sizes = []
        for name, objs in groups.items():
            ms = [o for o in _flatten([o for o in objs if o.name in bpy.data.objects]) if not _transparent(o) and len(o.data.polygons)]
            if ms:
                sizes.append(f"{name}={_texture_size(sum(_surface_area(o) for o in ms), texel)}")
        print("MAPS " + " ".join(sizes), flush=True)
    for gi, (name, objs) in enumerate(groups.items()):
        objs = [o for o in objs if o.name in bpy.data.objects]
        meshes = _flatten(objs)
        glass = [o for o in meshes if _transparent(o)]
        solid = [o for o in meshes if o not in glass and len(o.data.polygons)]
        keep += glass
        if not solid:
            continue
        names = {o.name for o in objs if o.type == "EMPTY"}
        ob = _join(f"bake_{name}", solid)
        for nm in names:    # parents / empties left behind
            if nm in bpy.data.objects:
                bpy.data.objects.remove(bpy.data.objects[nm])
        baked.append(ob)
        if not do_bake:
            continue
        _unwrap(ob)
        size = _texture_size(_surface_area(ob), texel)
        _cool_down(lambda p, m: progress(35 + 55 * gi / n, m))
        progress(35 + 55 * gi / n, f"baking light for {name} ({size}px)")
        img = _bake(ob, size, samples)
        fn = f"lm_{name}.webp"
        lmax[ob.name] = round(_encode(img, os.path.join(out, fn)), 4)
        lightmaps[ob.name] = fn
        bpy.data.images.remove(img)
    progress(92, "exporting model")
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    sel = baked + keep + [o for o in unbaked if o.name in bpy.data.objects]
    for o in sel:
        if o.name in vl.objects:
            o.select_set(True)
            for c in o.children_recursive:
                c.select_set(True)
    kw = dict(filepath=os.path.join(out, "house.glb"), export_format="GLB", use_selection=True, export_apply=True,
              export_texcoords=True, export_normals=True, export_lights=False, export_cameras=False,
              export_image_format="WEBP", export_draco_mesh_compression_enable=True,
              export_draco_mesh_compression_level=6, export_draco_position_quantization=14,
              export_draco_normal_quantization=10, export_draco_texcoord_quantization=14)
    while True:
        try:
            bpy.ops.export_scene.gltf(**kw)
            break
        except TypeError as e:          # option names differ between Blender versions: drop the unknown one
            bad = next((k for k in kw if k in str(e) and k != "filepath"), None)
            if not bad:
                raise
            kw.pop(bad)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "house_baked.blend"))
    return dict(lightmaps=lightmaps, lightmap_max=lmax, baked=bool(lightmaps))
