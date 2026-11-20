"""OpenCV plan reader: a plan as pixels -> PlanTo3D floor (walls, doors, windows, rooms).

No machine learning and no vector data: it works on a rendered page or a scan.

    1. walls     dark poché bands: pixels darker than WALL_GREY, opened with a square kernel
                 the size of the thinnest wall (thin lines, text, hatches and furniture go),
                 then split into horizontal and vertical runs, each run a rectangle
    2. openings  gaps of 0.5-3.5 m between collinear wall rectangles; a window when thin
                 lines run along the whole gap (frame and glazing), a hinged door when a
                 quarter circle of ink sits beside the gap, otherwise a sliding door
    3. rooms     enclosed free space (openings closed) split into regions; each named by
                 the words inside it (`words`, from the PDF text layer or OCR) and typed
                 with PlanTo3D's room vocabulary
    4. scale     the sheet's stated scale ("SCALE 1:100") when given, else 1:100

Output units are feet, origin at the lower-left of the walls, y up (PlanTo3D's floor).
"""

import math
import re
from dataclasses import dataclass, field

import cv2
import numpy as np

MM_PER_FT = 304.8
WALL_GREY = 175  # poché and wall outlines are darker than this; site hatches are lighter
MIN_WALL_MM = 90
MIN_RUN_MM = 250
GAP_MM = (500, 3600)
ROOM_MIN_M2 = 1.2
SCALE_TEXT = re.compile(r"\b1\s*:\s*(\d{2,4})\b")


@dataclass
class RasterResult:
    floor: dict
    scale: int
    notes: list[str] = field(default_factory=list)


def scale_from_text(text: str) -> int | None:
    m = SCALE_TEXT.search(text or "")
    return int(m.group(1)) if m else None


def _runs(mask: np.ndarray, horizontal: bool, min_px: int) -> list[tuple[int, int, int, int]]:
    """Rectangles (x0, y0, x1, y1) of the wall bands running one way."""
    k = (min_px, 1) if horizontal else (1, min_px)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, k)
    band = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    n, _, stats, _ = cv2.connectedComponentsWithStats(band, connectivity=4)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < 0.6 * w * h:  # an L or T piece: split it along its main direction later
            sub = band[y : y + h, x : x + w]
            out += [(x + a, y + b, x + c, y + d) for a, b, c, d in _split(sub, horizontal)]
        else:
            out.append((x, y, x + w, y + h))
    return out


def _split(sub: np.ndarray, horizontal: bool) -> list[tuple[int, int, int, int]]:
    """Rows (or columns) of a non-rectangular band grouped into rectangles."""
    arr = sub if horizontal else sub.T
    rows = [(i, np.flatnonzero(arr[i])) for i in range(arr.shape[0])]
    rects = []
    start = None
    prev = None
    for i, cols in rows + [(arr.shape[0], np.array([]))]:
        span = (int(cols.min()), int(cols.max()) + 1) if cols.size else None
        if span != prev:
            if prev is not None and start is not None:
                rects.append((prev[0], start, prev[1], i))
            start = i if span else None
        prev = span
    if horizontal:
        return rects
    return [(b, a, d, c) for a, b, c, d in rects]


def _building_only(mask: np.ndarray, reach_px: int) -> np.ndarray:
    """The walls of the building: start from the largest connected wall group and add
    every group within `reach_px` of what is kept, until nothing changes (door gaps split
    the walls into groups; title blocks, legends and scale bars stay out of reach)."""
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n <= 2:
        return mask
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    keep = np.zeros(n, dtype=bool)
    keep[big] = True
    x0, y0 = int(stats[big, 0]), int(stats[big, 1])
    x1, y1 = x0 + int(stats[big, 2]), y0 + int(stats[big, 3])
    changed = True
    while changed:
        changed = False
        for i in range(1, n):
            if keep[i]:
                continue
            cx, cy, cw, ch, _area = (int(v) for v in stats[i])
            gap_x = max(0, x0 - (cx + cw), cx - x1)
            gap_y = max(0, y0 - (cy + ch), cy - y1)
            if max(gap_x, gap_y) <= reach_px:
                keep[i] = True
                x0, y0 = min(x0, cx), min(y0, cy)
                x1, y1 = max(x1, cx + cw), max(y1, cy + ch)
                changed = True
    return (keep[labels] * 255).astype(np.uint8)


def _gaps(walls, horizontal: bool, px_mm: float, mask: np.ndarray):
    """Openings along each wall band: breaks in the wall ink along the band's line that
    have wall on both sides (another piece of the same wall, or a crossing wall) and are
    0.5-3.5 m long. Works for a door beside a corner as well as between two pieces."""
    lo_px, hi_px = GAP_MM[0] / px_mm, GAP_MM[1] / px_mm
    out: list[tuple[int, int, int, int]] = []
    seen: set[tuple[int, int, int, int]] = set()
    for r in walls:
        x0, y0, x1, y1 = r
        if horizontal:
            band = mask[y0:y1, :]
            mid0, mid1 = y0 + (y1 - y0) // 4, y1 - (y1 - y0) // 4
            line = mask[mid0 : max(mid0 + 1, mid1), :].max(axis=0) > 0
        else:
            band = mask[:, x0:x1]
            mid0, mid1 = x0 + (x1 - x0) // 4, x1 - (x1 - x0) // 4
            line = mask[:, mid0 : max(mid0 + 1, mid1)].max(axis=1) > 0
        _ = band
        idx = np.flatnonzero(np.diff(line.astype(np.int8)))
        # runs of False between True runs
        for a, b in zip(idx[::1], idx[1::1], strict=False):
            if line[a] and not line[a + 1] and not line[b] and line[b + 1]:
                length = b - a
                if lo_px <= length <= hi_px:
                    start, stop = a + 1, b + 1
                    lo, hi = (x0, x1) if horizontal else (y0, y1)
                    # only next to this wall piece: one end of the gap touches it
                    if not (abs(start - hi) <= 2 or abs(stop - lo) <= 2):
                        continue
                    g = (start, y0, stop, y1) if horizontal else (x0, start, x1, stop)
                    key = tuple(int(v / 4) for v in g)
                    if key not in seen:
                        seen.add(key)
                        out.append(g)
    return out


def _classify(gray: np.ndarray, gap, horizontal: bool) -> str | None:
    """'window', 'door' or None (a break with nothing drawn in or beside it is open floor,
    not an opening): windows have lines along the whole gap, sliding doors have panel
    lines inside it, hinged doors a quarter circle of ink beside it."""
    x0, y0, x1, y1 = gap
    inner = gray[y0:y1, x0:x1] < WALL_GREY
    if inner.size == 0:
        return None
    lines = inner.mean(axis=1 if horizontal else 0)
    if (lines > 0.85).sum() >= 2:
        return "window"
    if (lines > 0.3).sum() >= 2:
        return "door"  # sliding panels
    length = (x1 - x0) if horizontal else (y1 - y0)
    best = 0.0
    for hx, hy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        for side in (-1, 1):
            hits = total = 0
            for k in range(2, 9):
                t = k * math.pi / 20
                total += 1
                for rad in (0.92, 1.0, 1.08, 1.16):  # the leaf can be wider than the gap
                    r = length * rad
                    if horizontal:
                        px = hx + math.cos(t) * r * (1 if hx == x0 else -1)
                        py = hy + side * math.sin(t) * r
                    else:
                        px = hx + side * math.sin(t) * r
                        py = hy + math.cos(t) * r * (1 if hy == y0 else -1)
                    px, py = int(px), int(py)
                    if 0 <= py < gray.shape[0] and 0 <= px < gray.shape[1]:
                        patch = gray[max(0, py - 2) : py + 3, max(0, px - 2) : px + 3]
                        if (patch < WALL_GREY).any():
                            hits += 1
                            break
            if total:
                best = max(best, hits / total)
    return "door" if best >= 0.6 else None


def _dedupe(gaps: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    out: list[tuple[int, int, int, int]] = []
    for g in gaps:
        area = (g[2] - g[0]) * (g[3] - g[1])
        dup = False
        for h in out:
            ix = max(0, min(g[2], h[2]) - max(g[0], h[0]))
            iy = max(0, min(g[3], h[3]) - max(g[1], h[1]))
            if ix * iy > 0.4 * min(area, (h[2] - h[0]) * (h[3] - h[1])):
                dup = True
                break
        if not dup:
            out.append(g)
    return out


def read_raster(
    gray: np.ndarray,
    *,
    dpi: float,
    scale: int | None = None,
    words: list[tuple[str, float, float]] | None = None,
) -> RasterResult:
    """`gray`: the page as an 8-bit grey image; `words`: (text, x px, y px) on it."""
    notes: list[str] = []
    scale = scale or 100
    if scale == 100 and not words:
        notes.append("No scale on the sheet: 1:100 assumed.")
    px_mm = scale * 25.4 / dpi  # real mm per pixel
    ink = (gray < WALL_GREY).astype(np.uint8) * 255
    # wider than any drawn line (0.5 mm pens: frame, plot boundary), thinner than any wall
    t_px = max(3, int(MIN_WALL_MM / px_mm * 0.75), int(0.6 * dpi / 25.4) + 1)
    walls_mask = cv2.morphologyEx(
        ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (t_px, t_px))
    )
    # groups of one building sit closer than a door gap; sheet furniture sits further away
    walls_mask = _building_only(walls_mask, int(min(1600 / px_mm, 15 * dpi / 25.4)))
    res = read_mask(gray, walls_mask, px_mm=px_mm, words=words, t_px=t_px)
    res.scale = scale
    res.notes = notes + res.notes
    return res


def read_mask(
    gray: np.ndarray,
    walls_mask: np.ndarray,
    *,
    px_mm: float,
    words: list[tuple[str, float, float]] | None = None,
    t_px: int = 3,
) -> RasterResult:
    """The reading from a wall mask already made (walls white on black), `px_mm` real mm
    per pixel (a guess is fine: the scan reader rescales afterwards)."""
    from app.modules.plan3d.convert import room_type_from_name

    notes: list[str] = []
    scale = 0
    run = max(t_px + 2, int(MIN_RUN_MM / px_mm))
    hor = _runs(walls_mask, True, run)
    ver = _runs(walls_mask, False, run)
    # a band counted both ways (a short thick piece): keep it once, by its long side
    walls = [r for r in hor if (r[2] - r[0]) >= (r[3] - r[1])] + [
        r for r in ver if (r[3] - r[1]) > (r[2] - r[0])
    ]
    if not walls:
        return RasterResult(
            {"walls": [], "openings": [], "rooms": [], "stairs": []}, scale, ["No walls found."]
        )
    gaps_h = _gaps([r for r in walls if (r[2] - r[0]) >= (r[3] - r[1])], True, px_mm, walls_mask)
    gaps_v = _gaps([r for r in walls if (r[3] - r[1]) > (r[2] - r[0])], False, px_mm, walls_mask)
    found = [(g, True, _classify(gray, g, True)) for g in _dedupe(gaps_h)] + [
        (g, False, _classify(gray, g, False)) for g in _dedupe(gaps_v)
    ]
    openings = [o for o in found if o[2] is not None]
    closed = walls_mask.copy()
    for (x0, y0, x1, y1), _, _ in openings:
        cv2.rectangle(closed, (x0, y0), (x1 - 1, y1 - 1), 255, -1)
    # rooms: free space enclosed by walls (the outside touches the image border)
    free = cv2.bitwise_not(closed)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(free, connectivity=4)
    H, W = gray.shape
    xs = [r[0] for r in walls] + [r[2] for r in walls]
    ys = [r[1] for r in walls] + [r[3] for r in walls]
    bx0, by0, bx1, by1 = min(xs), min(ys), max(xs), max(ys)
    ft = px_mm / MM_PER_FT
    min_px = ROOM_MIN_M2 * 1e6 / (px_mm * px_mm)

    def R(x0: float, y0: float, x1: float, y1: float) -> list[float]:
        return [
            round((x0 - bx0) * ft, 3),
            round((x1 - bx0) * ft, 3),
            round((by1 - y1) * ft, 3),
            round((by1 - y0) * ft, 3),
        ]

    rooms = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < min_px or x <= 0 or y <= 0 or x + w >= W or y + h >= H:
            continue
        if x < bx0 - 2 or y < by0 - 2 or x + w > bx1 + 2 or y + h > by1 + 2:
            continue
        inside = [
            t
            for t, wx, wy in (words or [])
            if labels[min(H - 1, int(wy)), min(W - 1, int(wx))] == i
        ]
        label = " ".join(inside)[:80]
        name = next((t for t in inside if re.search(r"[A-Za-z]{2}", t)), "")
        rtype = room_type_from_name(name) or room_type_from_name(label) or "room"
        rooms.append(
            {
                "words": inside,
                "type": rtype,
                "label": name or label,
                "rects": [R(x, y, x + w, y + h)],
                "area": round(area * px_mm * px_mm / MM_PER_FT**2, 1),
                "dims": None,
            }
        )
    out_openings = [
        {"type": kind, "rect": R(*g), "axis": "x" if horizontal else "y"}
        for g, horizontal, kind in openings
    ]
    floor = {
        "title": None,
        "size": [round((bx1 - bx0) * ft, 2), round((by1 - by0) * ft, 2)],
        "walls": [[*R(*r), 0] for r in walls],
        "openings": out_openings,
        "rooms": rooms,
        "stairs": [],
        "labels": [],
        "page": 1,
        "name": "Floor 1",
        "level": 0,
    }
    return RasterResult(floor, scale, notes)


def _drop_words(res: RasterResult) -> RasterResult:
    for r in res.floor.get("rooms", []):
        r.pop("words", None)
    return res


def read_pdf_page(pdf: bytes, page_no: int = 0, dpi: int | None = None) -> RasterResult:
    """A PDF page rendered to pixels and read by `read_raster`. The text layer (when the
    PDF has one) names rooms and gives the stated scale; a scan needs OCR for that."""
    import pymupdf

    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        page = doc[page_no]
        stated = scale_from_text(page.get_text())
        # enough pixels that a 100 mm partition is wider than the thickest drawn line
        dpi = dpi or int(min(600, max(300, 300 * (stated or 100) / 125)))
        pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
        gray = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
        k = dpi / 72
        words = []
        for blk in page.get_text("dict")["blocks"]:
            for line in blk.get("lines", []):
                text = " ".join(s["text"] for s in line["spans"]).strip()
                if text:
                    x0, y0, x1, y1 = line["bbox"]
                    words.append((text, (x0 + x1) / 2 * k, (y0 + y1) / 2 * k))
    return _drop_words(read_raster(gray.copy(), dpi=dpi, scale=stated, words=words))
