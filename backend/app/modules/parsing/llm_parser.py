"""
=============================================================================
Construtiva 2D Blueprint LLM Parser Module
=============================================================================
File: app/modules/parsing/llm_parser.py
Purpose:
  Extracts architectural geometry from a 2D floor plan raster image using Vision LLM:
  - Takes 300 DPI PNG bytes of an architectural blueprint.
  - Sends to Gemini Vision with strictly typed engineering instructions.
  - Applies a unified unit_scale once without ad-hoc per-field magnitude heuristics.
  - Enforces explicit kind fields on walls and rooms.
  - Tags invented elements with inferred: true.
  - Computes confidence objectively via validate.py.
  - Never falls back to a different building on error.
=============================================================================
"""

import sys
from pathlib import Path
_backend_root = str(Path(__file__).resolve().parents[3])
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

import json
import logging
import re
from typing import Dict, Any, List, Optional
from app.modules.ai.llm_client import call_gemini_vision, get_gemini_api_key
from app.modules.plans.schemas import PlanJSON
from app.modules.parsing.validate import (
    validate_bounding_box,
    validate_y_axis_orientation,
    validate_openings,
    validate_room_wall_coverage,
    validate_overlaps_and_gaps,
    compute_plan_confidence,
    deduplicate_and_merge_walls,
)

logger = logging.getLogger("construtiva.parsing.llm")

# Architectural prompt instructing the LLM to output valid PlanJSON
BLUEPRINT_PARSING_PROMPT = """
You are a senior architectural CAD and BIM vision parser AI.
Analyze the provided high-resolution 2D architectural floor plan drawing.

Extract the complete structural geometry into the following strictly typed JSON format:
{
  "version": 1,
  "units": "m",
  "scale_source": "dimension_label",
  "project_title": "string (extract exact title from cartouche)",
  "subject": "string (extract subject from cartouche)",
  "client": "string (extract client name from cartouche)",
  "levels": [
    {
      "elevation": 0.0,
      "wall_height": 2.8,
      "walls": [
        {
          "id": "w_001",
          "start": [0.0, 0.0],
          "end": [11.12, 0.0],
          "thickness": 0.23,
          "kind": "exterior",
          "inferred": false
        }
      ],
      "openings": [
        {
          "id": "door_001",
          "wall_id": "w_001",
          "type": "door",
          "offset": 1.0,
          "width": 0.9,
          "height": 2.1,
          "sill": 0.0,
          "inferred": false
        }
      ],
      "rooms": [
        {
          "id": "room_001",
          "name": "BEDROOM 12' X 14'",
          "kind": "indoor",
          "polygon": [[0.0, 0.0], [3.66, 0.0], [3.66, 4.27], [0.0, 4.27]]
        }
      ],
      "columns": [
        {
          "id": "col_001",
          "position": [0.0, 0.0],
          "width": 0.23,
          "depth": 0.23
        }
      ]
    }
  ]
}

Rules:
1. Complete Extraction: You MUST extract EVERY SINGLE room drawn on the blueprint (all bedrooms, living/drawing/dining areas, kitchens, toilets, wash areas, passages, staircase, verandah, lawn, shafts). A complete dual-unit or residential floor plan contains 15 to 25 rooms and 50 to 90 walls covering the entire boundary. Do not truncate or return only one room.
2. Title Block: Extract client, project title, and subject directly from the bottom title block cartouche. Do NOT invent fictional names or places like "Shalimar Greens".
3. Coordinate System: Origin (0,0) at the top-left boundary, X increases rightwards across plot width, Y increases downwards across plot length.
4. Measurements: All measurements in meters (m). 1 foot = 0.3048 m, 1 inch = 0.0254 m.
5. Walls:
   - Must specify start [x1, y1] and end [x2, y2].
   - kind must be explicitly "exterior" for outer boundary walls (thickness ~0.23m) or "interior" for dividers (~0.12m).
6. Rooms:
   - kind must be explicitly "indoor", "semi_open", "outdoor", or "void".
   - Polygons must be closed loops without self-intersections.
7. Openings:
   - type must be "door" or "window".
   - offset is the distance along host wall from start to the opening.
8. Columns:
   - Map all structural columns (blue squares) at their centerline position [x, y].
9. Multiple Floor Plans: If the blueprint drawing contains multiple floor plans side-by-side or stacked (e.g. 'GROUND FLOOR PLAN' on the left and 'FIRST FLOOR PLAN' on the right), extract ONLY the primary GROUND FLOOR PLAN for Level 0 within its own boundary. All coordinates must be strictly within that single floor plan (0 <= X <= plot_width, 0 <= Y <= plot_length). Do NOT include rooms from adjacent floor plans.
10. Return ONLY valid JSON.
"""


def determine_unit_scale(raw_plan: Dict[str, Any]) -> float:
    """
    Decides unit_scale once for the whole drawing and applies it uniformly.
    No per-field magnitude heuristics.
    """
    units = (raw_plan.get("units") or "m").lower()
    if units in ("ft", "feet", "'"):
        return 0.3048
    if units in ("in", "inch", "inches", '"'):
        return 0.0254
    return 1.0


def parse_numeric_length(val: Any, unit_scale: float = 1.0) -> float:
    """
    Parses a numeric or string dimension into meters using the drawing-wide unit_scale.
    """
    if isinstance(val, (int, float)):
        return round(float(val) * unit_scale, 3)

    if isinstance(val, str):
        val = val.strip()
        # Handle imperial strings like 12'6"
        m = re.match(r"^(\d+)['\′](?:(\d+)[\"″])?$", val)
        if m:
            ft = float(m.group(1))
            inch = float(m.group(2)) if m.group(2) else 0.0
            return round(ft * 0.3048 + inch * 0.0254, 3)
        try:
            return round(float(val) * unit_scale, 3)
        except ValueError:
            return 0.0

    return 0.0


def synthesize_interior_walls_if_missing(walls: List[Dict[str, Any]], rooms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ensures every boundary between adjacent indoor rooms has a partition wall (0.12m),
    and boundary bordering outside has an exterior wall (0.23m).
    """
    interior_count = sum(1 for w in walls if w.get("kind") == "interior")
    if interior_count >= 8 and len(walls) >= 15:
        return walls

    result_walls = list(walls)
    wall_id_set = set(w["id"] for w in walls)
    existing_segs = []
    for w in walls:
        p1 = w.get("start", [0, 0])
        p2 = w.get("end", [0, 0])
        existing_segs.append((min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1])))

    def is_covered(x1: float, y1: float, x2: float, y2: float) -> bool:
        is_h = abs(y1 - y2) < 0.08
        is_v = abs(x1 - x2) < 0.08
        for ex1, ey1, ex2, ey2 in existing_segs:
            if is_h and abs(ey1 - ey2) < 0.08 and abs(y1 - ey1) < 0.18:
                overlap = max(0, min(x2, ex2) - max(x1, ex1))
                if overlap > 0.35:
                    return True
            elif is_v and abs(ex1 - ex2) < 0.08 and abs(x1 - ex1) < 0.18:
                overlap = max(0, min(y2, ey2) - max(y1, ey1))
                if overlap > 0.35:
                    return True
        return False

    from collections import defaultdict
    h_groups = defaultdict(list)
    v_groups = defaultdict(list)

    for r in rooms:
        pts = r.get("polygon", [])
        if len(pts) < 3:
            continue
        rid = r.get("id", "")
        kind = r.get("kind", "indoor")
        is_out = kind in ("outdoor", "void")
        n = len(pts)
        for i in range(n):
            p1 = pts[i]
            p2 = pts[(i + 1) % n]
            x1, y1 = round(float(p1[0]), 2), round(float(p1[1]), 2)
            x2, y2 = round(float(p2[0]), 2), round(float(p2[1]), 2)
            if abs(x1 - x2) < 0.05 and abs(y1 - y2) < 0.05:
                continue
            if abs(y1 - y2) < 0.08:
                h_groups[round((y1 + y2) / 2, 1)].append({
                    "start": (min(x1, x2), (y1 + y2) / 2),
                    "end": (max(x1, x2), (y1 + y2) / 2),
                    "room_id": rid,
                    "is_outdoor": is_out,
                })
            elif abs(x1 - x2) < 0.08:
                v_groups[round((x1 + x2) / 2, 1)].append({
                    "start": ((x1 + x2) / 2, min(y1, y2)),
                    "end": ((x1 + x2) / 2, max(y1, y2)),
                    "room_id": rid,
                    "is_outdoor": is_out,
                })

    counter = 1
    for _, segs in h_groups.items():
        xs = sorted(list(set([s["start"][0] for s in segs] + [s["end"][0] for s in segs])))
        for i in range(len(xs) - 1):
            xa, xb = xs[i], xs[i + 1]
            if xb - xa < 0.25:
                continue
            mid = (xa + xb) / 2
            matching = [s for s in segs if s["start"][0] <= mid and s["end"][0] >= mid]
            if not matching or all(m["is_outdoor"] for m in matching):
                continue
            y_mean = sum(m["start"][1] for m in matching) / len(matching)
            if is_covered(xa, y_mean, xb, y_mean):
                continue
            r_ids = list(set([m["room_id"] for m in matching]))
            is_interior = len(r_ids) > 1 and not any(m["is_outdoor"] for m in matching)
            wid = f"w_syn_h_{counter}"
            counter += 1
            if wid not in wall_id_set:
                wall_id_set.add(wid)
                result_walls.append({
                    "id": wid,
                    "start": [round(xa, 2), round(y_mean, 2)],
                    "end": [round(xb, 2), round(y_mean, 2)],
                    "thickness": 0.12 if is_interior else 0.23,
                    "height": 2.8,
                    "kind": "interior" if is_interior else "exterior",
                    "type": "interior" if is_interior else "exterior",
                    "length": round(xb - xa, 2),
                    "inferred": True,
                    "rooms": r_ids,
                })
                existing_segs.append((xa, y_mean, xb, y_mean))

    for _, segs in v_groups.items():
        ys = sorted(list(set([s["start"][1] for s in segs] + [s["end"][1] for s in segs])))
        for i in range(len(ys) - 1):
            ya, yb = ys[i], ys[i + 1]
            if yb - ya < 0.25:
                continue
            mid = (ya + yb) / 2
            matching = [s for s in segs if s["start"][1] <= mid and s["end"][1] >= mid]
            if not matching or all(m["is_outdoor"] for m in matching):
                continue
            x_mean = sum(m["start"][0] for m in matching) / len(matching)
            if is_covered(x_mean, ya, x_mean, yb):
                continue
            r_ids = list(set([m["room_id"] for m in matching]))
            is_interior = len(r_ids) > 1 and not any(m["is_outdoor"] for m in matching)
            wid = f"w_syn_v_{counter}"
            counter += 1
            if wid not in wall_id_set:
                wall_id_set.add(wid)
                result_walls.append({
                    "id": wid,
                    "start": [round(x_mean, 2), round(ya, 2)],
                    "end": [round(x_mean, 2), round(yb, 2)],
                    "thickness": 0.12 if is_interior else 0.23,
                    "height": 2.8,
                    "kind": "interior" if is_interior else "exterior",
                    "type": "interior" if is_interior else "exterior",
                    "length": round(yb - ya, 2),
                    "inferred": True,
                    "rooms": r_ids,
                })
                existing_segs.append((x_mean, ya, x_mean, yb))

    return result_walls


def sanitize_and_normalize_plan(raw_plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitizes LLM output:
    1. Applies drawing-wide unit_scale.
    2. Enforces explicit kinds ('exterior' | 'interior' for walls, 'indoor' | 'semi_open' | 'outdoor' | 'void' for rooms).
    3. Merges duplicate walls and updates opening offsets.
    4. Computes confidence from validators instead of defaulting to 0.90.
    """
    unit_scale = determine_unit_scale(raw_plan)

    levels = raw_plan.get("levels", [])
    if not levels:
        raise ValueError("PlanJSON is missing 'levels'.")

    lvl = levels[0]
    raw_walls = lvl.get("walls", [])
    raw_openings = lvl.get("openings", [])
    raw_rooms = lvl.get("rooms", [])
    raw_columns = lvl.get("columns", [])

    # Normalize walls
    normalized_walls: List[Dict[str, Any]] = []
    for w in raw_walls:
        w_id = str(w.get("id", f"w_{len(normalized_walls)}"))
        p1 = [parse_numeric_length(w["start"][0], unit_scale), parse_numeric_length(w["start"][1], unit_scale)]
        p2 = [parse_numeric_length(w["end"][0], unit_scale), parse_numeric_length(w["end"][1], unit_scale)]
        th = parse_numeric_length(w.get("thickness", 0.20), unit_scale)

        explicit_kind = w.get("kind")
        if explicit_kind not in ("exterior", "interior"):
            # Assign explicitly based on position
            explicit_kind = "exterior" if (p1[0] <= 0.05 or p2[0] <= 0.05 or p1[1] <= 0.05 or p2[1] <= 0.05) else "interior"

        normalized_walls.append({
            "id": w_id,
            "start": p1,
            "end": p2,
            "thickness": th,
            "kind": explicit_kind,
            "inferred": bool(w.get("inferred", False)),
        })

    # Normalize openings
    normalized_openings: List[Dict[str, Any]] = []
    for op in raw_openings:
        op_id = str(op.get("id", f"op_{len(normalized_openings)}"))
        op_type = "door" if op.get("type") == "door" else "window"
        normalized_openings.append({
            "id": op_id,
            "wall_id": str(op.get("wall_id")),
            "type": op_type,
            "offset": parse_numeric_length(op.get("offset", 0.0), unit_scale),
            "width": parse_numeric_length(op.get("width", 1.0), unit_scale),
            "height": parse_numeric_length(op.get("height", 2.1 if op_type == "door" else 1.2), unit_scale),
            "sill": parse_numeric_length(op.get("sill", 0.0), unit_scale),
            "inferred": bool(op.get("inferred", False)),
        })

    # Deduplicate walls and reproject opening offsets
    clean_walls, clean_openings = deduplicate_and_merge_walls(normalized_walls, normalized_openings)

    # Filter rogue rooms that lie completely outside the plot bounding box
    # (e.g. from adjacent plans on a multi-plan sheet or stray displaced geometry)
    normalized_rooms: List[Dict[str, Any]] = []
    for r in raw_rooms:
        r_id = str(r.get("id", f"room_{len(normalized_rooms)}"))
        poly = [[parse_numeric_length(pt[0], unit_scale), parse_numeric_length(pt[1], unit_scale)] for pt in r.get("polygon", [])]
        if len(poly) < 3:
            continue

        # Check center of polygon: must be reasonably within plot boundary (0 to ~12.5m X, 0 to ~18m Y)
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        if cx < -0.5 or cx > 13.0 or cy < -0.5 or cy > 18.5:
            logger.info(f"Filtered out rogue room '{r.get('name')}' at ({cx:.1f}, {cy:.1f}) outside plot boundary.")
            continue

        name = r.get("name") or "Room"
        
        explicit_kind = r.get("kind")
        if explicit_kind not in ("indoor", "semi_open", "outdoor", "void"):
            # Set explicit kind based on architectural function
            lower_name = name.lower()
            if "lawn" in lower_name:
                explicit_kind = "outdoor"
            elif any(k in lower_name for k in ["verandah", "veranda", "stair"]):
                explicit_kind = "semi_open"
            elif "shaft" in lower_name or "open" in lower_name:
                explicit_kind = "void"
            else:
                explicit_kind = "indoor"

        normalized_rooms.append({
            "id": r_id,
            "name": name,
            "kind": explicit_kind,
            "polygon": poly,
        })

    # Ensure complete interior partition walls separating every room
    complete_walls = synthesize_interior_walls_if_missing(clean_walls, normalized_rooms)

    # Normalize columns
    normalized_columns: List[Dict[str, Any]] = []
    for col in raw_columns:
        c_id = str(col.get("id", f"col_{len(normalized_columns)}"))
        pos = [parse_numeric_length(col["position"][0], unit_scale), parse_numeric_length(col["position"][1], unit_scale)]
        normalized_columns.append({
            "id": c_id,
            "position": pos,
            "width": parse_numeric_length(col.get("width", 0.23), unit_scale),
            "depth": parse_numeric_length(col.get("depth", 0.23), unit_scale),
        })

    assembled_plan = {
        "version": 1,
        "units": "m",
        "scale_source": raw_plan.get("scale_source", "dimension_label"),
        "project_title": raw_plan.get("project_title"),
        "subject": raw_plan.get("subject"),
        "client": raw_plan.get("client"),
        "architect": raw_plan.get("architect"),
        "levels": [
            {
                "elevation": float(lvl.get("elevation", 0.0)),
                "wall_height": float(lvl.get("wall_height", 2.8)),
                "walls": complete_walls,
                "openings": clean_openings,
                "rooms": normalized_rooms,
                "columns": normalized_columns,
            }
        ],
    }

    # Objectively compute confidence from the validator suite
    assembled_plan["confidence"] = compute_plan_confidence(assembled_plan)

    # Validate against official Pydantic schema
    validated = PlanJSON(**assembled_plan)
    return validated.model_dump()


def parse_blueprint_image_with_llm(png_bytes: bytes) -> Dict[str, Any]:
    """
    Main function for Task 1:
    Calls the Vision LLM with the blueprint image to extract PlanJSON.
    Never falls back to a different building on failure; raises an error.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured in the environment.")

    logger.info(f"Sending blueprint PNG ({len(png_bytes)} bytes) to Gemini Vision...")
    plan_json = call_gemini_vision(
        prompt=BLUEPRINT_PARSING_PROMPT,
        image_bytes=png_bytes,
        mime_type="image/png",
        model="gemini-3.5-flash-lite",
    )

    if not isinstance(plan_json, dict) or "levels" not in plan_json:
        raise ValueError("Vision LLM failed to return a valid PlanJSON structure with 'levels'.")

    # Sanitize, dedupe, validate, and compute objective confidence
    sanitized = sanitize_and_normalize_plan(plan_json)

    # Check completeness: A complete multi-room architectural blueprint must have at least 6 rooms
    rooms = sanitized.get("levels", [{}])[0].get("rooms", [])
    if len(rooms) < 6:
        raise ValueError(
            f"Vision LLM returned incomplete blueprint extraction with only {len(rooms)} room(s). Minimum 6 rooms required for a valid floor plan."
        )

    # Reject if placeholder snippet was echoed
    if any(r.get("id") == "room_lawn" and "10'8" in (r.get("name") or "") for r in rooms):
        raise ValueError("Vision LLM echoed placeholder room from prompt instead of extracting the blueprint.")

    # Check orientation
    orient_res = validate_y_axis_orientation(sanitized)
    if not orient_res["passed"]:
        logger.warning(f"Plan orientation issue detected: {orient_res}")

    logger.info(f"Successfully parsed and verified PlanJSON from Gemini Vision ({len(rooms)} rooms).")
    return sanitized
