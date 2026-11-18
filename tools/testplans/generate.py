"""Random but plausible floor plans with a known answer, drawn as PDFs in many styles.

    uv --directory backend run python ../tools/testplans/generate.py OUT_DIR [--n 200] [--seed 7] [--held-out 50]

Each plan k writes OUT_DIR/<id>.json (the answer, in PlanTo3D's plan JSON: feet, per floor origin at the lower-left of
the walls, rects [x0, x1, y0, y1]) and OUT_DIR/<id>.pdf (the drawing). OUT_DIR/index.json lists every plan with its
style, units, label language, storeys, special areas and whether it is held out (scored only, never tuned on).

Styles: lines (CAD double lines), solid (filled wall bands, coloured floors), hatched (outline + diagonal hatch),
fills (double lines + coloured floors); and raster_<style>: the drawing rasterised at 72-300 dpi, maybe rotated up to
5 degrees or by 90, with noise, blur and JPEG artefacts, embedded as a scanned page.
The vocabulary (labels per type) comes from services/planto3d/web/rooms.json, so the generator and the readers
share it; generated labels include sizes in feet-inches or metric.
"""
import argparse
import io
import json
import math
import random
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
VOCAB = json.loads((ROOT / "services/planto3d/web/rooms.json").read_text("utf-8"))
ARABIC_FONT = next((p for p in ("/Library/Fonts/Arial Unicode.ttf", "/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
                    if Path(p).exists()), None)
EXT, INT = 0.75, 0.375                 # wall thickness, feet
STYLES = ["lines", "solid", "hatched", "fills"]
SPECIAL_OUT = ["pool", "plunge pool", "jacuzzi", "fountain", "dock", "jetty", "water body", "parking", "carport",
               "tennis court", "padel court", "basketball court", "garden", "lawn"]
SPECIAL_IN = ["lift", "service lift", "cold store", "hot store", "majlis", "prayer room", "gym", "cinema", "bar",
              "breakfast area", "show kitchen", "foyer", "guest bedroom", "maid room", "driver room"]
# what a special area's label is and the room type a correct reader gives it
SPECIAL_TYPE = {"pool": "pool", "plunge pool": "pool", "jacuzzi": "pool", "fountain": "water", "dock": "dock",
                "jetty": "dock", "water body": "water", "parking": "parking", "carport": "parking",
                "tennis court": "court", "padel court": "court", "basketball court": "court", "garden": "garden",
                "lawn": "garden", "lift": "lift", "service lift": "lift", "cold store": "store", "hot store": "store",
                "majlis": "living", "prayer room": "puja", "gym": "gym", "cinema": "cinema", "bar": "bar",
                "breakfast area": "breakfast", "show kitchen": "kitchen", "foyer": "foyer", "guest bedroom": "bedroom",
                "maid room": "bedroom", "driver room": "bedroom"}
ARABIC = {"bedroom": "غرفة نوم", "toilet": "حمام", "kitchen": "مطبخ", "living": "مجلس", "dining": "غرفة طعام",
          "store": "مخزن", "wash": "غرفة غسيل", "passage": "ممر", "foyer": "مدخل", "pool": "مسبح", "lift": "مصعد",
          "puja": "مصلى", "parking": "موقف سيارات", "garden": "حديقة", "stair": "درج", "balcony": "شرفة"}


def split(rng, rect, n, min_side=8.0):
    """guillotine split of rect into about n rooms -> list of (rect, list of (rect_a, rect_b, axis, at) splits)"""
    x0, x1, y0, y1 = rect
    if n <= 1 or (x1 - x0 < 2 * min_side and y1 - y0 < 2 * min_side):
        return [rect], []
    vertical = (x1 - x0) >= (y1 - y0) if rng.random() < 0.8 else rng.random() < 0.5
    if vertical and x1 - x0 < 2 * min_side:
        vertical = False
    if not vertical and y1 - y0 < 2 * min_side:
        vertical = True
    lo, hi = (x0, x1) if vertical else (y0, y1)
    at = round(rng.uniform(lo + min_side, hi - min_side) * 2) / 2
    na = max(1, round(n * (at - lo) / (hi - lo)))
    a, b = ((x0, at, y0, y1), (at, x1, y0, y1)) if vertical else ((x0, x1, y0, at), (x0, x1, at, y1))
    ra, sa = split(rng, a, na, min_side)
    rb, sb = split(rng, b, n - na, min_side)
    return ra + rb, sa + sb + [(a, b, "v" if vertical else "h", at)]


def fmt_size(w, d, metric, rng):
    if metric:
        if rng.random() < 0.5:
            return f"{w * 0.3048:.2f} x {d * 0.3048:.2f} m"
        return f"{round(w * 30.48)}X{round(d * 30.48)}"
    def fi(v):
        f, i = int(v), round((v - int(v)) * 12)
        if i == 12:
            f, i = f + 1, 0
        return f"{f}'" + (f"{i}\"" if i else "")
    return f"{fi(w)}X{fi(d)}"


def label_for(rng, typ, lang, special=None):
    if special:
        words = special.upper()
        return ARABIC.get(typ, words) if lang == "ar" and rng.random() < 0.5 else words
    if lang == "ar" and typ in ARABIC and rng.random() < 0.7:
        return ARABIC[typ]
    phrases = [p for p in VOCAB["phrases"].get(typ, [typ.upper()]) if p.isascii() and len(p) > 2]
    return rng.choice(phrases[:6]) if phrases else typ.upper()


def make_plan(rng, pid):
    storeys = rng.choices([1, 2, 3], weights=[4, 4, 2])[0]
    kind = rng.choice(["villa", "villa", "townhouse", "apartment"]) if storeys == 1 else rng.choice(["villa", "townhouse"])
    W = round(rng.uniform(26, 44) if kind == "townhouse" else rng.uniform(36, 66))
    D = round(rng.uniform(36, 60))
    metric, lang = rng.random() < 0.4, rng.choices(["en", "ar"], weights=[4, 1])[0] if ARABIC_FONT else "en"
    specials_in = rng.sample(SPECIAL_IN, rng.randint(1, 4))
    specials_out = [] if kind == "apartment" else rng.sample(SPECIAL_OUT, rng.randint(1, 3))
    stair = (W - EXT - 9.5, W - EXT, D - EXT - 9.0, D - EXT) if storeys > 1 else None   # a 9.5 x 9 ft stair room
    floors = []
    for k in range(storeys):
        inner = (EXT, W - EXT, EXT, D - EXT)
        n = max(4, int((W * D) / rng.uniform(140, 220)))
        rects, splits = split(rng, inner, n)
        # the stair room is carved out of whichever room holds its corner
        if stair:
            rects = [r for r in rects if not (r[0] < stair[1] and r[1] > stair[0] and r[2] < stair[3] and r[3] > stair[2])
                     or (r[1] - r[0]) * (r[3] - r[2]) > 3 * 85.5] + [stair]
        floors.append(dict(name=["GROUND FLOOR", "FIRST FLOOR", "SECOND FLOOR"][k], rects=rects, splits=splits))
    plan_floors, specials_found = [], []
    for k, fl in enumerate(floors):
        rects = sorted(fl["rects"], key=lambda r: -(r[1] - r[0]) * (r[3] - r[2]))
        types = []
        pool = (["living", "kitchen", "dining"] if k == 0 else ["living"]) + ["bedroom"] * 6 + ["toilet"] * 4 + ["store", "wash", "dress", "study"]
        for r in rects:
            if stair and r == stair:
                types.append(("stair", None))
            elif specials_in and rng.random() < 0.35:
                sp = specials_in.pop()
                types.append((SPECIAL_TYPE[sp], sp))
            else:
                types.append((pool.pop(0) if pool else "room", None))
        rooms = []
        for r0, (t, sp) in zip(rects, types):
            # the room is the clear space between wall faces (what a drawing labels and a reader finds); interior
            # walls are centred on the split lines
            r = (r0[0] + (INT / 2 if r0[0] > EXT + 0.01 else 0), r0[1] - (INT / 2 if r0[1] < W - EXT - 0.01 else 0),
                 r0[2] + (INT / 2 if r0[2] > EXT + 0.01 else 0), r0[3] - (INT / 2 if r0[3] < D - EXT - 0.01 else 0))
            if t == "toilet" and (r[1] - r[0]) * (r[3] - r[2]) > 140:
                t = "bedroom"
            label = label_for(rng, t, lang, sp)
            area = (r[1] - r[0]) * (r[3] - r[2])
            rooms.append(dict(type=t, label=label, special=sp, rects=[list(r)], area=round(area, 1), split=list(r0),
                              size=fmt_size(r[1] - r[0], r[3] - r[2], metric, rng)))
        # open plan: a kitchen, dining or living room next to another one loses the wall between them
        open_pairs = []
        if rng.random() < 0.5:
            for i, a in enumerate(rooms):
                for j, b in enumerate(rooms):
                    if i < j and {a["type"], b["type"]} <= {"kitchen", "dining", "living"} and _shared(a["split"], b["split"]):
                        open_pairs.append((i, j))
        walls, openings = _walls(rng, W, D, rooms, open_pairs, k, storeys)
        stairs = []
        if stair:
            x0, x1, y0, y1 = stair
            mid = (y0 + y1) / 2
            stairs = [dict(rect=[x0 + 0.5, x1 - 2.5, y0 + 0.3, mid - 0.2], axis="x", steps=9, up=True),
                      dict(rect=[x0 + 0.5, x1 - 2.5, mid + 0.2, y1 - 0.3], axis="x", steps=9, up=True)]
        plan_floors.append(dict(name=fl["name"].title(), level=k, walls=walls, openings=openings, rooms=rooms,
                                stairs=stairs, open_pairs=open_pairs))
    # outside: special areas in a strip south (front) and north (back) of the house, beyond a garden margin
    outside = []
    if specials_out:
        x = 2.0
        for sp in specials_out:
            w = {"tennis court": 36.0, "padel court": 33.0, "basketball court": 30.0, "parking": 20.0, "carport": 18.0}.get(sp, rng.uniform(10, 22))
            d = {"tennis court": 78.0, "padel court": 66.0, "basketball court": 50.0}.get(sp, rng.uniform(10, 18))
            y0 = D + 6 if sp not in ("parking", "carport") else -(d + 6)
            outside.append(dict(type=SPECIAL_TYPE[sp], label=label_for(rng, SPECIAL_TYPE[sp], lang, sp), special=sp,
                                rects=[[x, x + w, y0, y0 + d]], area=round(w * d, 1), size=fmt_size(w, d, metric, rng)))
            x += w + 4
        plan_floors[0]["rooms"] += outside
        specials_found += [o["special"] for o in outside]
    return dict(id=pid, kind=kind, storeys=storeys, metric=metric, lang=lang, units="ft", floors=plan_floors,
                specials=[r["special"] for f in plan_floors for r in f["rooms"] if r.get("special")], footprint=[W, D])


def _shared(a, b):
    return (abs(a[1] - b[0]) < 0.01 or abs(b[1] - a[0]) < 0.01) and min(a[3], b[3]) - max(a[2], b[2]) > 4 or \
           (abs(a[3] - b[2]) < 0.01 or abs(b[3] - a[2]) < 0.01) and min(a[1], b[1]) - max(a[0], b[0]) > 4


def _walls(rng, W, D, rooms, open_pairs, k, storeys):
    """exterior walls with a front door and windows; one interior wall per shared room edge with a door (none between
    open-plan zones). -> (walls [x0, x1, y0, y1, low], openings [{type, rect, axis}])"""
    walls, openings = [], []

    def run(x0, x1, y0, y1, gaps, axis):
        """a wall run with openings cut in it: gaps = [(a, b, type)] along the run"""
        a = x0 if axis == "x" else y0
        for g0, g1, t in sorted(gaps):
            if g0 - a > 0.3:
                walls.append([a, g0, y0, y1, 0] if axis == "x" else [x0, x1, a, g0, 0])
            openings.append(dict(type=t, rect=[g0, g1, y0, y1] if axis == "x" else [x0, x1, g0, g1], axis=axis))
            a = g1
        end = x1 if axis == "x" else y1
        if end - a > 0.3:
            walls.append([a, end, y0, y1, 0] if axis == "x" else [x0, x1, a, end, 0])

    # exterior: windows on each room's outer sides, a front door on the south wall (ground floor)
    def outer_gaps(side):
        gaps = []
        for r in rooms:
            q = r.get("split", r["rects"][0])
            on = {"S": q[2] <= EXT + 0.01, "N": q[3] >= D - EXT - 0.01, "W": q[0] <= EXT + 0.01, "E": q[1] >= W - EXT - 0.01}[side]
            if not on or r["type"] == "stair":
                continue
            lo, hi = (q[0], q[1]) if side in "NS" else (q[2], q[3])
            if hi - lo > 7:
                c = (lo + hi) / 2 + rng.uniform(-1, 1)
                gaps.append((round(c - 2, 2), round(c + 2, 2), "window"))
        return gaps
    south = outer_gaps("S")
    if k == 0:
        c = W / 2
        south = [g for g in south if g[1] < c - 2 or g[0] > c + 2] + [(c - 1.75, c + 1.75, "door")]
    run(0, W, 0, EXT, south, "x")
    run(0, W, D - EXT, D, outer_gaps("N"), "x")
    run(0, EXT, EXT, D - EXT, outer_gaps("W"), "y")
    run(W - EXT, W, EXT, D - EXT, outer_gaps("E"), "y")
    # interior: each shared edge between two rooms, a door in its middle (open-plan pairs: no wall at all)
    done = set()
    for i, a in enumerate(rooms):
        for j, b in enumerate(rooms):
            if j <= i or (i, j) in open_pairs:
                continue
            qa, qb = a.get("split", a["rects"][0]), b.get("split", b["rects"][0])
            for axis, line, lo, hi in _edges(qa, qb):
                key = (axis, round(line, 2), round(lo, 2), round(hi, 2))
                if key in done or hi - lo < 1:
                    continue
                done.add(key)
                h = INT / 2
                gaps = []
                if hi - lo >= 4 and "lift" not in (a["type"], b["type"]) or (a["type"] == "lift" or b["type"] == "lift") and hi - lo >= 4:
                    w = 2.5 if "toilet" in (a["type"], b["type"]) else 3.0
                    c = (lo + hi) / 2
                    gaps = [(c - w / 2, c + w / 2, "door")]
                if axis == "x":
                    run(lo, hi, line - h, line + h, gaps, "x")
                else:
                    run(line - h, line + h, lo, hi, gaps, "y")
    return walls, openings


def _edges(a, b):
    out = []
    for p, q in ((a, b), (b, a)):
        if abs(p[1] - q[0]) < 0.01:
            lo, hi = max(p[2], q[2]), min(p[3], q[3])
            if hi > lo:
                out.append(("y", p[1], lo, hi))
        if abs(p[3] - q[2]) < 0.01:
            lo, hi = max(p[0], q[0]), min(p[1], q[1])
            if hi > lo:
                out.append(("x", p[3], lo, hi))
    return out


# ------------------------------------------------------------------ drawing
COLOURS = {"bedroom": (0.93, 0.88, 0.95), "toilet": (0.85, 0.93, 0.98), "kitchen": (0.98, 0.92, 0.84),
           "living": (0.97, 0.95, 0.85), "dining": (0.97, 0.9, 0.86), "pool": (0.65, 0.85, 0.97), "water": (0.7, 0.88, 0.97),
           "dock": (0.6, 0.8, 0.95), "garden": (0.82, 0.93, 0.78), "court": (0.75, 0.85, 0.72), "parking": (0.88, 0.88, 0.9)}


def draw(plan, style, rng):
    """-> PDF bytes. Floors side by side on one landscape sheet, each titled; scale fixed per sheet."""
    W, D = plan["footprint"]
    extra = max([r["rects"][0][3] for r in plan["floors"][0]["rooms"]] + [D]) - min([r["rects"][0][2] for r in plan["floors"][0]["rooms"]] + [0])
    n = len(plan["floors"])
    pw, ph = (1191, 842) if n > 1 or extra > 70 else (842, 595)        # A3 for several storeys or a big site
    S = min((pw - 80) / (n * (W + 20)), (ph - 115) / (extra + 30))
    doc = pymupdf.open()
    page = doc.new_page(width=pw, height=ph)
    if ARABIC_FONT and plan["lang"] == "ar":
        page.insert_font(fontname="ar", fontfile=ARABIC_FONT)
    ymin = min([r["rects"][0][2] for r in plan["floors"][0]["rooms"]] + [0])
    for k, f in enumerate(plan["floors"]):
        ox, oy = 40 + k * (W + 20) * S, ph - 50 - (0 - ymin) * S
        P = lambda x, y: pymupdf.Point(ox + x * S, oy - y * S)
        shape = page.new_shape()
        if style in ("solid", "fills"):
            for r in f["rooms"]:
                q = r["rects"][0]
                shape.draw_rect(pymupdf.Rect(P(q[0], q[3]), P(q[1], q[2])))
                shape.finish(color=None, fill=COLOURS.get(r["type"], (0.95, 0.95, 0.93)), width=0)
        elif r_out := [r for r in f["rooms"] if r["type"] in ("pool", "water", "dock")]:
            for r in r_out:      # water is drawn blue in every style (a raster reader sees it too)
                q = r["rects"][0]
                shape.draw_rect(pymupdf.Rect(P(q[0], q[3]), P(q[1], q[2])))
                shape.finish(color=(0, 0, 0), fill=COLOURS[r["type"]], width=0.5)
        for w in f["walls"]:
            x0, x1, y0, y1 = w[:4]
            rect = pymupdf.Rect(P(x0, y1), P(x1, y0))
            shape.draw_rect(rect)
            if style == "solid":
                shape.finish(color=None, fill=(0.15, 0.15, 0.15), width=0)
            else:
                shape.finish(color=(0, 0, 0), width=0.6)
            if style == "hatched":
                step = 2.0
                xx = rect.x0 - rect.height
                while xx < rect.x1:
                    a = pymupdf.Point(max(xx, rect.x0), rect.y1 - max(0, rect.x0 - xx))
                    b = pymupdf.Point(min(xx + rect.height, rect.x1), rect.y0 + max(0, xx + rect.height - rect.x1))
                    shape.draw_line(a, b)
                    xx += step
                shape.finish(color=(0.3, 0.3, 0.3), width=0.25)
        for o in f["openings"]:
            x0, x1, y0, y1 = o["rect"]
            if o["type"] == "window":
                if o["axis"] == "x":
                    for t in (0.33, 0.66):
                        y = y0 + (y1 - y0) * t
                        shape.draw_line(P(x0, y), P(x1, y))
                    shape.draw_line(P(x0, y0), P(x1, y0)); shape.draw_line(P(x0, y1), P(x1, y1))
                else:
                    for t in (0.33, 0.66):
                        x = x0 + (x1 - x0) * t
                        shape.draw_line(P(x, y0), P(x, y1))
                    shape.draw_line(P(x0, y0), P(x0, y1)); shape.draw_line(P(x1, y0), P(x1, y1))
                shape.finish(color=(0.1, 0.3, 0.8) if style in ("solid", "fills") else (0, 0, 0), width=0.4)
            else:     # leaf and quarter-circle swing into the room above / right of the wall
                if o["axis"] == "x":
                    hinge, r = (x0, y1), x1 - x0
                    shape.draw_line(P(*hinge), P(hinge[0], hinge[1] + r))
                    shape.draw_curve(P(hinge[0], hinge[1] + r), P(hinge[0] + r * 0.55, hinge[1] + r), P(x1, y1))
                else:
                    hinge, r = (x1, y0), y1 - y0
                    shape.draw_line(P(*hinge), P(hinge[0] + r, hinge[1]))
                    shape.draw_curve(P(hinge[0] + r, hinge[1]), P(hinge[0] + r, hinge[1] + r * 0.55), P(x1, y1))
                shape.finish(color=(0.8, 0.1, 0.1) if style in ("solid", "fills") else (0, 0, 0), width=0.4)
        for st in f["stairs"]:
            x0, x1, y0, y1 = st["rect"]
            for i in range(st["steps"] + 1):
                x = x0 + (x1 - x0) * i / st["steps"]
                shape.draw_line(P(x, y0), P(x, y1))
            shape.finish(color=(0, 0, 0), width=0.3)
        shape.commit()
        for r in f["rooms"]:
            q = r["rects"][0]
            cx, cy = (q[0] + q[1]) / 2, (q[2] + q[3]) / 2
            fs = max(4.5, min(8.0, S * 0.9))
            arabic = not r["label"].isascii()
            for text, dy in ((r["label"], 0.6), (r["size"], -0.9)):
                if not text:
                    continue
                width = pymupdf.get_text_length(text, fontsize=fs) if not (arabic and text == r["label"]) else len(text) * fs * 0.5
                at = pymupdf.Point(ox + cx * S - width / 2, oy - (cy + dy) * S)
                page.insert_text(at, text, fontsize=fs, fontname="ar" if (arabic and text == r["label"]) else "helv")
        if f["stairs"]:
            st = f["stairs"][0]
            word = "UP" if k + 1 < len(plan["floors"]) else "DN"
            page.insert_text(P(st["rect"][1] - 1.5, (st["rect"][2] + st["rect"][3]) / 2), word, fontsize=6)
        title = f"{f['name'].upper()} PLAN"
        page.insert_text(pymupdf.Point(ox + W * S / 2 - pymupdf.get_text_length(title, fontsize=9) / 2, oy + 25), title, fontsize=9)
    page.insert_text(pymupdf.Point(40, 30), f"{plan['kind'].upper()}  -  PROPOSED {plan['storeys']}-STOREY {plan['kind'].upper()}", fontsize=10)
    doc.subset_fonts()          # (a whole Unicode font is 23 MB)
    return doc.tobytes(garbage=3, deflate=True)


def rasterise(pdf_bytes, rng):
    """the drawing as a scan: 72-300 dpi, maybe turned, noise, blur, JPEG -> (pdf bytes, how)"""
    dpi = rng.choice([72, 100, 150, 200, 300])
    page = pymupdf.open(stream=pdf_bytes, filetype="pdf")[0]
    pix = page.get_pixmap(dpi=dpi)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    how = [f"{dpi}dpi"]
    r = rng.random()
    if r < 0.25:
        im = im.rotate(90, expand=True); how.append("rot90")
    elif r < 0.7:
        a = rng.uniform(-5, 5); im = im.rotate(a, expand=True, fillcolor="white"); how.append(f"rot{a:.1f}")
    if rng.random() < 0.6:
        arr = np.asarray(im).astype(np.int16) + np.random.default_rng(rng.randint(0, 1 << 30)).normal(0, 8, (im.height, im.width, 3)).astype(np.int16)
        im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)); how.append("noise")
    if rng.random() < 0.5:
        im = im.filter(ImageFilter.GaussianBlur(rng.uniform(0.4, 1.2))); how.append("blur")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=rng.choice([45, 60, 75, 90]))
    doc = pymupdf.open()
    pg = doc.new_page(width=im.width * 72 / dpi, height=im.height * 72 / dpi)
    pg.insert_image(pg.rect, stream=buf.getvalue())
    return doc.tobytes(), "+".join(how)


def answer(plan):
    """the known answer as PlanTo3D plan JSON (helpers like `special` and `size` kept for scoring)"""
    floors = []
    for f in plan["floors"]:
        floors.append(dict(name=f["name"], level=f["level"], walls=f["walls"], openings=f["openings"],
                           rooms=[dict(type=r["type"], label=r["label"], rects=r["rects"], area=r["area"], special=r.get("special"),
                                       dims=None)
                                  for r in f["rooms"]], stairs=f["stairs"]))
    return dict(version=1, units="ft", kind=plan["kind"], storeys=plan["storeys"], floors=floors)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--held-out", type=int, default=50)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.seed)
    index = []
    for k in range(a.n):
        pid = f"p{k:03d}"
        plan = make_plan(rng, pid)
        style = STYLES[k % 4]
        raster = (k // 4) % 2 == 1
        pdf = draw(plan, style, rng)
        how = ""
        if raster:
            pdf, how = rasterise(pdf, rng)
        (out / f"{pid}.pdf").write_bytes(pdf)
        (out / f"{pid}.json").write_text(json.dumps(answer(plan)))
        index.append(dict(id=pid, style=("raster_" if raster else "") + style, raster=how, kind=plan["kind"],
                          storeys=plan["storeys"], metric=plan["metric"], lang=plan["lang"], specials=plan["specials"],
                          held_out=k >= a.n - a.held_out))
    (out / "index.json").write_text(json.dumps(index, indent=1))
    print(f"{len(index)} plans in {out} ({sum(i['held_out'] for i in index)} held out)")


if __name__ == "__main__":
    main()
