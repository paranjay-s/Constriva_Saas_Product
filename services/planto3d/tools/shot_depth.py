"""Depth maps for the High stills, for the fast tour's parallax (PATCHES 57). No rendering: rays are cast through
the scene from each shot's camera on a coarse grid.

    blender -b JOB/house.blend -P tools/shot_depth.py -- SHOTS.json OUT_DIR [--grid 192x108] [--res 1920x1080]

Writes OUT_DIR/NAME_depth.npy (metres along the view axis; inf where a ray meets nothing) with the camera set up
exactly as cinema.py sets it for --shots (feet in, level when the shot says so, lens and vertical shift).
"""

import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
shots, out = json.load(open(argv[0])), argv[1]
gw, gh = (int(v) for v in (argv[argv.index("--grid") + 1] if "--grid" in argv else "192x108").split("x"))
rw, rh = (int(v) for v in (argv[argv.index("--res") + 1] if "--res" in argv else "1920x1080").split("x"))
F = 0.3048
sc = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()
os.makedirs(out, exist_ok=True)
for sh in shots:
    p = Vector(sh["p"]) * F
    aim = (Vector(sh["t"]) - Vector(sh["p"])) * F
    if sh.get("level"):
        aim.z = 0.0
    rot = aim.to_track_quat("-Z", "Y")
    fwd, right, up = rot @ Vector((0, 0, -1)), rot @ Vector((1, 0, 0)), rot @ Vector((0, 1, 0))
    lens, sensor = sh.get("lens", 18), 36.0
    half_w = sensor / 2 / lens                                 # tan of half the horizontal field of view
    half_h = half_w * rh / rw
    shift = sh.get("shift_y", 0.0) * 2 * half_w                # Blender's shift is in units of the larger side
    d = np.full((gh, gw), np.inf, np.float32)
    for j in range(gh):
        v = (1 - 2 * (j + 0.5) / gh) * half_h + shift
        for i in range(gw):
            u = (2 * (i + 0.5) / gw - 1) * half_w
            ray = (fwd + right * u + up * v).normalized()
            hit, loc, *_ = sc.ray_cast(dg, p, ray)
            if hit:
                d[j, i] = (loc - p).dot(fwd)
    np.save(os.path.join(out, sh["name"] + "_depth.npy"), d)
    fin = d[np.isfinite(d)]
    print(f"DEPTH {sh['name']} median {float(np.median(fin)) if fin.size else math.nan:.2f} m", flush=True)
