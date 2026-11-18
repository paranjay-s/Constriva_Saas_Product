"""A bare doorway whose floor colour runs into the wall gap is not a window. Drawings that colour their floors stroke
each colour fill with its own pale pen; with a threshold line across the gap the fill's edge made two "glass" lines
and the doorway was built as a window.  python3 tests/test_doorway.py"""
import os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import detect  # noqa: E402

T, S = 5.7, 17.0                       # wall 5.7 pt thick, 17 pt per foot
FLOOR, GREY, BLACK = (217, 211, 196), (173, 173, 173), (0, 0, 0)
lo, hi, b0, b1 = 448.2, 503.5, 899.2, 910.6          # a 3.25 ft gap in a horizontal wall band
segs = [(lo, b1, hi, b1, FLOOR, 0.12), (hi, b1, hi, b0, FLOOR, 0.12), (hi, b0, lo, b0, FLOOR, 0.12),
        (lo, b0, lo, b1, FLOOR, 0.12), (lo, b0, hi, b1, FLOOR, 0.12),          # the floor fill's outline (two triangles)
        (lo, (b0 + b1) / 2, hi, (b0 + b1) / 2, GREY, 0.36),                     # threshold line
        (lo, b0, lo, b1, BLACK, 0.84), (hi, b0, hi, b1, BLACK, 0.84)]           # the jambs
fills = [([(lo, b0), (hi, b0), (hi, b1)], FLOOR), ([(lo, b0), (lo, b1), (hi, b1)], FLOOR)]


def lines(segs):
    """as detect_page builds its per-pen lines"""
    by_pen, out = defaultdict(list), {"h": [], "v": []}
    for g in segs:
        by_pen[g[4], round(g[5], 2)].append(g)
    for gs in by_pen.values():
        for o, ls in detect.join_dashes(detect.axis_lines(gs, min_len=0.5), 0.8 * T).items():
            out[o] += ls
    return out


gap = (lo, hi, b0, b1)
outline = detect.fill_outlines(fills)
kept = [g for g in segs if not detect.is_outline(g, outline)]
assert len(kept) == 3, kept
assert detect.classify(gap, "h", lines(segs), [], T, S)[0] == "window"         # what the outline used to do
kind, _ = detect.classify(gap, "h", lines(kept), [], T, S)
assert kind != "window", kind
# a real window keeps its lines: frame and glass in a dark pen are not fill outlines
win = [(lo, c, hi, c, (48, 125, 207), 0.72) for c in (b0, b0 + 4.7, b0 + 7.2, b1)]
assert not any(detect.is_outline(g, outline) for g in win)
assert detect.classify(gap, "h", lines(win), [], T, S)[0] == "window"
print("ok   a doorway with a coloured floor is not a window (%s)" % kind)
