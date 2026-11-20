"""Join a rendered tour's frames into its film with room titles and a minimap (PATCHES 57).

    blender -b --factory-startup -P tools/tour_join.py -- FRAMES_DIR TIMELINE.json META.json OUT.mp4 [--fps 30]
            [--label Evening]

TIMELINE.json is what cinema.py writes beside the frames: {"fps", "duration", "rooms": [[seconds, label], ...]}.
On entering a room its title fades in for TITLE_S seconds; the minimap (top right) shows that room's storey with the
room lit. Frames are composited in NumPy and piped to ffmpeg (libx264, yuv420p), so nothing is written twice.
"""

import glob
import json
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from overlay import MAP, crop_text, load, minimap, over, title_images  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
FRAMES, TIMELINE, META, OUT = argv[:4]
FPS = int(argv[argv.index("--fps") + 1]) if "--fps" in argv else 30
LABEL = argv[argv.index("--label") + 1] if "--label" in argv else ""
TITLE_S = 3.0
tl = json.load(open(TIMELINE))
meta = json.load(open(META))
frames = sorted(glob.glob(os.path.join(FRAMES, "f_*.jpg")))
if not frames:
    raise SystemExit("no frames")
first = load(frames[0])
H, W = first.shape[:2]
rooms = [(float(t), str(label)) for t, label in tl.get("rooms", [])]


def find(label):
    for f in meta["floors"]:
        for r in f["rooms"]:
            if (r.get("label") or "").strip().lower() == label.strip().lower():
                return f, r
    return meta["floors"][0], None


maps = {}
titles = title_images(sorted({lb for _, lb in rooms if lb}) + ([LABEL] if LABEL else []),
                      os.path.dirname(os.path.abspath(OUT)))
ff = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                       "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                       "-pix_fmt", "yuv420p", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
for i, path in enumerate(frames):
    t = i / FPS
    now = [(t0, lb) for t0, lb in rooms if t0 <= t]
    fr = load(path)[..., :3] if i else first[..., :3]
    if now:
        t0, lb = now[-1]
        if lb not in maps:
            fl, r = find(lb)
            maps[lb] = minimap(fl, r)
        over(fr, maps[lb], W - MAP - 40, 40, 0.9)
        age = t - t0
        if age < TITLE_S and lb in titles:
            a = min(1.0, age / 0.5, (TITLE_S - age) / 0.5)
            ti = crop_text(titles[lb])
            over(fr, ti, 60, H - ti.shape[0] - 60, a)
    if LABEL:
        over(fr, crop_text(titles[LABEL]), 60, 40, 0.7)
    ff.stdin.write((np.clip(fr, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
ff.stdin.close()
ff.wait()
print(f"TOUR JOINED {len(frames)} frames -> {OUT}", flush=True)
