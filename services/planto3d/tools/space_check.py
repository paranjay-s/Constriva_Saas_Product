"""How big do the rooms read? Plan size against what the 3D builds (PART C1, docs/pro2/3d/SPACE.md).

    python3 tools/space_check.py PLAN.json [META.json] [--md]

Per room: the size its label states, the size read from the drawing (the room's largest rectangle, inside
the wall faces), the difference, how much of the rectangle walls take (walls must not eat into a room beyond
the drawing), and with a built house (meta.json) the number of furniture pieces, the share of the floor they
cover and the narrowest gap between them and the walls along the room's long axis. Then the heights and
cameras the build uses.
"""
import json
import math
import re
import sys

LABEL = re.compile(r"""(\d+)\s*'?\s*-?\s*(\d+)?\s*"?\s*[xX×]\s*(\d+)\s*'?\s*-?\s*(\d+)?\s*"?""")
M = 0.3048


def label_ft(label):
    m = LABEL.search(label or "")
    if not m:
        return None
    a = int(m.group(1)) + int(m.group(2) or 0) / 12
    b = int(m.group(3)) + int(m.group(4) or 0) / 12
    return sorted((a, b))


def overlap(a, b):
    w = min(a[1], b[1]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[2], b[2])
    return w * h if w > 0 and h > 0 else 0.0


def main():
    plan = json.load(open(sys.argv[1]))
    meta = json.load(open(sys.argv[2])) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
    md = "--md" in sys.argv
    rows = []
    for k, f in enumerate(plan["floors"]):
        walls = [w[:4] for w in f["walls"]]
        mf = meta["floors"][k] if meta and k < len(meta["floors"]) else None
        furn = [b for b in (mf or {}).get("furniture", []) if isinstance(b, list) and len(b) >= 4]
        for r in f["rooms"]:
            if not r.get("rects"):
                continue
            q = max(r["rects"], key=lambda t: (t[1] - t[0]) * (t[3] - t[2]))
            w, h = sorted((q[1] - q[0], q[3] - q[2]))
            lab = label_ft(r.get("label"))
            diff = max(abs(w - lab[0]) / lab[0], abs(h - lab[1]) / lab[1]) if lab else None
            area = (q[1] - q[0]) * (q[3] - q[2])
            eaten = sum(overlap(q, wl) for wl in walls) / area if area else 0
            pieces = share = gap = None
            if mf is not None:  # meta furniture boxes are in metres, the plan in feet
                qm = [v * M for v in q]
                inside = [b for b in furn if qm[0] <= (b[0] + b[1]) / 2 <= qm[1] and qm[2] <= (b[2] + b[3]) / 2 <= qm[3]]
                pieces = len(inside)
                share = sum((b[1] - b[0]) * (b[3] - b[2]) for b in inside) / (area * M * M)
                long_x = (qm[1] - qm[0]) >= (qm[3] - qm[2])
                gaps = []
                for b in inside:  # free distance across the room's short axis beside each piece
                    if long_x:
                        gaps.append(max(b[2] - qm[2], qm[3] - b[3]))
                    else:
                        gaps.append(max(b[0] - qm[0], qm[1] - b[1]))
                gap = min(gaps) if gaps else None
            rows.append(dict(floor=f.get("name", k), room=r.get("label") or r["type"], type=r["type"],
                             label=lab, read=[round(w, 2), round(h, 2)], diff=diff, walls_in=eaten,
                             pieces=pieces, share=share, gap=gap))
    H = plan.get("floor_height", 10.0)
    if md:
        print("| Floor | Room | Label (ft) | Read inside the walls (ft) | Diff | Walls inside the room | Pieces | Floor covered | Widest free strip beside the tightest piece (m) |")
        print("|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            lab = f"{r['label'][0]:.1f} x {r['label'][1]:.1f}" if r["label"] else "-"
            d = f"{r['diff']:.0%}" if r["diff"] is not None else "-"
            print(f"| {r['floor']} | {r['room']} | {lab} | {r['read'][0]:.1f} x {r['read'][1]:.1f} | {d} | {r['walls_in']:.1%} | "
                  f"{'-' if r['pieces'] is None else r['pieces']} | {'-' if r['share'] is None else format(r['share'], '.0%')} | "
                  f"{'-' if r['gap'] is None else format(r['gap'], '.2f')} |")
    else:
        for r in rows:
            print(r)
    labelled = [r for r in rows if r["diff"] is not None]
    within = sum(r["diff"] <= 0.05 for r in labelled)
    ceiling = (meta or {}).get("ceiling_m") or H * M
    doors = (meta or {}).get("door_head_m") or 7.0 * M
    print(f"\nlabelled rooms {len(labelled)}, within 5 % of their label {within}; "
          f"floor to ceiling {ceiling:.2f} m; doors {doors:.2f} m; eye {meta['eye'] if meta else 1.6} m")
    if meta and meta.get("fov_h"):
        print(f"walkthrough: horizontal FOV {meta['fov_h']:g} deg on every window shape (Wide view; 65 normal)")
    else:
        for aspect in (16 / 9, 4 / 3):
            v = 70
            hfov = 2 * math.degrees(math.atan(math.tan(math.radians(v / 2)) * aspect))
            print(f"walkthrough: vertical FOV {v} deg -> horizontal {hfov:.0f} deg at {aspect:.2f}:1")


if __name__ == "__main__":
    main()
