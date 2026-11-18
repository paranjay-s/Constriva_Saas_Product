"""Room titles in the style of the reference tour (small spaced kicker, big thin uppercase name, mono caption),
then the final MP4.  python3 tools/titles.py RENDER_DIR TITLES.json OUT.mp4
TITLES.json: {"opening": [kicker, title, caption], "closing": [...], "rooms": {"ROOM KEY": [kicker, title, caption], ...}}
RENDER_DIR has frames/f_#####.jpg and timeline.json (written by blender/cinema.py)."""
import json, os, subprocess, sys

R, spec, out = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]
tl = json.load(open(os.path.join(R, "timeline.json")))
fps, dur = tl["fps"], tl["duration"]
W, H = 1920, 1080
t = lambda s: f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"
ass = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2", "",
       "[V4+ Styles]",
       "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
       "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
       "Style: Kick, Noto Sans Medium, 22, &H00F0F4F7, &H00FFFFFF, &H00000000, &H78000000, 0, 0, 0, 0, 100, 100, 6, 0, 1, 0, 1, 7, 0, 0, 0, 1",
       "Style: Title, Noto Sans Light, 104, &H00FFFFFF, &H00FFFFFF, &H00000000, &H70000000, 0, 0, 0, 0, 100, 100, 1, 0, 1, 0, 2, 7, 0, 0, 0, 1",
       "Style: Cap, DejaVu Sans Mono, 20, &H00E6EBEE, &H00FFFFFF, &H00000000, &H78000000, 0, 0, 0, 0, 100, 100, 5, 0, 1, 0, 1, 7, 0, 0, 0, 1",
       "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]


def card(a, b, kicker, title, caption, side):
    """one title card from a to b seconds; side 'l' / 'r' / 'c' like the reference's alternating placement"""
    lines = title.split("\n")
    an = {"l": 7, "r": 9, "c": 8}[side]
    x = {"l": 110, "r": W - 110, "c": W // 2}[side]
    y = 330 if side != "c" else 380
    tag = lambda dy, d0: (f"{{\\an{an}\\move({x},{y + dy + 26},{x},{y + dy},{d0},{d0 + 700})"
                          f"\\fad({300 + d0},450)}}")
    ass.append(f"Dialogue: 2, {t(a)}, {t(b)}, Kick,, 0, 0, 0,, {tag(-52, 0)}{kicker.upper()}")
    for k, ln in enumerate(lines):
        ass.append(f"Dialogue: 2, {t(a)}, {t(b)}, Title,, 0, 0, 0,, {tag(k * 108, 120 + 80 * k)}{ln.upper()}")
    if caption:
        ass.append(f"Dialogue: 2, {t(a)}, {t(b)}, Cap,, 0, 0, 0,, {tag(len(lines) * 108 + 22, 320)}{caption.upper()}")


op = spec["opening"]
card(0.6, 6.5, *op, "c")
seen, rooms = {}, []
for s, r in tl["rooms"]:          # a name met twice (second suite's bath) may have its own entry "NAME#2"
    seen[r] = seen.get(r, 0) + 1
    key = f"{r}#{seen[r]}" if f"{r}#{seen[r]}" in spec["rooms"] else r
    if key in spec["rooms"] and s > 1:
        rooms.append((s, key))
for k, (s, r) in enumerate(rooms):
    nxt = rooms[k + 1][0] if k + 1 < len(rooms) else dur
    cat, title, cap = spec["rooms"][r]
    card(s + 0.4, min(s + 4.6, nxt - 0.2), f"{k + 1:02d} / {cat}", title, cap, "lr"[k % 2])
cl = spec["closing"]
card(dur - 4.8, dur - 0.3, *cl, "c")
sub = os.path.join(R, "titles.ass")
open(sub, "w").write("\n".join(ass) + "\n")

vf = (f"subtitles={sub},vignette=angle=0.35,fade=in:0:{int(fps * 1.2)},"
      f"fade=out:st={dur - 1.2:.2f}:d=1.2,format=yuv420p")
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(fps),
                "-i", os.path.join(R, "frames", "f_%05d.jpg"), "-vf", vf, "-c:v", "libx264", "-preset", "slow",
                "-crf", "18", "-movflags", "+faststart", out], check=True)
print("wrote", out)
