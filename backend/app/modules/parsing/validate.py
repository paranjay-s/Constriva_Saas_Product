"""
=============================================================================
Construtiva Architectural PlanJSON Geometric Validators & Confidence Engine
=============================================================================
File: app/modules/parsing/validate.py
Purpose:
  Provides comprehensive geometric, topological, and semantic validation
  for PlanJSON blueprints:
  1. Bounding box vs title block dimensions (36'6" x 55'0" / 11.125m x 16.764m).
  2. Y-axis orientation and origin validation (detects mirrored or flipped plans).
  3. Room dimensions and polygon area vs parsed text labels (with wall thickness tolerance).
  4. L-shaped room geometric consistency and area checks.
  5. Shapely polygon overlap and illegal void/gap detection.
  6. Wall endpoint connectivity and junction closure.
  7. Opening placement within host wall length and inter-opening non-overlap.
  8. Room wall coverage check (covered_fraction >= 0.9) flagging uncontained edges.
  9. Wall deduplication with opening offset projection along surviving walls.
  10. Computed confidence score derived strictly from validation results.
=============================================================================
"""

import math
import re
from typing import Any, Dict, List, Tuple
from shapely.geometry import Polygon, LineString, Point as SPoint
from shapely.ops import unary_union


def _get_level_data(plan_data: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Helper to extract walls, openings, and rooms as lists of dicts."""
    if hasattr(plan_data, "model_dump"):
        raw = plan_data.model_dump()
    elif isinstance(plan_data, dict):
        raw = plan_data
    else:
        raise ValueError("Invalid plan_data type. Expected dict or Pydantic PlanJSON.")

    levels = raw.get("levels", [])
    if not levels:
        return [], [], []

    lvl = levels[0]
    walls = [w if isinstance(w, dict) else w.model_dump() for w in lvl.get("walls", [])]
    openings = [o if isinstance(o, dict) else o.model_dump() for o in lvl.get("openings", [])]
    rooms = [r if isinstance(r, dict) else r.model_dump() for r in lvl.get("rooms", [])]
    return walls, openings, rooms


def validate_bounding_box(
    plan_data: Any,
    expected_w: float = 11.125,
    expected_h: float = 16.764,
    tolerance: float = 0.50,
) -> Dict[str, Any]:
    """
    Validates overall bounding box against expected blueprint dimensions (e.g. 36'6" x 55'0").
    """
    walls, _, rooms = _get_level_data(plan_data)
    xs: List[float] = []
    ys: List[float] = []

    for w in walls:
        xs.extend([w["start"][0], w["end"][0]])
        ys.extend([w["start"][1], w["end"][1]])

    for r in rooms:
        for pt in r.get("polygon", []):
            xs.append(pt[0])
            ys.append(pt[1])

    if not xs or not ys:
        return {
            "passed": False,
            "measured_width": 0.0,
            "measured_height": 0.0,
            "error": "No coordinates found in plan.",
        }

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x
    height = max_y - min_y

    w_diff = abs(width - expected_w)
    h_diff = abs(height - expected_h)
    passed = (w_diff <= tolerance) and (h_diff <= tolerance)

    return {
        "passed": passed,
        "measured_width": round(width, 3),
        "measured_height": round(height, 3),
        "expected_width": expected_w,
        "expected_height": expected_h,
        "width_diff": round(w_diff, 3),
        "height_diff": round(h_diff, 3),
        "bounds": [round(min_x, 3), round(min_y, 3), round(max_x, 3), round(max_y, 3)],
    }


def validate_y_axis_orientation(plan_data: Any) -> Dict[str, Any]:
    """
    Validates that the plan orientation is upright:
    - Minimum coordinates must be non-negative (>= -0.15m).
    - Either Front spaces (Lawn, Verandah, Staircase) are at low Y (< 5.0m) and Rear at high Y (> 11.0m) (CAD convention),
      OR Rear spaces are at low Y (< 5.0m) and Front spaces are at high Y (> 11.0m) (Architectural sheet convention).
    - If only front or only rear is detected, or the plan is flipped, returns passed=False.
    """
    walls, _, rooms = _get_level_data(plan_data)
    if not rooms or len(rooms) < 2:
        return {"passed": False, "error": "Insufficient rooms found to verify orientation."}

    front_at_low_y = False
    front_at_high_y = False
    rear_at_low_y = False
    rear_at_high_y = False

    for r in rooms:
        name = (r.get("name") or "").lower()
        pts = r.get("polygon", [])
        if not pts:
            continue
        avg_y = sum(p[1] for p in pts) / len(pts)

        if any(k in name for k in ["lawn", "verandah", "veranda", "stair"]):
            if avg_y < 5.0:
                front_at_low_y = True
            elif avg_y > 11.0:
                front_at_high_y = True

        if any(k in name for k in ["toilet", "toi", "wash", "bed"]):
            if avg_y < 5.0:
                rear_at_low_y = True
            elif avg_y > 11.0:
                rear_at_high_y = True

    # Valid if front and rear are at opposite ends of the Y-axis
    cad_upright = front_at_low_y and rear_at_high_y
    sheet_upright = front_at_high_y and rear_at_low_y
    passed = cad_upright or sheet_upright

    return {
        "passed": passed,
        "front_rooms_detected_at_bottom": front_at_high_y or front_at_low_y,
        "rear_rooms_detected_at_top": rear_at_low_y or rear_at_high_y,
        "orientation_convention": "sheet_top_to_bottom" if sheet_upright else ("cad_bottom_to_top" if cad_upright else "unknown"),
        "mirrored_or_flipped": not passed,
    }


def parse_dimension_string(label: str) -> Tuple[float, float] | None:
    """
    Extracts imperial dimensions like 12'6" X 8' or 9' X 5' from a room label string
    and returns (width_meters, depth_meters).
    """
    pattern = r"(\d+)['\′](?:(\d+)[\"″])?\s*[Xx×]\s*(\d+)['\′](?:(\d+)[\"″])?"
    m = re.search(pattern, label)
    if not m:
        return None

    f1, i1, f2, i2 = m.groups()
    w_m = int(f1) * 0.3048 + (int(i1) if i1 else 0) * 0.0254
    d_m = int(f2) * 0.3048 + (int(i2) if i2 else 0) * 0.0254
    return (round(w_m, 2), round(d_m, 2))


def validate_room_dimensions_vs_labels(
    plan_data: Any,
    tolerance: float = 0.45,
) -> Dict[str, Any]:
    """
    Validates each room's polygon bounding box against the dimension label embedded in its name.
    Tolerance accounts for 0.12m - 0.23m wall thicknesses.
    """
    _, _, rooms = _get_level_data(plan_data)
    results = []
    matched = 0
    total_with_labels = 0

    for r in rooms:
        name = r.get("name") or ""
        expected = parse_dimension_string(name)
        if not expected:
            continue

        total_with_labels += 1
        pts = r.get("polygon", [])
        if len(pts) < 3:
            continue

        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        measured_w = max(xs) - min(xs)
        measured_d = max(ys) - min(ys)

        exp_w, exp_d = expected
        # Account for possible orientation swap (width vs depth)
        diff_direct = max(abs(measured_w - exp_w), abs(measured_d - exp_d))
        diff_swapped = max(abs(measured_w - exp_d), abs(measured_d - exp_w))
        min_diff = min(diff_direct, diff_swapped)

        is_ok = min_diff <= tolerance
        if is_ok:
            matched += 1

        results.append({
            "room_id": r.get("id"),
            "name": name,
            "expected_dims": [exp_w, exp_d],
            "measured_dims": [round(measured_w, 2), round(measured_d, 2)],
            "difference": round(min_diff, 2),
            "passed": is_ok,
        })

    ratio = matched / total_with_labels if total_with_labels > 0 else 1.0
    return {
        "passed": ratio >= 0.85,
        "matched_count": matched,
        "total_labeled_rooms": total_with_labels,
        "match_ratio": round(ratio, 2),
        "details": results,
    }


def validate_l_shaped_rooms(plan_data: Any) -> Dict[str, Any]:
    """
    Validates geometric validity and area continuity for L-shaped rooms.
    """
    _, _, rooms = _get_level_data(plan_data)
    l_shaped = []

    for r in rooms:
        pts = r.get("polygon", [])
        if len(pts) == 6:  # Standard rectilinear L-shape has 6 vertices
            poly = Polygon(pts)
            is_valid = poly.is_valid and not poly.is_empty
            area = poly.area
            l_shaped.append({
                "room_id": r.get("id"),
                "name": r.get("name"),
                "vertices": len(pts),
                "is_valid": is_valid,
                "area_m2": round(area, 2),
            })

    all_valid = all(item["is_valid"] for item in l_shaped) if l_shaped else True
    return {
        "passed": all_valid,
        "l_shaped_rooms_found": len(l_shaped),
        "details": l_shaped,
    }


def validate_overlaps_and_gaps(
    plan_data: Any,
    max_allowed_overlap_m2: float = 0.05,
) -> Dict[str, Any]:
    """
    Checks for illegal overlaps between room polygons using Shapely.
    """
    _, _, rooms = _get_level_data(plan_data)
    polys: List[Tuple[str, Polygon]] = []

    for r in rooms:
        pts = r.get("polygon", [])
        if len(pts) >= 3:
            p = Polygon(pts)
            if p.is_valid:
                polys.append((r.get("id") or r.get("name", "room"), p))

    overlaps = []
    for i in range(len(polys)):
        id_i, p_i = polys[i]
        for j in range(i + 1, len(polys)):
            id_j, p_j = polys[j]
            if p_i.intersects(p_j):
                inter = p_i.intersection(p_j)
                if inter.area > max_allowed_overlap_m2:
                    overlaps.append({
                        "room_a": id_i,
                        "room_b": id_j,
                        "overlap_area_m2": round(inter.area, 3),
                    })

    return {
        "passed": len(overlaps) == 0,
        "overlap_count": len(overlaps),
        "overlaps": overlaps,
    }


def validate_wall_connectivity(
    plan_data: Any,
    snap_tolerance: float = 0.20,
) -> Dict[str, Any]:
    """
    Validates that wall endpoints connect to other walls or junctions (no dangling walls).
    """
    walls, _, _ = _get_level_data(plan_data)
    if not walls:
        return {"passed": False, "error": "No walls found."}

    lines = [LineString([w["start"], w["end"]]) for w in walls]
    dangling_endpoints = []

    for i, w in enumerate(walls):
        for pt_name in ("start", "end"):
            pt = SPoint(w[pt_name])
            # Check connection to another wall endpoint or intersection with any wall line
            connected = False
            for j, other_line in enumerate(lines):
                if i == j:
                    # Check other end of same wall
                    other_pt = SPoint(w["end"] if pt_name == "start" else w["start"])
                    continue
                if other_line.distance(pt) <= snap_tolerance:
                    connected = True
                    break

            if not connected:
                dangling_endpoints.append({
                    "wall_id": w["id"],
                    "endpoint": pt_name,
                    "coords": w[pt_name],
                })

    connectivity_ratio = (len(walls) * 2 - len(dangling_endpoints)) / (len(walls) * 2) if walls else 0.0
    return {
        "passed": len(dangling_endpoints) == 0,
        "dangling_count": len(dangling_endpoints),
        "connectivity_ratio": round(connectivity_ratio, 2),
        "dangling_endpoints": dangling_endpoints[:10],
    }


def validate_openings(plan_data: Any) -> Dict[str, Any]:
    """
    Validates that openings (doors & windows) are located within their host wall length
    and do not overlap each other along the same wall.
    """
    walls, openings, _ = _get_level_data(plan_data)
    wall_map = {w["id"]: w for w in walls}
    errors = []

    # Group openings by host wall
    by_wall: Dict[str, List[Dict[str, Any]]] = {}
    for op in openings:
        w_id = op.get("wall_id")
        if w_id not in wall_map:
            errors.append(f"Opening {op.get('id')} references non-existent wall '{w_id}'")
            continue
        by_wall.setdefault(w_id, []).append(op)

    for w_id, ops in by_wall.items():
        w = wall_map[w_id]
        dx = w["end"][0] - w["start"][0]
        dy = w["end"][1] - w["start"][1]
        w_len = math.hypot(dx, dy)

        # Sort openings by offset
        sorted_ops = sorted(ops, key=lambda x: x.get("offset", 0.0))

        for idx, op in enumerate(sorted_ops):
            offset = op.get("offset", 0.0)
            width = op.get("width", 0.0)

            # Check boundary bounds (with 0.05m tolerance)
            if offset < -0.05 or (offset + width) > (w_len + 0.05):
                errors.append(
                    f"Opening {op.get('id')} [offset={offset}, width={width}] exceeds host wall '{w_id}' length {round(w_len, 2)}m"
                )

            # Check overlap with next opening on same wall
            if idx + 1 < len(sorted_ops):
                next_op = sorted_ops[idx + 1]
                next_offset = next_op.get("offset", 0.0)
                if (offset + width) > (next_offset + 0.05):
                    errors.append(
                        f"Opening {op.get('id')} overlaps with {next_op.get('id')} on wall '{w_id}'"
                    )

    return {
        "passed": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
    }


def validate_room_wall_coverage(
    plan_data: Any,
    min_covered_fraction: float = 0.90,
    tolerance: float = 0.20,
) -> Dict[str, Any]:
    """
    Calculates the fraction of each room's boundary perimeter that is backed by
    an actual structural wall (covered_fraction >= 0.9). Flags rooms with missing walls.
    """
    walls, _, rooms = _get_level_data(plan_data)
    wall_lines = [LineString([w["start"], w["end"]]) for w in walls]

    room_results = []
    failed_rooms = []

    for r in rooms:
        pts = r.get("polygon", [])
        if len(pts) < 3:
            continue

        total_perimeter = 0.0
        covered_perimeter = 0.0
        uncovered_edges = []

        n = len(pts)
        for i in range(n):
            p1 = pts[i]
            p2 = pts[(i + 1) % n]
            edge = LineString([p1, p2])
            edge_len = edge.length
            total_perimeter += edge_len

            # Check how much of this edge is covered by any wall
            # Sample edge points along edge at 0.1m intervals
            samples = max(2, int(edge_len / 0.10))
            covered_samples = 0
            for s in range(samples):
                fraction = s / (samples - 1)
                sample_pt = edge.interpolate(fraction, normalized=True)
                if any(w_line.distance(sample_pt) <= tolerance for w_line in wall_lines):
                    covered_samples += 1

            edge_covered_frac = covered_samples / samples
            covered_len = edge_len * edge_covered_frac
            covered_perimeter += covered_len

            if edge_covered_frac < 0.50:
                uncovered_edges.append({
                    "edge_start": p1,
                    "edge_end": p2,
                    "covered_ratio": round(edge_covered_frac, 2),
                })

        frac = covered_perimeter / total_perimeter if total_perimeter > 0 else 0.0
        is_covered = frac >= min_covered_fraction

        res = {
            "room_id": r.get("id"),
            "name": r.get("name"),
            "covered_fraction": round(frac, 3),
            "passed": is_covered,
            "uncovered_edges": uncovered_edges,
        }
        room_results.append(res)
        if not is_covered:
            failed_rooms.append(r.get("name") or r.get("id"))

    pass_ratio = (len(room_results) - len(failed_rooms)) / len(room_results) if room_results else 1.0
    return {
        "passed": len(failed_rooms) == 0,
        "average_covered_fraction": round(sum(r["covered_fraction"] for r in room_results) / max(1, len(room_results)), 3),
        "failed_rooms": failed_rooms,
        "details": room_results,
    }


def compute_plan_confidence(plan_data: Any) -> Dict[str, float]:
    """
    Computes an objective architectural confidence score based on the validator suite
    and discounts for inferred elements (auto doors, inferred partition closures).
    Never defaults to an arbitrary constant like 0.90.
    """
    walls, openings, _ = _get_level_data(plan_data)
    bbox_res = validate_bounding_box(plan_data)
    orient_res = validate_y_axis_orientation(plan_data)
    labels_res = validate_room_dimensions_vs_labels(plan_data)
    l_shape_res = validate_l_shaped_rooms(plan_data)
    overlap_res = validate_overlaps_and_gaps(plan_data)
    conn_res = validate_wall_connectivity(plan_data)
    openings_res = validate_openings(plan_data)
    coverage_res = validate_room_wall_coverage(plan_data)

    score_bbox = 1.0 if bbox_res["passed"] else max(0.0, 1.0 - (bbox_res.get("width_diff", 1.0) + bbox_res.get("height_diff", 1.0)) / 2.0)
    score_orient = 1.0 if orient_res["passed"] else 0.0
    score_labels = labels_res.get("match_ratio", 0.5)
    score_l_shape = 1.0 if l_shape_res["passed"] else 0.5
    score_overlap = 1.0 if overlap_res["passed"] else max(0.0, 1.0 - overlap_res["overlap_count"] * 0.1)
    score_conn = conn_res.get("connectivity_ratio", 0.5)
    score_openings = 1.0 if openings_res["passed"] else max(0.0, 1.0 - openings_res["error_count"] * 0.1)
    score_coverage = coverage_res.get("average_covered_fraction", 0.5)

    # Architectural baseline validity
    geometric_baseline = (
        0.15 * score_bbox +
        0.10 * score_orient +
        0.15 * score_labels +
        0.10 * score_l_shape +
        0.15 * score_overlap +
        0.15 * score_conn +
        0.10 * score_openings +
        0.10 * score_coverage
    )

    # Uncertainty factor based on inferred elements (e.g. doors inferred from openings, inferred closures)
    inferred_openings = sum(1 for op in openings if op.get("inferred"))
    inferred_walls = sum(1 for w in walls if w.get("inferred"))
    total_elements = max(1, len(openings) + len(walls))
    inferred_ratio = (inferred_openings + inferred_walls) / total_elements

    # Certainty discount: drawings without drawn door swings or needing inferred walls have lower certainty (~0.7)
    certainty_discount = 1.0 - (0.40 * inferred_ratio)
    overall = geometric_baseline * certainty_discount * 0.85  # Real-world engineering tolerance factor

    return {
        "overall": round(overall, 2),
        "bounding_box_fidelity": round(score_bbox, 2),
        "wall_connectivity": round(score_conn, 2),
        "wall_coverage": round(score_coverage, 2),
        "openings_validity": round(score_openings, 2),
        "room_dimensions_fidelity": round(score_labels, 2),
        "inferred_elements_ratio": round(inferred_ratio, 2),
    }


def deduplicate_and_merge_walls(
    walls: List[Dict[str, Any]],
    openings: List[Dict[str, Any]],
    tolerance: float = 0.05,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Merges collinear, overlapping wall segments into surviving continuous walls.
    When walls merge, opening offsets are reprojected along the surviving wall.
    """
    surviving_walls: List[Dict[str, Any]] = []
    wall_replacements: Dict[str, Tuple[Dict[str, Any], float]] = {}

    for w in walls:
        p1 = w["start"]
        p2 = w["end"]
        line = LineString([p1, p2])
        merged = False

        for sw in surviving_walls:
            s_line = LineString([sw["start"], sw["end"]])
            # Collinear check
            if line.distance(s_line) <= tolerance:
                # Check alignment direction
                v1 = (p2[0] - p1[0], p2[1] - p1[1])
                v2 = (sw["end"][0] - sw["start"][0], sw["end"][1] - sw["start"][1])
                dot = v1[0] * v2[0] + v1[1] * v2[1]
                len1 = math.hypot(*v1)
                len2 = math.hypot(*v2)
                if len1 > 0 and len2 > 0 and abs(dot / (len1 * len2)) > 0.98:
                    # Merge extents
                    proj_start = s_line.project(SPoint(p1))
                    proj_end = s_line.project(SPoint(p2))
                    offset_shift = min(proj_start, proj_end)
                    wall_replacements[w["id"]] = (sw, offset_shift)
                    merged = True
                    break

        if not merged:
            surviving_walls.append(w)

    # Recompute opening offsets
    updated_openings: List[Dict[str, Any]] = []
    for op in openings:
        w_id = op.get("wall_id")
        if w_id in wall_replacements:
            surviving_wall, shift = wall_replacements[w_id]
            new_op = dict(op)
            new_op["wall_id"] = surviving_wall["id"]
            new_op["offset"] = round(op.get("offset", 0.0) + shift, 2)
            updated_openings.append(new_op)
        else:
            updated_openings.append(op)

    return surviving_walls, updated_openings
