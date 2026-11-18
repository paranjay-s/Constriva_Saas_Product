"""Pictures of the furniture for the furniture page: blender -b PREVIEW/house.blend -P blender/thumbs.py -- OUT_DIR
(house.blend = gen.py run on catalog.preview_plan(); one PNG per item, named after it)."""
import bpy, os, sys
from mathutils import Vector
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from catalog import CATALOG, CELL  # noqa: E402

out, F = sys.argv[sys.argv.index("--") + 1], 0.3048
sc = bpy.context.scene
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bake  # noqa: E402
bake._gpu(sc)          # Cycles: real materials, and unlike EEVEE it runs on a server with no display or GPU
sc.cycles.samples, sc.cycles.use_denoising = 32, True
for o in sc.objects:                # roof off: the sky lights the preview room evenly, as in a photo studio
    if o.name.startswith(("roof", "parapet")):
        o.hide_render = True
sc.render.resolution_x, sc.render.resolution_y = 480, 360
cam = bpy.data.objects.new("thumb", bpy.data.cameras.new("thumb"))
sc.collection.objects.link(cam)
cam.data.lens = 26
sc.camera = cam
for k, (fn, (_, w, d, _kw)) in enumerate(CATALOG.items()):
    c = Vector(((k + 0.5) * CELL, CELL / 2, 2.2)) * F
    back = max(w, d) * 0.7 + 4.5                 # feet: far enough to fit the item
    cam.location = c + Vector((back * 0.55, -back, 3.2)) * F
    cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(out, fn + ".png")
    bpy.ops.render.render(write_still=True)
print("THUMBS OK", flush=True)
