"""
=============================================================================
Construtiva Bill of Materials (BOQ) Mathematical Calculator
=============================================================================
File: app/modules/sheets/calculator.py
Purpose:
  Calculates construction material quantities from architectural PlanJSON geometry:
  1. Computes room floor areas using the Shoelace formula on room polygons.
  2. Computes net vertical wall paint and plaster area minus door/window openings.
  3. Estimates structural concrete volume (foundation plinth, slab, lintels).
  4. Estimates structural TMT steel rebar requirement (Fe 550D).
  5. Applies standard industry wastage factors (3% - 5%).
  6. Multiplies quantities by material catalogue rates to generate total estimated cost.
=============================================================================
"""

import math
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger("construtiva.calculator")


def calculate_polygon_area(polygon: List[List[float]]) -> float:
    """
    Calculates the 2D surface area of a closed polygon using the Shoelace formula (Gauss's area formula).

    Args:
        polygon (List[List[float]]): List of [x, y] coordinates defining room perimeter.

    Returns:
        float: Net floor area in square meters (m²).
    """
    n = len(polygon)
    if n < 3:
        return 0.0

    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += polygon[i][0] * polygon[j][1]
        area -= polygon[j][0] * polygon[i][1]

    return round(abs(area) / 2.0, 2)


def calculate_boq_from_plan(plan_json: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    """
    Derives standard construction material quantities, waste allowances, and cost lines
    from the geometric specifications in PlanJSON.

    Args:
        plan_json (Dict[str, Any]): Active architectural plan with levels, walls, rooms, openings.

    Returns:
        Tuple[List[Dict[str, Any]], Dict[str, float]]:
            - List of individual material line items (name, area, quantity, rate, amount, surface_tag).
            - Summary dictionary with subtotal, contingency, and total_cost.
    """
    level = plan_json.get("levels", [{}])[0]
    walls = level.get("walls", [])
    openings = level.get("openings", [])
    rooms = level.get("rooms", [])
    wall_height = float(level.get("wall_height", 2.8))

    # -------------------------------------------------------------------------
    # 1. Calculate Room Areas
    # -------------------------------------------------------------------------
    living_area = 0.0
    bedroom_area = 0.0
    kitchen_area = 0.0
    bath_area = 0.0
    balcony_area = 0.0
    total_floor_area = 0.0

    for room in rooms:
        poly = room.get("polygon", [])
        area = calculate_polygon_area(poly)
        total_floor_area += area
        name = (room.get("name") or "").lower()

        if "living" in name or "drawing" in name:
            living_area += area
        elif "bed" in name:
            bedroom_area += area
        elif "kitchen" in name or "pantry" in name:
            kitchen_area += area
        elif "bath" in name or "toilet" in name:
            bath_area += area
        elif "balcony" in name or "terrace" in name:
            balcony_area += area

    if total_floor_area <= 0.0:
        total_floor_area = 89.25  # Fallback standard built-up area

    # -------------------------------------------------------------------------
    # 2. Calculate Wall Surface Area
    # -------------------------------------------------------------------------
    total_wall_length = 0.0
    for w in walls:
        start = w.get("start", [0, 0])
        end = w.get("end", [0, 0])
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.sqrt(dx * dx + dy * dy)
        total_wall_length += length

    # Gross wall surface (both internal faces: 2 x length x height)
    gross_wall_surface = 2.0 * total_wall_length * wall_height

    # Deduct door and window openings
    total_opening_area = 0.0
    for op in openings:
        w = float(op.get("width", 1.0))
        h = float(op.get("height", 2.1))
        total_opening_area += (w * h)

    net_wall_surface = max(10.0, round(gross_wall_surface - total_opening_area, 1))

    # -------------------------------------------------------------------------
    # 3. Structural Concrete & Steel Rebar Calculations
    # -------------------------------------------------------------------------
    # Standard thumb rule: 0.22 m³ concrete per m² built-up area
    concrete_volume = round(total_floor_area * 0.22, 1)

    # Rebar thumb rule: ~42 kg steel per m² built-up area (divided by 1000 for Metric Tons)
    steel_tons = round((total_floor_area * 42.0) / 1000.0, 2)

    # -------------------------------------------------------------------------
    # 4. Assemble Bill of Materials Items
    # -------------------------------------------------------------------------
    items: List[Dict[str, Any]] = [
        {
            "id": "mat_1",
            "materialName": "Marble Flooring",
            "category": "Finishes",
            "totalArea": f"{round(living_area or 30.0)} m²",
            "quantity": f"{round((living_area or 30.0) * 1.05)} m²",
            "rate": 1850,
            "unit": "m²",
            "estimatedAmount": int(round((living_area or 30.0) * 1.05 * 1850)),
            "surfaceTag": "marble",
        },
        {
            "id": "mat_2",
            "materialName": "Wall Paint (Textured)",
            "category": "Finishes",
            "totalArea": f"{round(net_wall_surface)} m²",
            "quantity": f"{max(12, int(net_wall_surface / 9.5))} L",
            "rate": 2600,
            "unit": "L",
            "estimatedAmount": int(max(12, int(net_wall_surface / 9.5)) * 2600),
            "surfaceTag": "paint",
        },
        {
            "id": "mat_3",
            "materialName": "Oak Wood Flooring",
            "category": "Woodwork",
            "totalArea": f"{round(bedroom_area or 22.5)} m²",
            "quantity": f"{round((bedroom_area or 22.5) * 1.05)} m²",
            "rate": 3400,
            "unit": "m²",
            "estimatedAmount": int(round((bedroom_area or 22.5) * 1.05 * 3400)),
            "surfaceTag": "wood",
        },
        {
            "id": "mat_4",
            "materialName": "Ceramic Bathroom Tiles",
            "category": "Finishes",
            "totalArea": f"{round((bath_area + kitchen_area) or 21.0)} m²",
            "quantity": f"{round(((bath_area + kitchen_area) or 21.0) * 1.05)} m²",
            "rate": 950,
            "unit": "m²",
            "estimatedAmount": int(round(((bath_area + kitchen_area) or 21.0) * 1.05 * 950)),
            "surfaceTag": "tiles",
        },
        {
            "id": "mat_5",
            "materialName": "Ready-Mix Concrete (Grade M25)",
            "category": "Structure",
            "totalArea": f"{round(total_floor_area)} m²",
            "quantity": f"{concrete_volume} m³",
            "rate": 6800,
            "unit": "m³",
            "estimatedAmount": int(round(concrete_volume * 6800)),
            "surfaceTag": "concrete",
        },
        {
            "id": "mat_6",
            "materialName": "TMT Steel Rebar (Fe 550D)",
            "category": "Structure",
            "totalArea": "Building Core",
            "quantity": f"{steel_tons} Tons",
            "rate": 64000,
            "unit": "Tons",
            "estimatedAmount": int(round(steel_tons * 64000)),
            "surfaceTag": "concrete",
        },
    ]

    subtotal = sum(item["estimatedAmount"] for item in items)
    contingency = int(round(subtotal * 0.05))
    total_cost = subtotal + contingency

    summary = {
        "subtotal": float(subtotal),
        "contingency_percent": 5.0,
        "contingency_amount": float(contingency),
        "total_cost": float(total_cost),
        "currency": "INR",
    }

    return items, summary
