"""Plan a continuous walking tour (stop - turn - walk, with a slow look-around in each room).
python3 tools/tour.py meta.json waypoints.json out_dir   -> out_dir/frames.json, out_dir/labels.ass
waypoints.json: [[x, y, look], ...] in metres; look = seconds to pan around the room at that point (0 = none)."""
import json, math, sys

FPS, SPEED, TURN, PITCH = 30, 1.0, math.radians(75), math.radians(-6)   # m/s, rad/s


def ease(t):
    return t * t * (3 - 2 * t)


def tour(wps):
    """-> frames [(x, y, yaw, pitch)]"""
    out = []
    x, y = wps[0][:2]
    yaw = math.atan2(-(wps[1][0] - x), wps[1][1] - y)

    def turn_to(target):
        nonlocal yaw
        d = (target - yaw + math.pi) % (2 * math.pi) - math.pi
        n = max(1, int(abs(d) / TURN * FPS))
        y0 = yaw
        for i in range(1, n + 1):
            out.append((x, y, y0 + d * ease(i / n), PITCH))
        yaw = y0 + d

    for k, (tx, ty, look) in enumerate(wps[1:], 1):
        dx, dy = tx - x, ty - y
        L = math.hypot(dx, dy)
        if L < 0.05:
            continue
        head = math.atan2(-dx, dy)
        d = abs((head - yaw + math.pi) % (2 * math.pi) - math.pi)
        if d > math.radians(25):
            turn_to(head)
        n = max(2, int(L / SPEED * FPS))
        x0, y0, yaw0 = x, y, yaw
        dh = (head - yaw0 + math.pi) % (2 * math.pi) - math.pi
        for i in range(1, n + 1):
            t = i / n
            s = t if 0.15 < t < 0.85 else ease(t)      # gentle start / stop
            x, y = x0 + dx * s, y0 + dy * s
            out.append((x, y, yaw0 + dh * min(1, t * 3), PITCH))
        yaw = yaw0 + dh
        if look:                                       # pan left, right, back to the heading
            base, n = yaw, int(look * FPS)
            for i in range(1, n + 1):
                t = i / n
                out.append((x, y, base + math.radians(70) * math.sin(2 * math.pi * ease(t)), PITCH))
    return out


def room_at(meta, x, y):
    for r in meta["floors"][0]["rooms"]:
        for q in r["rects"]:
            if q[0] - 0.05 <= x <= q[1] + 0.05 and q[2] - 0.05 <= y <= q[3] + 0.05:
                return "BEDROOM" if r["label"].startswith("BED ROOM") else r["label"].split(" ")[0]
    return None


if __name__ == "__main__":
    meta = json.load(open(sys.argv[1]))
    wps = json.load(open(sys.argv[2]))
    frames = tour(wps)
    od = sys.argv[3]
    json.dump(frames, open(f"{od}/frames.json", "w"))
    # room captions (ASS subtitles): one event per run of frames in the same room
    names = {"FAMILY": "Family hall", "MAID": "Maid room", "BEDROOM": "Bedroom", "BATH": "Bath", "DRESS": "Dressing",
             "KITCHEN": "Kitchen", "STORE": "Store", "LOBBY": "Lobby", "GARDEN": "Garden", "ENTRANCE": "Entrance"}
    lab, ev, start = None, [], 0
    for i, (x, y, *_ ) in enumerate(frames + [(-99, -99, 0, 0)]):
        r = room_at(meta, x, y) if i < len(frames) else "END"
        r = r or lab
        if r != lab:
            if lab:
                ev.append((start / FPS, i / FPS, names.get(lab, lab.title())))
            lab, start = r, i
    t = lambda s: f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"
    ass = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1280", "PlayResY: 720", "",
           "[V4+ Styles]", "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginV",
           "Style: Room, Noto Sans, 34, &H00FFFFFF, &H00000000, &H80000000, 1, 1, 2, 1, 7, 40, 36", "",
           "[Events]", "Format: Layer, Start, End, Style, Text"]
    ass += [f"Dialogue: 0, {t(a)}, {t(b)}, Room, {{\\fad(300,300)}}{n}" for a, b, n in ev if b - a > 0.6]
    open(f"{od}/labels.ass", "w").write("\n".join(ass) + "\n")
    print(len(frames), "frames", round(len(frames) / FPS, 1), "s;", [n for _, _, n in ev])
