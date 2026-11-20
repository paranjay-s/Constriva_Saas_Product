"""The fast tour (PATCHES 57): a 1080p film made from the High stills instead of rendering every frame.

    blender -b --factory-startup -P tools/fast_tour.py -- STILLS_DIR SHOTS.json META.json OUT.mp4 [--sec 3.5]
            [--fps 30] [--res 1920x1080] [--label "Evening"]

Each still becomes a short shot: the camera moves gently forward into the picture, with parallax from the depth
map cinema.py saved beside it (NAME_depth.npy, ray-cast from the same camera; without one the still is simply
pushed in). Shots are joined by half-second crossfades, in the order front elevation, rooms, the other elevations.
Every shot carries its title (rendered as an image by Blender's own text, since the ffmpeg here has no text
filter) and a minimap of the storey with the room highlighted. Frames are piped to ffmpeg (libx264, yuv420p).
Runs inside Blender for NumPy; renders nothing but the titles (Workbench, a fraction of a second each).
"""

import json
import math
import os
import subprocess
import sys

import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
STILLS, SHOTS, META, OUT = argv[:4]


def opt(k, d):
    return type(d)(argv[argv.index(k) + 1]) if k in argv else d


SEC, FPS = opt("--sec", 3.5), opt("--fps", 30)
W, H = (int(v) for v in opt("--res", "1920x1080").split("x"))
LABEL = opt("--label", "")
FADE = int(FPS * 0.5)
meta = json.load(open(META))
shots = json.load(open(SHOTS))
names = {s["name"]: s for s in shots}
order = [s for s in shots if s["name"] == "elevation_front"] + [s for s in shots if s["name"].startswith("room_")] + \
        [s for s in shots if s["name"].startswith("elevation_") and s["name"] != "elevation_front"]
order = [s for s in order if os.path.exists(os.path.join(STILLS, s["name"] + ".jpg"))]
if not order:
    raise SystemExit("no stills to make a tour from")


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from overlay import MAP, crop_text, load, minimap, over, title_images  # noqa: E402


def room_of(shot):
    """the storey and room a room shot stands in (meta rooms, metres)"""
    if not shot["name"].startswith("room_"):
        return meta["floors"][0], None
    px, py, pz = (v * 0.3048 for v in shot["p"])
    tx, ty = (v * 0.3048 for v in shot["t"][:2])
    mx, my = px + (tx - px) * 0.4, py + (ty - py) * 0.4
    fl = min(meta["floors"], key=lambda f: abs(f["z"] + float(meta.get("eye", 1.6)) - pz))
    for r in fl["rooms"]:
        if any(q[0] <= mx <= q[1] and q[2] <= my <= q[3] for q in r["rects"]):
            return fl, r
    return fl, None


# ------------------------------------------------------------------ one shot: push in with parallax
def frames_of(shot):
    img = load(os.path.join(STILLS, shot["name"] + ".jpg"), (W, H))[..., :3]
    dp = os.path.join(STILLS, shot["name"] + "_depth.npy")
    depth = None
    if os.path.exists(dp):
        d = np.load(dp).astype(np.float32)
        fin = np.isfinite(d) & (d > 0)
        far = float(np.max(d[fin])) if fin.any() else 10.0
        inv = np.where(fin, 1.0 / np.maximum(d, 0.05), 1.0 / (far * 4))   # the sky: far away
        # bilinear up to the picture, then soft: steps in depth would tear the picture apart at edges
        gy = np.linspace(0, inv.shape[0] - 1, H)
        gx = np.linspace(0, inv.shape[1] - 1, W)
        y0, x0 = np.floor(gy).astype(int), np.floor(gx).astype(int)
        y1, x1 = np.minimum(y0 + 1, inv.shape[0] - 1), np.minimum(x0 + 1, inv.shape[1] - 1)
        wy, wx = (gy - y0)[:, None], (gx - x0)[None, :]
        up = (inv[y0][:, x0] * (1 - wy) * (1 - wx) + inv[y0][:, x1] * (1 - wy) * wx +
              inv[y1][:, x0] * wy * (1 - wx) + inv[y1][:, x1] * wy * wx)
        for _ in range(3):                                      # box blurs, radius 1 % of the width
            r = max(1, W // 100)
            c = np.cumsum(np.pad(up, ((0, 0), (r + 1, r)), mode="edge"), axis=1)
            up = (c[:, 2 * r + 1:] - c[:, :-2 * r - 1]) / (2 * r + 1)
            c = np.cumsum(np.pad(up, ((r + 1, r), (0, 0)), mode="edge"), axis=0)
            up = (c[2 * r + 1:] - c[:-2 * r - 1]) / (2 * r + 1)
        depth = 1.0 / np.maximum(up, 1e-4)
    n = int(SEC * FPS)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = (W - 1) / 2, (H - 1) / 2
    med = float(np.median(depth)) if depth is not None else 1.0
    if depth is not None:          # a narrow range: parallax without bending straight edges near the sky
        depth = np.clip(depth, 0.7 * med, 1.6 * med)
    for i in range(n):
        u = i / max(1, n - 1)
        s = 0.5 - 0.5 * math.cos(math.pi * u)                  # ease in and out
        if depth is not None:                                  # forward by 6 % of the median depth
            dz = 0.06 * med * s
            f = np.clip((depth - dz) / depth, 0.6, 1.0)        # near things grow faster than far ones
        else:
            f = np.full((H, W), 1.0 / (1.0 + 0.07 * s), np.float32)
        sx = cx + (xx - cx) * f
        sy = cy + (yy - cy) * f
        x0 = np.clip(np.floor(sx).astype(int), 0, W - 2)
        y0 = np.clip(np.floor(sy).astype(int), 0, H - 2)
        ax, ay = (sx - x0)[..., None], (sy - y0)[..., None]
        yield (img[y0, x0] * (1 - ax) * (1 - ay) + img[y0, x0 + 1] * ax * (1 - ay) +
               img[y0 + 1, x0] * (1 - ax) * ay + img[y0 + 1, x0 + 1] * ax * ay)


titles = title_images([s.get("title") or s["name"] for s in order] + ([LABEL] if LABEL else []), os.path.dirname(os.path.abspath(OUT)))
ff = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                       "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                       "-pix_fmt", "yuv420p", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
tail = []
count = 0
for si, shot in enumerate(order):
    fl, room = room_of(shot)
    mm = minimap(fl, room)
    title = crop_text(titles[shot.get("title") or shot["name"]])
    frames = list(frames_of(shot))
    for i, fr in enumerate(frames):
        a = min(1.0, i / FADE, (len(frames) - 1 - i) / FADE + 0.0001)
        over(fr, mm, W - MAP - 40, 40, 0.9)
        over(fr, title, 60, H - title.shape[0] - 60, max(0.0, min(1.0, a * 1.5)))
        if LABEL:
            over(fr, crop_text(titles[LABEL]) * np.array([1, 1, 1, 0.7], np.float32), 60, 40)
        if tail and i < FADE:                                  # crossfade from the last shot
            k = (i + 1) / (FADE + 1)
            fr = tail[i] * (1 - k) + fr * k
        if i >= len(frames) - FADE and si < len(order) - 1:
            tail.append(fr)
            continue
        ff.stdin.write((np.clip(fr, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
        count += 1
    if si < len(order) - 1:
        tail = tail[-FADE:]
    else:
        tail = []
ff.stdin.close()
ff.wait()
print(f"FAST TOUR {count} frames, {count / FPS:.1f} s, {len(order)} shots -> {OUT}", flush=True)
