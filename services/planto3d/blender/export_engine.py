"""The built house for a real-time engine (PATCHES 58): glTF 2.0 (.glb, no Draco, textures inside) and USD (.usdc).

    blender -b JOB/house_baked.blend -P blender/export_engine.py -- OUT_DIR [--usd] [--gltf]

Unreal Engine 5 imports both (Interchange for glTF, the USD Importer plugin for USD); tools/unreal/import_render.py
takes the .glb by default. Light maps are left out (an engine lights the scene itself), the lights are exported as
punctual lights in glTF and as USD lights, cameras are left out (the engine side places its own from shots.json).
Units: metres, Z up in Blender; glTF is Y up by its standard and USD keeps Z up with metersPerUnit = 1.
"""

import os
import sys
import time

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
out = argv[0]
os.makedirs(out, exist_ok=True)
both = "--usd" not in argv and "--gltf" not in argv
for o in list(bpy.data.objects):
    if o.type == "CAMERA":
        bpy.data.objects.remove(o)
# world-space meshes: every transform applied, so an engine can place every mesh at the origin
for o in bpy.data.objects:
    o.hide_set(False)
    o.hide_viewport = False
bpy.ops.object.select_all(action="SELECT")
try:
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.make_single_user(object=True, obdata=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
except RuntimeError as e:                               # a context Blender refuses: export as it is
    print("transforms kept:", e, flush=True)
t0 = time.time()
if both or "--gltf" in argv:
    bpy.ops.export_scene.gltf(filepath=os.path.join(out, "house_engine.glb"), export_format="GLB",
                              export_draco_mesh_compression_enable=False, export_lights=True, export_cameras=False,
                              export_apply=True, export_yup=True)
    print(f"GLTF {time.time() - t0:.1f}s", flush=True)
if both or "--usd" in argv:
    t1 = time.time()
    kw = dict(filepath=os.path.join(out, "house_engine.usdc"), export_materials=True, export_lights=True,
              export_cameras=False, export_textures=True, relative_paths=True)
    try:
        bpy.ops.wm.usd_export(**kw)
    except TypeError:                                   # option names differ between Blender versions
        bpy.ops.wm.usd_export(filepath=kw["filepath"])
    print(f"USD {time.time() - t1:.1f}s", flush=True)
print("EXPORT OK", flush=True)
