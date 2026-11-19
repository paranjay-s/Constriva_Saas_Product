"""The creator agent's hands: a Blender process that builds one asset from a fixed set of operations.

    blender -b --factory-startup -P creator_worker.py -- FOLDER MAX_TRIS

Reads one JSON command per line on stdin ({"op": ..., "args": {...}}) and answers one JSON line per command on stdout
("RESULT {...}"). The operations make and change geometry, materials and lights in this scene, render a preview and
export the asset into FOLDER; nothing else. There is no Python evaluation, no file path from outside (every file it
writes is a fixed name inside FOLDER), no add-on, no network. The polygon budget is checked on every addition.
Units are metres; the asset stands on z = 0 and is centred on x = y = 0, front toward -Y (style.py conventions)."""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

import style  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
FOLDER = os.path.realpath(argv[0])
MAX_TRIS = int(argv[1]) if len(argv) > 1 else 40000
MAX_OBJECTS = 300
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
M = style.Materials()
FLAT = {}


def tris():
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for o in scene.objects:
        if o.type == "MESH":
            me = o.evaluated_get(dg).to_mesh()
            n += sum(len(p.vertices) - 2 for p in me.polygons)
            o.evaluated_get(dg).to_mesh_clear()
    return n


def num(a, k, lo, hi, default=None):
    v = a.get(k, default)
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not lo <= v <= hi:
        raise ValueError(f"{k} must be a number from {lo} to {hi}")
    return float(v)


def vec(a, k, lo=-50.0, hi=50.0, n=3):
    v = a.get(k)
    if not (isinstance(v, list) and len(v) == n and all(isinstance(c, (int, float)) for c in v) and all(lo <= c <= hi for c in v)):
        raise ValueError(f"{k} must be [{', '.join('x y z'.split()[:n])}] within {lo}..{hi} m")
    return [float(c) for c in v]


def name_of(a):
    n = str(a.get("name") or "part")[:40]
    return "".join(c for c in n if c.isalnum() or c in "_-") or "part"


def material(a):
    m = a.get("material")
    if m in style.RECIPES:
        return M[m]
    col = a.get("color")
    if isinstance(col, str) and len(col) == 7 and col.startswith("#"):
        key = (col, round(float(a.get("roughness", 0.5)), 2), round(float(a.get("metallic", 0.0)), 2))
        if key not in FLAT:
            mat = bpy.data.materials.new(f"flat_{col[1:]}")
            mat.use_nodes = True
            p = mat.node_tree.nodes["Principled BSDF"]
            p.inputs["Base Color"].default_value = style.rgba(col)
            p.inputs["Roughness"].default_value = max(0.0, min(1.0, key[1]))
            p.inputs["Metallic"].default_value = max(0.0, min(1.0, key[2]))
            FLAT[key] = mat
        return FLAT[key]
    raise ValueError(f"material must be one of the style's ({', '.join(sorted(style.RECIPES))}) or color '#rrggbb'")


def check_budget(new):
    if len(scene.objects) > MAX_OBJECTS:
        bpy.data.objects.remove(new)
        raise ValueError(f"too many objects (most {MAX_OBJECTS})")
    t = tris()
    if t > MAX_TRIS:
        bpy.data.objects.remove(new)
        raise ValueError(f"over the polygon budget ({t} > {MAX_TRIS} triangles): use fewer or simpler parts")
    return t


def op_add_box(a):
    lo, hi = vec(a, "min"), vec(a, "max")
    if any(h <= l for l, h in zip(lo, hi)):
        raise ValueError("max must be greater than min on every axis")
    o = style.box(name_of(a), (lo[0], hi[0]), (lo[1], hi[1]), (lo[2], hi[2]), material(a), bevel=num(a, "bevel", 0, 0.2, 0.0))
    return dict(object=o.name, triangles=check_budget(o))


def op_add_cylinder(a):
    c = vec(a, "center")
    r1, r2, h = num(a, "radius", 0.005, 20), num(a, "radius_top", 0.0, 20, a.get("radius")), num(a, "height", 0.002, 20)
    segs = int(num(a, "segments", 6, 96, 32))
    prof = [(0.0, 0.0), (r1, 0.0), (r2, h), (0.0, h)]
    o = style.lathe(name_of(a), c, prof, material(a), segs=segs)
    return dict(object=o.name, triangles=check_budget(o))


def op_add_lathe(a):
    c = vec(a, "center")
    prof = a.get("profile")
    if not (isinstance(prof, list) and 2 <= len(prof) <= 64 and all(isinstance(p, list) and len(p) == 2 and all(isinstance(v, (int, float)) for v in p) for p in prof)):
        raise ValueError("profile must be 2-64 [radius, height] pairs, bottom to top")
    if any(not (0 <= p[0] <= 20 and -1 <= p[1] <= 20) for p in prof):
        raise ValueError("profile radii 0..20 m, heights -1..20 m")
    o = style.lathe(name_of(a), c, [tuple(p) for p in prof], material(a), segs=int(num(a, "segments", 6, 96, 32)))
    return dict(object=o.name, triangles=check_budget(o))


def op_add_rod(a):
    o = style.rod(name_of(a), vec(a, "start"), vec(a, "end"), num(a, "radius", 0.002, 2), material(a))
    return dict(object=o.name, triangles=check_budget(o))


def op_set_material(a):
    o = bpy.data.objects.get(str(a.get("object")))
    if o is None or o.type != "MESH":
        raise ValueError("no such object")
    o.data.materials.clear()
    o.data.materials.append(material(a))
    return dict(object=o.name)


def op_transform(a):
    o = bpy.data.objects.get(str(a.get("object")))
    if o is None:
        raise ValueError("no such object")
    if "location" in a:
        o.location = vec(a, "location")
    if "rotation_deg" in a:
        o.rotation_euler = [math.radians(v) for v in vec(a, "rotation_deg", -360, 360)]
    if "scale" in a:
        o.scale = vec(a, "scale", 0.01, 50)
    return dict(object=o.name, triangles=tris())


def op_delete(a):
    o = bpy.data.objects.get(str(a.get("object")))
    if o is None:
        raise ValueError("no such object")
    bpy.data.objects.remove(o)
    return dict(deleted=True)


def op_add_light(a):
    kind = a.get("kind", "POINT")
    if kind not in ("POINT", "SPOT", "AREA"):
        raise ValueError("kind must be POINT, SPOT or AREA")
    d = bpy.data.lights.new(name_of(a), kind)
    d.energy = num(a, "watts", 1, 2000, 60)
    d.color = (1.0, 0.8, 0.6) if a.get("warm", True) else (1.0, 0.97, 0.94)
    o = bpy.data.objects.new(name_of(a), d)
    scene.collection.objects.link(o)
    o.location = vec(a, "location")
    return dict(object=o.name)


def op_scene(a):
    objs = []
    for o in scene.objects:
        if o.type == "MESH":
            from mathutils import Vector
            pts = [o.matrix_world @ Vector(v) for v in o.bound_box]
            objs.append(dict(name=o.name, min=[round(min(p[i] for p in pts), 3) for i in range(3)],
                             max=[round(max(p[i] for p in pts), 3) for i in range(3)],
                             material=o.data.materials[0].name if o.data.materials else None))
    return dict(objects=objs, triangles=tris())


def bounds():
    from mathutils import Vector
    pts = [o.matrix_world @ Vector(c) for o in scene.objects if o.type == "MESH" for c in o.bound_box]
    if not pts:
        return None
    return [[min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]]


def op_render_preview(a):
    """640 px previews in a small studio: evening (preview.png) and day (preview_day.png), in FOLDER"""
    b = bounds()
    if not b:
        raise ValueError("nothing to render yet")
    lo, hi = b
    span = max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2], 0.5)
    from mathutils import Vector
    tmp = [style.box("pv_floor", (-span * 3, span * 3), (-span * 3, span * 3), (-0.02, 0.0), M["Paving"])]
    style.room_light("pv_key", (0, lo[1] - 0.4, hi[2] + max(1.2, span * 0.6)), (max(1.6, span), max(1.0, span)), 260 * max(1, span), M)
    cam = bpy.data.objects.new("pv_cam", bpy.data.cameras.new("pv_cam"))
    scene.collection.objects.link(cam)
    cam.data.lens = 35
    target = Vector(((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) * 0.4))
    dist = span * 1.6 + 0.6
    cam.location = target + Vector((dist * 0.55, -dist, dist * 0.5))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    style.evening_sky(scene, 0.4)
    style.cycles(scene, int(num(a, "samples", 8, 64, 24)), (640, 360))
    style.colour_management(scene, -0.1, 4700)
    scene.render.filepath = os.path.join(FOLDER, "preview.png")
    bpy.ops.render.render(write_still=True)
    style.day_sky(scene)
    style.colour_management(scene, -0.45, 5600)
    scene.render.filepath = os.path.join(FOLDER, "preview_day.png")
    bpy.ops.render.render(write_still=True)
    for n in [o.name for o in scene.objects if o.name.startswith("pv_") or o.name == "day_sun"]:
        bpy.data.objects.remove(bpy.data.objects[n])
    return dict(preview="preview.png", preview_day="preview_day.png")


def op_export(a):
    """the detailed .blend and a browser .glb (Draco) in FOLDER, and the asset's size"""
    b = bounds()
    if not b:
        raise ValueError("nothing to export")
    detailed = tris()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(FOLDER, "asset.blend"), compress=True)
    import browser_bake
    _, browser = browser_bake.bake_browser(scene, "asset", FOLDER, min(MAX_TRIS, 30000))
    lo, hi = b
    return dict(size_m=[round(hi[i] - lo[i], 3) for i in range(3)], min=[round(v, 3) for v in lo],
                triangles=dict(detailed=detailed, browser=browser), files=["asset.blend", "asset.glb"], final=True)


def op_quit(a):
    return dict(bye=True)


OPS = {k[3:]: v for k, v in globals().items() if k.startswith("op_")}
print("READY", json.dumps(dict(ops=sorted(OPS), max_tris=MAX_TRIS)), flush=True)
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        cmd = json.loads(line)
        f = OPS.get(cmd.get("op"))
        if f is None:
            raise ValueError(f"unknown operation; use one of {sorted(OPS)}")
        out = dict(ok=True, **f(cmd.get("args") or {}))
    except Exception as e:  # every failure goes back to the agent as an error result
        out = dict(ok=False, error=str(e)[:300])
    print("RESULT " + json.dumps(out), flush=True)
    if out.get("bye"):
        break
