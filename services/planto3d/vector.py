"""Read the drawing primitives of a CAD-exported PDF page: line segments, curves, filled shapes and words.
Coordinates are PDF points, y pointing down (page space). Needs poppler (pdftocairo, pdftotext)."""
import html, re, subprocess, xml.etree.ElementTree as ET

NUM = r"-?\d*\.?\d+(?:[eE][-+]?\d+)?"


def _matrix(t):
    if not t:
        return (1, 0, 0, 1, 0, 0)
    m = re.match(r"matrix\(([^)]*)\)", t)
    if m:
        return tuple(float(v) for v in re.split(r"[ ,]+", m.group(1).strip()))
    m = re.match(r"translate\(([^)]*)\)", t)
    if m:
        v = [float(v) for v in re.split(r"[ ,]+", m.group(1).strip())] + [0]
        return (1, 0, 0, 1, v[0], v[1])
    raise ValueError(f"unsupported transform {t}")


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


def page_count(pdf):
    out = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True, timeout=60).stdout
    return int(re.search(r"Pages:\s+(\d+)", out).group(1))


def read_page(pdf, page=1):
    """-> dict(width, height, segs, curves, fills, words). segs: (x0,y0,x1,y1,stroke,width)."""
    svg = subprocess.run(["pdftocairo", "-svg", "-f", str(page), "-l", str(page), pdf, "-"],
                         capture_output=True, check=True, timeout=120).stdout
    root = ET.fromstring(svg)
    ns = "{http://www.w3.org/2000/svg}"
    vb = [float(v) for v in root.get("viewBox").split()]
    segs, curves, fills = [], [], []

    def walk(el, m):
        tag = el.tag.replace(ns, "")
        if tag in ("defs", "clipPath", "mask", "symbol", "pattern"):
            return
        m = _mul(m, _matrix(el.get("transform")))
        if tag == "path":
            path(el, m)
        for ch in el:
            walk(ch, m)

    def path(el, m):
        stroke, fill = _rgb(el.get("stroke")), _rgb(el.get("fill", "black"))
        a, b, c, d, e, f = m
        sw = float(el.get("stroke-width", 1)) * (abs(a * d - b * c) ** 0.5)
        tf = lambda x, y: (a * x + c * y + e, b * x + d * y + f)
        toks = re.findall(rf"[MLCZHVmlczhv]|{NUM}", el.get("d", ""))
        i, cmd, cur, start, poly, polys = 0, None, (0, 0), (0, 0), [], []
        while i < len(toks):
            if toks[i].isalpha():
                cmd = toks[i]
                i += 1
                if cmd in "Zz":
                    if stroke and cur != start:
                        segs.append((*tf(*cur), *tf(*start), stroke, sw))
                    cur = start
                    if poly:
                        polys.append(poly)
                    poly = []
                    continue
            if cmd == "M":
                cur = start = (float(toks[i]), float(toks[i + 1])); i += 2
                if poly:
                    polys.append(poly)
                poly = [tf(*cur)]
                cmd = "L"
            elif cmd == "L":
                p = (float(toks[i]), float(toks[i + 1])); i += 2
                if stroke:
                    segs.append((*tf(*cur), *tf(*p), stroke, sw))
                cur = p
                poly.append(tf(*p))
            elif cmd == "C":
                pts = [(float(toks[i + k]), float(toks[i + k + 1])) for k in (0, 2, 4)]; i += 6
                if stroke:
                    curves.append((tf(*cur), *(tf(*q) for q in pts), stroke, sw))
                cur = pts[2]
                poly.append(tf(*cur))
            else:   # relative / H / V commands are not emitted by pdftocairo; skip their numbers
                i += 1
        if poly:
            polys.append(poly)
        if fill:
            fills.extend((p, fill) for p in polys if len(p) >= 3)

    walk(root, (1, 0, 0, 1, 0, 0))
    return dict(width=vb[2], height=vb[3], segs=segs, curves=curves, fills=fills, words=read_words(pdf, page))


def read_words(pdf, page=1):
    out = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf, "-"],
                         capture_output=True, text=True, check=True, timeout=120).stdout
    words = []
    for m in re.finditer(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', out):
        x0, y0, x1, y1 = (float(m.group(k)) for k in range(1, 5))
        words.append((x0, y0, x1, y1, html.unescape(m.group(5))))
    return words
