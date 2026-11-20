"""Scanned or photographed plans -> PlanTo3D plan: OpenCV geometry, OCR labels, fitted scale.

    result = read_scan_pdf(pdf_bytes)      # ScanResult(plan, notes, rooms_off)

1. The page image: the embedded scan at its own resolution (or the page rendered at
   RENDER_DPI), deskewed by the dominant line angle.
2. OCR (RapidOCR: PaddleOCR's models through ONNX Runtime, Apache-2.0) finds room names,
   dimension labels and a stated scale. Their boxes are blanked before walls are traced, so
   text strokes never become walls.
3. Walls: several masks are tried, one per drawing style: dark poché (solid walls), double
   lines and hatching closed into bands, and lighter fills. raster_reader.read_mask turns
   each into walls, openings and rooms; the mask whose closed rooms hold the most OCR'd room
   names wins.
4. Scale: fitted to every dimension label inside a room at once (median of the ratios, labels
   off by more than OUTLIER from the median left out); the fitted rooms are then checked and
   any room more than 2 % from its label is listed for the review page.
The AI is not used here; the gateway's AI steps name unknown rooms and check the result.
"""

from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass, field
from functools import lru_cache

import cv2
import numpy as np

from app.modules.plan3d.raster_reader import read_mask, scale_from_text

RENDER_DPI = 220
OUTLIER = 0.08
GUESS_SCALES = (50, 100, 200)  # drawing scales tried before the size labels fix the true one
WALL_MM = 180  # a typical wall, to turn a guessed scale into a wall width in pixels
FLOOR_SHARE = 0.3  # a second drawing on the sheet is a storey when at least this big
MAX_INK_SHARE = 0.35  # walls cover well under this share of a storey's extent
MAX_WALL_RUN = 8  # plans measured: 2-4; textures read as walls: 30-130
DARK = 150  # grey level below which ink is a line or wall rather than a room fill
MIN_DPI = 200  # coarser scans are enlarged before reading (OCR and thin walls need it)
DIMS = re.compile(
    r"(\d{1,3})\s*['’]\s*-?\s*(\d{1,2})?\s*(?:\"|”|'')?\s*[xX×*]\s*"
    r"(\d{1,3})\s*['’]?\s*-?\s*(\d{1,2})?\s*(?:\"|”|'')?"
)
METRIC = re.compile(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*[xX×*]\s*(\d{1,2}(?:[.,]\d{1,2})?)")
CM = re.compile(r"\b(\d{3,4})\s*[xX×*]\s*(\d{3,4})\b")


@dataclass
class ScanResult:
    plan: dict | None
    notes: list[str] = field(default_factory=list)
    rooms_off: list[str] = field(default_factory=list)
    scale_source: str = "assumed"


@lru_cache(maxsize=1)
def _ocr():
    from rapidocr import RapidOCR

    return RapidOCR()


def label_dims_ft(text: str) -> tuple[float, float] | None:
    """(a, b) in feet from a dimension label: 15'9"x12'4", 15' X 12', 4.50 x 3.60 (m)."""
    m = DIMS.search(text or "")
    if m:
        a, ai, b, bi = m.groups()
        return float(a) + float(ai or 0) / 12, float(b) + float(bi or 0) / 12
    m = METRIC.search(text or "")
    if m:
        a, b = (float(v.replace(",", ".")) for v in m.groups())
        if 1.0 <= a <= 25 and 1.0 <= b <= 25 and ("." in m.group(0) or "," in m.group(0)):
            return a / 0.3048, b / 0.3048
    return None


def page_image(pdf: bytes) -> tuple[np.ndarray, float]:
    """The page as an 8-bit grey image and its dots per inch."""
    import pymupdf

    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        page = doc[0]
        imgs = page.get_images(full=True)
        if len(imgs) == 1:  # a scan: use it at its own resolution
            pix = pymupdf.Pixmap(doc, imgs[0][0])
            if pix.n - pix.alpha >= 3:
                pix = pymupdf.Pixmap(pymupdf.csGRAY, pix)
            rect = page.get_image_rects(imgs[0][0])
            width_in = (rect[0].width if rect else page.rect.width) / 72
            dpi = pix.width / max(width_in, 1e-6)
            gray = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            return gray[:, :, 0].copy(), dpi
        pix = page.get_pixmap(dpi=RENDER_DPI, colorspace=pymupdf.csGRAY)
        gray = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
        return gray.copy(), RENDER_DPI


def deskew(gray: np.ndarray) -> tuple[np.ndarray, float]:
    """Rotate by the dominant line angle when it is off axis by more than 0.3 degrees."""
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(
        edges, 1, math.pi / 720, 60, minLineLength=gray.shape[1] // 30, maxLineGap=6
    )
    if lines is None:
        return gray, 0.0
    angles = []
    for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
        a = math.degrees(math.atan2(y2 - y1, x2 - x1))
        a = ((a + 45) % 90) - 45  # fold onto -45..45 around the nearest axis
        angles.append(a)
    angle = statistics.median(angles)
    if abs(angle) < 0.3 or abs(angle) > 10:
        return gray, 0.0
    h, w = gray.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(gray, m, (w, h), borderValue=255), angle


def ocr_words(gray: np.ndarray) -> list[tuple[str, float, float, tuple[int, int, int, int]]]:
    """(text, centre x, centre y, box) for every line of text the OCR finds."""
    res = _ocr()(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR))
    out = []
    if res is None or res.boxes is None:
        return out
    for box, text, score in zip(res.boxes, res.txts, res.scores, strict=False):
        if score < 0.5 or not text.strip():
            continue
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        out.append(
            (
                text.strip(),
                float(sum(xs) / 4),
                float(sum(ys) / 4),
                (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))),
            )
        )
    return out


def _masks(gray: np.ndarray, px_wall: int):
    """Candidate wall masks, one per drawing style (walls white)."""
    # dark ink (walls, lines) apart from light room fills: Otsu alone puts grey fills with the ink
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    dark = cv2.bitwise_and(otsu, ((gray < DARK) * 255).astype(np.uint8))
    out = []
    k = max(2, px_wall // 2)
    square = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    out.append(("solid", cv2.morphologyEx(dark, cv2.MORPH_OPEN, square)))
    for gap in (px_wall, px_wall * 2):
        g = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, gap), max(3, gap)))
        closed = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, g)
        out.append((f"lines{gap}", cv2.morphologyEx(closed, cv2.MORPH_OPEN, square)))
    light = (gray < 215).astype(np.uint8) * 255
    out.append(("fills", cv2.morphologyEx(light, cv2.MORPH_OPEN, square)))
    return out


def _plausible(floor: dict) -> bool:
    """Walls a building could have: their total length is a few times the outline's half
    perimeter (MAX_WALL_RUN), not the hundreds that a texture or fill read as walls gives."""
    walls = floor["walls"]
    if not walls:
        return False
    total = sum(max(w[1] - w[0], w[3] - w[2]) for w in walls)
    w, h = floor["size"]
    return total <= MAX_WALL_RUN * max(1e-6, w + h)


def _floor_masks(mask: np.ndarray, reach: int, most: int = 4) -> list[np.ndarray]:
    """One mask per drawing on the sheet (ground floor, first floor ...): the biggest group of
    walls with everything within `reach`, then the next biggest of what is left, while a group's
    extent is at least FLOOR_SHARE of the first one's."""
    from app.modules.plan3d.raster_reader import _building_only

    out, rest, first = [], mask.copy(), None
    for _ in range(most):
        if cv2.countNonZero(rest) == 0:
            break
        part = _building_only(rest, reach)
        ys, xs = np.nonzero(part)
        extent = float(np.ptp(xs) + 1) * float(np.ptp(ys) + 1)
        first = first or extent
        rest = cv2.subtract(rest, part)
        if extent >= FLOOR_SHARE * first:
            out.append(part)
    return out


LEVELS = [
    ("BASEMENT", -1),
    ("GROUND", 0),
    ("FIRST", 1),
    ("SECOND", 2),
    ("THIRD", 3),
    ("ROOF", 9),
    ("TERRACE", 9),
]


def _level_of(part: np.ndarray, words) -> tuple[int | None, str | None]:
    """A drawing's storey from the nearest title under or over it ("GROUND FLOOR PLAN")."""
    ys, xs = np.nonzero(part)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    h = y1 - y0
    best = None
    for text, x, y, _ in words:
        up = text.upper()
        if "FLOOR" not in up and "PLAN" not in up and "ROOF" not in up:
            continue
        for key, level in LEVELS:
            if key in up and x0 <= x <= x1 and y0 - 0.3 * h <= y <= y1 + 0.3 * h:
                d = min(abs(y - y0), abs(y - y1))
                if best is None or d < best[0]:
                    best = (d, level, text.strip().title())
    return (best[1], best[2]) if best else (None, None)


def _dims_words(words: list[str], metric_page: bool) -> tuple[float, float] | None:
    dims = label_dims_ft(" ".join(words))
    if dims or not metric_page:
        return dims
    for w in words:  # "474X322": a metric label whose decimal point the OCR lost
        m = CM.search(w)
        if m:
            a, b = (int(v) for v in m.groups())
            if 150 <= a <= 2500 and 150 <= b <= 2500:
                return a / 100 / 0.3048, b / 100 / 0.3048
    return None


def read_scan_pdf(pdf: bytes) -> ScanResult:
    gray, dpi = page_image(pdf)
    if dpi < MIN_DPI:
        k = MIN_DPI / dpi
        gray = cv2.resize(gray, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
        dpi = MIN_DPI
    gray, angle = deskew(gray)
    notes = [f"The scan was straightened by {angle:.1f} degrees."] if angle else []
    words = ocr_words(gray)
    stated = scale_from_text(" ".join(w[0] for w in words))
    metric_page = any(METRIC.search(w[0]) for w in words)
    clean = gray.copy()
    for _, _, _, (x0, y0, x1, y1) in words:  # text is never a wall
        clean[max(0, y0 - 2) : y1 + 3, max(0, x0 - 2) : x1 + 3] = 255
    names = [(t, x, y) for t, x, y, _ in words]
    reach = int(0.04 * math.hypot(*gray.shape))
    # The drawing scale is not known yet: wall thickness and opening sizes in pixels follow
    # from it, so each likely scale is tried with each mask; the reading whose rooms hold the
    # most OCR'd names wins, and the true size is fitted to the labels afterwards.
    best = None
    for guess in GUESS_SCALES:
        guess_mm = guess * 25.4 / dpi  # real mm per pixel at 1:guess
        px_wall = max(2, round(WALL_MM / guess_mm))
        for style, mask in _masks(clean, px_wall):
            reads = []
            for part in _floor_masks(mask, reach):
                ys, xs = np.nonzero(part)
                share = len(xs) / max(1.0, float(np.ptp(xs) + 1) * float(np.ptp(ys) + 1))
                if share > MAX_INK_SHARE:  # floor fills or hatching, not walls
                    continue
                res = read_mask(gray, part, px_mm=guess_mm, words=names, t_px=max(2, px_wall // 2))
                if len(res.floor["rooms"]) >= 2 and _plausible(res.floor):
                    reads.append((part, res))
            # each OCR'd name in a room of its own counts once; rooms with no name count
            # against a reading (a mask that cuts rooms into pieces is not rewarded)
            labels = [r["label"] or "" for _, res in reads for r in res.floor["rooms"]]
            named = len({t for t in labels if re.search(r"[A-Za-z]{3}", t)})
            # the same word in two rooms (BEDROOM, BATH) is several rooms: count those too
            named += sum(1 for t in labels if re.search(r"[A-Za-z]{3}", t)) - named
            unnamed = sum(1 for t in labels if not re.search(r"[A-Za-z]{3}", t))
            score = named - 0.5 * max(0, unnamed - named // 2)
            if reads and (best is None or score > best[0]):
                best = (score, guess, style, reads)
    if best is None:
        return ScanResult(None, notes + ["No walls could be traced in the scan."])
    _, guess, style, reads = best
    # storeys: by their titles, else left to right, top to bottom
    placed = []
    for i, (part, res) in enumerate(reads):
        level, title = _level_of(part, words)
        ys, xs = np.nonzero(part)
        placed.append((level if level is not None else 100 + i, xs.min(), ys.min(), title, res))
    placed.sort(key=lambda t: (t[0], t[1] // max(1, gray.shape[1] // 8), t[2]))
    floors = [t[4].floor for t in placed]
    # 4. scale: true feet per foot read at the guess, from every room whose words carry its size
    ratios, pairs = [], []
    for floor in floors:
        for r in floor["rooms"]:
            dims = _dims_words(r.get("words") or [], metric_page)
            if not dims:
                continue
            q = max(r["rects"], key=lambda q: (q[1] - q[0]) * (q[3] - q[2]))
            w, h = q[1] - q[0], q[3] - q[2]
            if w <= 0 or h <= 0:
                continue
            a, b = dims
            straight, turned = (a / w, b / h), (b / w, a / h)
            pick = (
                straight if abs(straight[0] - straight[1]) <= abs(turned[0] - turned[1]) else turned
            )
            pairs.append((r, dims))
            ratios += list(pick)
    scale_source = "assumed"
    if ratios:
        med = statistics.median(ratios)
        good = [v for v in ratios if abs(v - med) / med <= OUTLIER]
        factor = statistics.median(good) if good else med
        scale_source = "labels"
        notes.append(f"Scale fitted to {len(good)} labelled sizes (style: {style}).")
    elif stated:
        factor = stated / guess
        scale_source = "given"
        notes.append(f"Scale from the sheet: 1:{stated}.")
    else:
        factor = 1.0
        notes.append(
            f"No sizes or scale could be read: 1:{guess} assumed. Check a known size in review."
        )
    for floor in floors:
        _rescale(floor, factor)
    off = []
    for r, dims in pairs:
        q = max(r["rects"], key=lambda q: (q[1] - q[0]) * (q[3] - q[2]))
        w, h = sorted((q[1] - q[0], q[3] - q[2]))
        a, b = sorted(dims)
        diff = max(abs(w - a) / a, abs(h - b) / b)
        r["dims"] = [round(dims[0], 2), round(dims[1], 2)]
        if diff > 0.02:
            off.append(f"{r['label'] or r['type']}: {diff:.0%} from its label")
    names_ = ["Ground Floor", "First Floor", "Second Floor", "Third Floor"]
    plan = {
        "version": 1,
        "units": "ft",
        "scale_source": scale_source,
        "floors": [
            dict(
                f,
                title=t[3],
                name=t[3] or (names_[k] if k < len(names_) else f"Floor {k}"),
                level=k,
                page=1,
            )
            for k, (f, t) in enumerate(zip(floors, placed, strict=True))
        ],
    }
    return ScanResult(plan, notes, off, scale_source)


def _rescale(floor: dict, factor: float) -> None:
    """Coordinates read at the 1:100 guess to true feet: times `factor`."""

    def sc(r):
        return [round(v * factor, 3) for v in r]

    floor["walls"] = [[*sc(w[:4]), *w[4:]] for w in floor["walls"]]
    for o in floor["openings"]:
        o["rect"] = sc(o["rect"])
    for r in floor["rooms"]:
        r["rects"] = [sc(q) for q in r["rects"]]
        r["area"] = round(sum((q[1] - q[0]) * (q[3] - q[2]) for q in r["rects"]), 1)
        r.pop("words", None)
    floor["size"] = [round(v * factor, 2) for v in floor["size"]]
