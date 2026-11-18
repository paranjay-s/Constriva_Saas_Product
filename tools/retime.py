"""Speed up the start of a rendered tour without re-rendering: frames before UNTIL seconds play SPEED x faster,
easing back to 1x over the last EASE seconds; room times in timeline.json shift to match.
python3 tools/retime.py SRC_RENDER_DIR DST_RENDER_DIR UNTIL SPEED [EASE]   (then tools/titles.py on DST)"""
import json, os, sys

src, dst, until, speed = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
ease = float(sys.argv[5]) if len(sys.argv) > 5 else 6.0
tl = json.load(open(os.path.join(src, "timeline.json")))
fps = tl["fps"]
names = sorted(n for n in os.listdir(os.path.join(src, "frames")) if n.startswith("f_"))
end, e0 = until * fps, (until - ease) * fps

picks, pos = [], 0.0
while round(pos) < int(end):
    picks.append(round(pos))
    u = min(max((pos - e0) / (end - e0), 0), 1)          # 0 before the ease, 1 at the end
    pos += speed + (1 - speed) * u * u * (3 - 2 * u)      # smoothstep from SPEED to 1x
picks += range(int(end), len(names))
assert picks == sorted(picks) and picks[-1] == len(names) - 1

out = os.path.join(dst, "frames")
os.makedirs(out, exist_ok=True)
for n in os.listdir(out):
    os.remove(os.path.join(out, n))
for k, i in enumerate(picks):
    os.symlink(os.path.abspath(os.path.join(src, "frames", names[i])), os.path.join(out, f"f_{k:05d}.jpg"))
shift = (len(names) - len(picks)) / fps
tl["rooms"] = [[t if t < 1 else round(t - shift, 2), r] for t, r in tl["rooms"]]
tl["duration"] = len(picks) / fps
json.dump(tl, open(os.path.join(dst, "timeline.json"), "w"), indent=1)
print(f"opening {until:.1f}s -> {until - shift:.1f}s, video {len(names) / fps:.1f}s -> {tl['duration']:.1f}s")
