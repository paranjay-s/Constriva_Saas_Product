"""Scans: walls from the scan reader, room names and types from the AI reader (C2.2).

Measured on the held-out raster plans (PART B): the scan reader traces walls better than the AI
reader, the AI reader names and types rooms far better (room types 68-81 % against 11-52 %). So a
scan that the scan reader reads is also read by the AI (one cached call per PDF), and each scan room
takes the type, and the name when OCR found none, of the AI room that matches it:
  1. the same label (letters and digits, ignoring case and spacing), the nearest such room;
  2. else the AI room whose centre is nearest, in coordinates relative to each reading's own
     extent (the two readings differ in scale and origin), within NEAR_SHARE of the extent.
An AI room is used once. Geometry is never taken from the AI.
"""

from __future__ import annotations

import math
import re
from typing import Any

NEAR_SHARE = 0.18
UNKNOWN = {"", "multipurpose", "room", "custom", "other"}


def _key(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _word_key(text: str | None) -> str:
    """the label's name part only ("BED 12'-0\" x10'-0\"" -> "bed")"""
    words = re.findall(r"[A-Za-z]{2,}", text or "")
    return "".join(words).lower()


def _centres(floor: dict[str, Any]) -> tuple[list[tuple[float, float] | None], tuple[float, ...]]:
    pts = []
    xs, ys = [], []
    for r in floor.get("rooms", []):
        rects = r.get("rects") or []
        if not rects:
            pts.append(None)
            continue
        q = max(rects, key=lambda t: (t[1] - t[0]) * (t[3] - t[2]))
        pts.append(((q[0] + q[1]) / 2, (q[2] + q[3]) / 2))
        xs += [q[0], q[1]]
        ys += [q[2], q[3]]
    box = (min(xs), max(xs), min(ys), max(ys)) if xs else (0.0, 1.0, 0.0, 1.0)
    return pts, box


def _norm(p, box):
    x0, x1, y0, y1 = box
    return ((p[0] - x0) / max(1e-6, x1 - x0), (p[1] - y0) / max(1e-6, y1 - y0))


def name_scan_rooms(scan: dict[str, Any], ai: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """The scan plan with room types (and missing names) from the AI plan; -> (plan, rooms named).
    Floors are paired in order."""
    named = 0
    for sf, af in zip(scan.get("floors", []), ai.get("floors", []), strict=False):
        s_pts, s_box = _centres(sf)
        a_pts, a_box = _centres(af)
        used: set[int] = set()
        a_rooms = af.get("rooms", [])
        for i, r in enumerate(sf.get("rooms", [])):
            if s_pts[i] is None:
                continue
            here = _norm(s_pts[i], s_box)

            def dist(j, here=here, a_pts=a_pts, a_box=a_box):
                return math.dist(here, _norm(a_pts[j], a_box))

            cands = [j for j in range(len(a_rooms)) if j not in used and a_pts[j] is not None]
            same = [j for j in cands if _word_key(a_rooms[j].get("label"))
                    and _word_key(a_rooms[j].get("label")) == _word_key(r.get("label"))]
            pick = min(same, key=dist) if same else None
            if pick is None:
                near = [j for j in cands if dist(j) <= NEAR_SHARE]
                pick = min(near, key=dist) if near else None
            if pick is None:
                continue
            used.add(pick)
            a = a_rooms[pick]
            if a.get("type") and a["type"] not in UNKNOWN:
                r["type"] = a["type"]
                named += 1
            if not (r.get("label") or "").strip() and a.get("label"):
                r["label"] = a["label"]
    return scan, named
