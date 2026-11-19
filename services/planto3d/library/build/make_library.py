"""Build library pieces: a detailed .blend (live procedural materials, for renders and video), a browser .glb (one
mesh, colours baked into a texture atlas, glowing and glass parts as simple glTF materials), a 1280 px preview and an
index entry. Re-runnable from a clean Blender; one piece per run keeps memory and the texture cache clean.

    blender -b --factory-startup -P make_library.py -- NAME [--out DIR] [--no-preview] [--samples 48] [--size W,D,H]

Writes DIR/<kind>/<NAME>/{NAME.blend, NAME.glb, preview.png, entry.json} (DIR defaults to services/planto3d/library)."""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import pieces  # noqa: E402
import style  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
NAME = argv[0]
opt = lambda k, d: argv[argv.index(k) + 1] if k in argv else d
OUT = os.path.abspath(opt("--out", os.path.join(HERE, "..")))
SAMPLES = int(opt("--samples", 48))
BUDGET = {"furniture": 30000, "appliance": 20000, "fixture": 20000, "lighting": 15000}      # browser triangles

builder, size, rooms, kind = pieces.PIECES[NAME]
if "--size" in argv:
    size = tuple(float(v) for v in opt("--size", "").split(","))
folder = os.path.join(OUT, kind, NAME)
os.makedirs(folder, exist_ok=True)
t0 = time.time()

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
M = style.Materials()
objs = [o for o in builder(M, *size) if o is not None]
bpy.context.view_layer.update()


def tris(obs):
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for o in obs:
        if o.type == "MESH":
            me = o.evaluated_get(dg).to_mesh()
            n += sum(len(p.vertices) - 2 for p in me.polygons)
            o.evaluated_get(dg).to_mesh_clear()
    return n


detail_tris = tris(objs)
pts = [o.matrix_world @ Vector(c) for o in objs if o.type == "MESH" for c in o.bound_box]
lo = [min(p[i] for p in pts) for i in range(3)]
hi = [max(p[i] for p in pts) for i in range(3)]
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(folder, f"{NAME}.blend"), compress=True)

# ---- preview: a small studio (stone floor, plaster back wall), the handover's room light, a washer and its look
if "--no-preview" not in argv:
    span = max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2], 0.5)
    floor = style.box("pv_floor", (-6, 6), (-6, 6), (-0.02, 0.0), M["Paving"])
    wall = style.box("pv_wall", (-6, 6), (hi[1] + 0.02, hi[1] + 0.1), (0, 4), M["Plaster"])
    style.room_light("pv_key", (0, lo[1] - 0.4, max(2.6, hi[2] + 1.2)), (1.6, 1.0), 260, M)
    style.washer("pv_wash", (span * 0.6, lo[1] - 0.6, max(2.6, hi[2] + 1.2)), (0, hi[1], hi[2] * 0.5), 140, M)
    sun = bpy.data.lights.new("pv_fill", "AREA")
    sun.energy, sun.size, sun.color = 120, 3.0, style.EVENING
    f = bpy.data.objects.new("pv_fill", sun)
    scene.collection.objects.link(f)
    f.location = (-span * 1.4, lo[1] - span, hi[2] + 1.0)
    f.rotation_euler = (Vector((0, 0, hi[2] / 2)) - f.location).to_track_quat("-Z", "Y").to_euler()
    style.evening_sky(scene, 0.4)
    cam = bpy.data.objects.new("pv_cam", bpy.data.cameras.new("pv_cam"))
    scene.collection.objects.link(cam)
    cam.data.lens, cam.data.sensor_width = 35, 36
    target = Vector(((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) * 0.45))
    dist = span * 1.55 + 0.6
    cam.location = target + Vector((dist * 0.55, -dist, dist * 0.42))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    style.cycles(scene, SAMPLES, (1280, 720))
    style.colour_management(scene, -0.1, 4700)
    scene.render.filepath = os.path.join(folder, "preview.png")
    bpy.ops.render.render(write_still=True)
    for n in [o.name for o in scene.objects if o.name.startswith("pv_")]:
        bpy.data.objects.remove(bpy.data.objects[n])

# ---- browser model: everything joined, modifiers applied, colours baked into one atlas (browser_bake.py)
import browser_bake  # noqa: E402

_, browser_tris = browser_bake.bake_browser(scene, NAME, folder, BUDGET.get(kind, 20000))

entry = dict(id=NAME, kind=kind, rooms=list(rooms), size_m=[round(v, 3) for v in size],
             fits=dict(w=[round(size[0] * 0.6, 2), round(size[0] * 1.6, 2)], d=[round(size[1] * 0.6, 2), round(size[1] * 1.6, 2)]),
             shape="rectangular", style=["lantern", "warm-modern"],
             detailed=f"{kind}/{NAME}/{NAME}.blend", browser=f"{kind}/{NAME}/{NAME}.glb", preview=f"{kind}/{NAME}/preview.png",
             tris=dict(detailed=detail_tris, browser=browser_tris), source="team-made, procedural (style handover recipes)",
             licence="team-made", version=1, review="unreviewed", built_s=round(time.time() - t0, 1))
json.dump(entry, open(os.path.join(folder, "entry.json"), "w"), indent=1)
print("LIBRARY OK", json.dumps(entry), flush=True)
