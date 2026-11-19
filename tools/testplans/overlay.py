"""Draw a plan's truth (green) and its reading (red) over the drawing, one image per storey.

    uv --directory backend run python ../tools/testplans/overlay.py PLANS_DIR DUMP_DIR OUT_DIR ID [ID ...]

Walls are their centre lines, as the scorer sees them (score_plan.centre_lines). Truth is in feet from the plan's
origin; the reading is placed with its own floor origin_pt and scale_pt_per_ft when it has them (the detector), and
otherwise fitted to the truth's bounding box (the AI reader, whose plan has no page frame). Rooms of the reading are
outlined thinly in red with their type.
"""

import json
import sys
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw

DPI = 110


def page(pdf: Path) -> Image.Image:
    doc = pymupdf.open(pdf)
    pix = doc[0].get_pixmap(dpi=DPI)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def bbox(walls):
    xs = [v for w in walls for v in w[:2]]
    ys = [v for w in walls for v in w[2:4]]
    return (min(xs), max(xs), min(ys), max(ys)) if xs else (0, 1, 0, 1)


def main() -> None:
    plans, dump, out = (Path(a) for a in sys.argv[1:4])
    out.mkdir(parents=True, exist_ok=True)
    k = DPI / 72
    for pid in sys.argv[4:]:
        ref = json.loads((plans / f"{pid}.json").read_text())
        det = json.loads((dump / f"{pid}.det.json").read_text())
        base = page(plans / f"{pid}.pdf")
        for i, rf in enumerate(ref["floors"]):
            im = base.copy()
            d = ImageDraw.Draw(im, "RGBA")
            # the truth's frame on the page (written by generate.py)
            ox, oy, s = rf["origin_pt"][0], rf["origin_pt"][1], rf["scale_pt_per_ft"]

            def truth(x, y, ox=ox, oy=oy, s=s):
                return ((ox + x * s) * k, (oy - y * s) * k)

            for w in rf["walls"]:
                cx, cy = (w[0] + w[1]) / 2, (w[2] + w[3]) / 2
                a, b = ((w[0], cy), (w[1], cy)) if w[1] - w[0] >= w[3] - w[2] else ((cx, w[2]), (cx, w[3]))
                d.line([truth(*a), truth(*b)], fill=(20, 160, 60, 255), width=5)
            df = det["floors"][i] if i < len(det.get("floors", [])) else None
            if df:
                if df.get("origin_pt") and det.get("scale_pt_per_ft"):
                    X0, Y1, S = df["origin_pt"][0], df["origin_pt"][1], det["scale_pt_per_ft"]

                    def mine(x, y, X0=X0, Y1=Y1, S=S):
                        return ((X0 + x * S) * k, (Y1 - y * S) * k)
                else:  # no page frame: map the reading's walls onto the truth's extent
                    t, m = bbox(rf["walls"]), bbox(df.get("walls", []))

                    def mine(x, y, t=t, m=m):
                        u = t[0] + (x - m[0]) * (t[1] - t[0]) / max(1e-6, m[1] - m[0])
                        v = t[2] + (y - m[2]) * (t[3] - t[2]) / max(1e-6, m[3] - m[2])
                        return truth(u, v)

                for r in df.get("rooms", []):
                    for q in r.get("rects", []):
                        p0, p1 = mine(q[0], q[3]), mine(q[1], q[2])
                        d.rectangle([min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1])],
                                    outline=(200, 40, 40, 110), width=1)
                    if r.get("rects"):
                        q = r["rects"][0]
                        d.text(mine((q[0] + q[1]) / 2, (q[2] + q[3]) / 2), str(r.get("type", "")), fill=(200, 40, 40, 255))
                for w in df.get("walls", []):
                    cx, cy = (w[0] + w[1]) / 2, (w[2] + w[3]) / 2
                    a, b = ((w[0], cy), (w[1], cy)) if w[1] - w[0] >= w[3] - w[2] else ((cx, w[2]), (cx, w[3]))
                    d.line([mine(*a), mine(*b)], fill=(220, 30, 30, 230), width=2)
            d.text((12, 12), f"{pid} {rf.get('name', '')}: truth green, reading red", fill=(0, 0, 0, 255))
            im.save(out / f"{pid}_f{i}.png")
            print(out / f"{pid}_f{i}.png")


if __name__ == "__main__":
    main()
