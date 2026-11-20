"""Read the drawing primitives of a CAD-exported PDF page: line segments, curves, filled shapes and words.
Coordinates are PDF points, y pointing down (page space). Needs poppler (pdftocairo, pdftotext)."""
import html, math, re, subprocess, xml.etree.ElementTree as ET

NUM = r"-?\d*\.?\d+(?:[eE][-+]?\d+)?"


NS = "{http://www.w3.org/2000/svg}"
HREF = ("{http://www.w3.org/1999/xlink}href", "href")


def _matrix(t):
    """an SVG transform attribute (a list of matrix / translate / scale / rotate / skewX / skewY) -> one matrix.
    pdftocairo writes a single matrix(); other writers and hand-made SVG use the rest."""
    m = (1, 0, 0, 1, 0, 0)
    if not t:
        return m
    for name, args in re.findall(r"([a-zA-Z]+)\s*\(([^)]*)\)", t):
        v = [float(x) for x in re.findall(NUM, args)]
        if name == "matrix":
            n = tuple(v[:6])
        elif name == "translate":
            n = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale":
            n = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate":
            a = math.radians(v[0])
            n = (math.cos(a), math.sin(a), -math.sin(a), math.cos(a), 0, 0)
            if len(v) == 3:      # rotate(a, cx, cy) = translate(cx, cy) rotate(a) translate(-cx, -cy)
                n = _mul(_mul((1, 0, 0, 1, v[1], v[2]), n), (1, 0, 0, 1, -v[1], -v[2]))
        elif name == "skewX":
            n = (1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        elif name == "skewY":
            n = (1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        else:
            raise ValueError(f"unsupported transform {t}")
        m = _mul(m, n)
    return m


def _clip_seg(x0, y0, x1, y1, box):
    """the part of a segment inside an axis-aligned box (Liang-Barsky), or None"""
    t0, t1, dx, dy = 0.0, 1.0, x1 - x0, y1 - y0
    for p, q in ((-dx, x0 - box[0]), (dx, box[1] - x0), (-dy, y0 - box[2]), (dy, box[3] - y0)):
        if abs(p) < 1e-12:
            if q < 0:
                return None
            continue
        r = q / p
        if p < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return None
    return (x0 + t0 * dx, y0 + t0 * dy, x0 + t1 * dx, y0 + t1 * dy)


def _mul(m, n):
    """m applied after n."""
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + c * B, b * A + d * B, a * C + c * D, b * C + d * D, a * E + c * F + e, b * E + d * F + f)


def _rgb(s):
    if not s or s == "none":
        return None
    m = re.findall(NUM, s)
    return tuple(round(float(v) * (2.55 if "%" in s else 1)) for v in m[:3]) if m else s


def polyline_arc(pts):
    """an open polyline of many short pieces that lies on one circle (an arc flattened by the exporter, e.g. a
    door swing) -> the equivalent cubic (p0, c1, c2, p3), else None."""
    if len(pts) < 8:
        return None
    (ax, ay), (bx, by), (cx, cy) = pts[0], pts[len(pts) // 2], pts[-1]
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-9:
        return None         # straight
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    ox = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d
    oy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d
    r = ((ax - ox) ** 2 + (ay - oy) ** 2) ** 0.5
    if r < 1 or any(abs(((x - ox) ** 2 + (y - oy) ** 2) ** 0.5 - r) > 0.02 * r for x, y in pts):
        return None
    # each piece short against the radius (a polygon with a few long sides is not an arc), sweep under 180 deg
    if any(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 > 0.4 * r for (x0, y0), (x1, y1) in zip(pts, pts[1:])):
        return None
    cross = (ax - ox) * (cy - oy) - (ay - oy) * (cx - ox)
    dot = (ax - ox) * (cx - ox) + (ay - oy) * (cy - oy)
    sweep = abs(math.atan2(cross, dot))
    mid = (bx - ox) * (ax + cx - 2 * ox) + (by - oy) * (ay + cy - 2 * oy)
    if mid < 0 or sweep < 0.3:
        return None         # the middle point lies on the far side: a sweep of 180 deg or more
    k = 4 / 3 * math.tan(sweep / 4)
    sgn = 1 if cross > 0 else -1
    # tangents at the ends (perpendicular to the radius, in the direction of travel)
    t0 = (-sgn * (ay - oy), sgn * (ax - ox))
    t1 = (-sgn * (cy - oy), sgn * (cx - ox))
    return ((ax, ay), (ax + k * t0[0], ay + k * t0[1]), (cx - k * t1[0], cy - k * t1[1]), (cx, cy))


def circle_pieces(pts, most=80.0):
    """a polyline of short pieces lying on one circle (a ring the exporter flattened, curved walls) -> the same
    points cut into runs of at most `most` degrees (each then reads as one arc), else []"""
    if len(pts) < 12:
        return []
    n = len(pts)
    a, b, c = pts[0], pts[n // 3], pts[2 * n // 3]
    d = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
    if abs(d) < 1e-9:
        return []
    a2, b2, c2 = a[0] ** 2 + a[1] ** 2, b[0] ** 2 + b[1] ** 2, c[0] ** 2 + c[1] ** 2
    ox = (a2 * (b[1] - c[1]) + b2 * (c[1] - a[1]) + c2 * (a[1] - b[1])) / d
    oy = (a2 * (c[0] - b[0]) + b2 * (a[0] - c[0]) + c2 * (b[0] - a[0])) / d
    r = math.dist(a, (ox, oy))
    if r < 1 or any(abs(math.dist(p, (ox, oy)) - r) > 0.02 * r for p in pts):
        return []
    out, run, swept = [], [pts[0]], 0.0
    for p, q in zip(pts, pts[1:]):
        step = abs(math.atan2((p[0] - ox) * (q[1] - oy) - (p[1] - oy) * (q[0] - ox),
                              (p[0] - ox) * (q[0] - ox) + (p[1] - oy) * (q[1] - oy)))
        run.append(q)
        swept += math.degrees(step)
        if swept >= most:
            out.append(run)
            run, swept = [q], 0.0
    if len(run) >= 8:
        out.append(run)
    return out


def page_count(pdf):
    out = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True, timeout=60).stdout
    return int(re.search(r"Pages:\s+(\d+)", out).group(1))


def read_page(pdf, page=1):
    """-> dict(width, height, segs, curves, fills, words). segs: (x0,y0,x1,y1,stroke,width).
    Drawings nested in groups, transforms of any SVG form, forms placed with <use> (repeated symbols) and
    rectangular clip paths are followed, so lines inside them land where the page shows them."""
    svg = subprocess.run(["pdftocairo", "-svg", "-f", str(page), "-l", str(page), pdf, "-"],
                         capture_output=True, check=True, timeout=120).stdout
    root = ET.fromstring(svg)
    vb = [float(v) for v in root.get("viewBox").split()]
    segs, curves, fills = [], [], []
    ids = {el.get("id"): el for el in root.iter() if el.get("id")}
    clips = {}

    def clip_box(ref, m):
        """an axis-aligned rectangle clip path as a page box; any other clip shape -> None (not applied)"""
        k = re.match(r"url\(#([^)]+)\)", ref or "")
        cp = ids.get(k.group(1)) if k else None
        if cp is None:
            return None
        if k.group(1) not in clips:
            pts = []
            for el in cp.iter(NS + "path"):
                pts += [tuple(float(v) for v in xy) for xy in re.findall(rf"({NUM})[ ,]+({NUM})", el.get("d", ""))]
            for el in cp.iter(NS + "rect"):
                x, y, w, h = (float(el.get(a, 0)) for a in ("x", "y", "width", "height"))
                pts += [(x, y), (x + w, y + h)]
            xs, ys = {round(q[0], 2) for q in pts}, {round(q[1], 2) for q in pts}
            clips[k.group(1)] = (min(xs), max(xs), min(ys), max(ys)) if pts and len(xs) <= 2 and len(ys) <= 2 else None
        b = clips[k.group(1)]
        if b is None or m[1] or m[2]:        # (a rotated clip rectangle is not a box any more: not applied)
            return None
        xs = sorted(m[0] * x + m[4] for x in b[:2])
        ys = sorted(m[3] * y + m[5] for y in b[2:])
        return (xs[0], xs[1], ys[0], ys[1])

    def walk(el, m, box, depth=0):
        tag = el.tag.replace(NS, "")
        if tag in ("defs", "clipPath", "mask", "symbol", "pattern", "image"):
            return
        m = _mul(m, _matrix(el.get("transform")))
        if el.get("clip-path"):
            cb = clip_box(el.get("clip-path"), m)
            if cb:
                box = cb if box is None else (max(box[0], cb[0]), min(box[1], cb[1]), max(box[2], cb[2]), min(box[3], cb[3]))
        if tag == "path":
            path(el, m, box)
        elif tag == "use":
            # poppler places glyphs (text: read by pdftotext instead) and repeated forms with <use>
            ref = next((el.get(h) for h in HREF if el.get(h)), "")[1:]
            if ref in ids and not ref.startswith("glyph") and depth < 20:
                m2 = _mul(m, (1, 0, 0, 1, float(el.get("x", 0)), float(el.get("y", 0))))
                tgt = ids[ref]
                for ch in (list(tgt) if tgt.tag.replace(NS, "") in ("symbol", "defs") else [tgt]):
                    walk(ch, m2, box, depth + 1)
            return
        for ch in el:
            walk(ch, m, box, depth)

    def add_seg(p, q, stroke, sw, box):
        g = (*p, *q) if box is None else _clip_seg(*p, *q, box)
        if g:
            segs.append((*g, stroke, sw))

    def path(el, m, box):
        stroke, fill = _rgb(el.get("stroke")), _rgb(el.get("fill", "black"))
        a, b, c, d, e, f = m
        sw = float(el.get("stroke-width", 1)) * (abs(a * d - b * c) ** 0.5)
        tf = lambda x, y: (a * x + c * y + e, b * x + d * y + f)
        toks = re.findall(rf"[MLCZHVQmlczhvq]|[SsTtAa]|{NUM}", el.get("d", ""))
        i, cmd, cur, start, poly, polys, bent = 0, None, (0, 0), (0, 0), [], [], False

        def flat_arc(poly):     # a subpath of straight pieces only: maybe an arc the exporter flattened
            if not stroke or bent:
                return
            arc = polyline_arc(poly)
            if arc:
                curves.append((*arc, stroke, sw))
                return
            for piece in circle_pieces(poly):      # a whole circle or a long arc: in pieces of 90 deg or less
                arc = polyline_arc(piece)
                if arc:
                    curves.append((*arc, stroke, sw))

        def bez(p1, p2, p3):
            if stroke:
                pts = [tf(*cur), tf(*p1), tf(*p2), tf(*p3)]
                if box is None or any(box[0] - 1 <= x <= box[1] + 1 and box[2] - 1 <= y <= box[3] + 1 for x, y in pts):
                    curves.append((*pts, stroke, sw))
            poly.append(tf(*p3))

        while i < len(toks):
            if toks[i].isalpha():
                cmd = toks[i]
                i += 1
                if cmd in "Zz":
                    if stroke and cur != start:
                        add_seg(tf(*cur), tf(*start), stroke, sw, box)
                    cur = start
                    if poly:
                        flat_arc(poly + [poly[0]] if poly[-1] != poly[0] else poly)   # a closed ring
                        polys.append(poly)
                    poly = []
                    continue
            rel = bool(cmd) and cmd.islower()
            ox, oy = cur if rel else (0, 0)
            C = cmd.upper() if cmd else None
            try:
                if C == "M":
                    cur = start = (ox + float(toks[i]), oy + float(toks[i + 1])); i += 2
                    if poly:
                        flat_arc(poly)
                        polys.append(poly)
                    poly, bent = [tf(*cur)], False
                    cmd = "l" if rel else "L"     # further pairs after a moveto are linetos
                elif C in ("L", "H", "V"):
                    if C == "L":
                        q = (ox + float(toks[i]), oy + float(toks[i + 1])); i += 2
                    elif C == "H":
                        q = (ox + float(toks[i]), cur[1]); i += 1
                    else:
                        q = (cur[0], oy + float(toks[i])); i += 1
                    if stroke:
                        add_seg(tf(*cur), tf(*q), stroke, sw, box)
                    cur = q
                    poly.append(tf(*q))
                elif C == "C":
                    p1, p2, p3 = [(ox + float(toks[i + k]), oy + float(toks[i + k + 1])) for k in (0, 2, 4)]; i += 6
                    bez(p1, p2, p3)
                    cur, bent = p3, True
                elif C == "Q":       # quadratic -> the same curve as a cubic
                    q, p3 = [(ox + float(toks[i + k]), oy + float(toks[i + k + 1])) for k in (0, 2)]; i += 4
                    p1 = (cur[0] + 2 / 3 * (q[0] - cur[0]), cur[1] + 2 / 3 * (q[1] - cur[1]))
                    p2 = (p3[0] + 2 / 3 * (q[0] - p3[0]), p3[1] + 2 / 3 * (q[1] - p3[1]))
                    bez(p1, p2, p3)
                    cur, bent = p3, True
                else:   # S / T / A (not written by pdftocairo): skip their numbers
                    i += 1
            except (IndexError, ValueError):
                break      # a truncated path: keep what was read
        if poly:
            flat_arc(poly)
            polys.append(poly)
        if fill:
            fills.extend((q, fill) for q in polys if len(q) >= 3)

    walk(root, (1, 0, 0, 1, 0, 0), None)
    return dict(width=vb[2], height=vb[3], segs=segs, curves=curves, fills=fills, words=read_words(pdf, page))


def read_words(pdf, page=1):
    out = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf, "-"],
                         capture_output=True, text=True, check=True, timeout=120).stdout
    words = []
    for m in re.finditer(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', out):
        x0, y0, x1, y1 = (float(m.group(k)) for k in range(1, 5))
        words.append((x0, y0, x1, y1, html.unescape(m.group(5))))
    return words
