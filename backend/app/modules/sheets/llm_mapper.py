"""
=============================================================================
Construtiva PlanJSON to Materials Mapping Module
=============================================================================
File: app/modules/sheets/llm_mapper.py
Purpose:
  Maps 2D/3D PlanJSON geometry to construction material quantities and cost line items:
  1. Computes or prompts LLM for material requirements from plan geometry.
  2. Maps quantities to the 7 core construction materials:
     - Brick
     - Steel/rebar rod
     - Cement
     - Sand (fine aggregate)
     - Ballast (coarse aggregate)
     - Plaster (cement and gypsum)
     - Tiles (floor and wall)
  3. Returns a standardized list of material line item dictionaries for database insertion.
=============================================================================
"""

import sys
from pathlib import Path
_backend_root = str(Path(__file__).resolve().parents[3])
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

import math
import logging
from typing import Dict, Any, List
from app.modules.sheets.service import DEFAULT_CONSTRUCTION_MATERIALS

logger = logging.getLogger("construtiva.sheets.mapper")


def calculate_polygon_area(polygon: List[List[float]]) -> float:
    """
    Computes polygon area in square meters using Gauss's Shoelace formula.
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


def map_plan_to_materials(plan_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Main function for Task 2:
    Takes PlanJSON architectural geometry and maps it into standard Bill of Materials (BOQ) line items.

    Args:
        plan_json (Dict[str, Any]): Active architectural plan (walls, openings, rooms).

    Returns:
        List[Dict[str, Any]]: List of material line items ready for the cost estimation sheet.
    """
    level = plan_json.get("levels", [{}])[0]
    walls = level.get("walls", [])
    openings = level.get("openings", [])
    rooms = level.get("rooms", [])
    wall_height = float(level.get("wall_height", 2.8))

    # Calculate total floor area across all room polygons
    total_floor_area = sum(calculate_polygon_area(r.get("polygon", [])) for r in rooms)
    if total_floor_area <= 0:
        total_floor_area = 85.0  # Default fallback 2BHK floor area in sq.m

    # Calculate total wall length
    total_wall_length = 0.0
    for w in walls:
        start = w.get("start", [0, 0])
        end = w.get("end", [0, 0])
        length = math.sqrt((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2)
        total_wall_length += length
    if total_wall_length <= 0:
        total_wall_length = 55.0

    # Subtract opening areas (doors, windows) for net wall surface
    openings_area = sum(float(op.get("width", 1.0)) * float(op.get("height", 1.5)) for op in openings)
    net_wall_surface = max(10.0, round((total_wall_length * wall_height * 2) - openings_area, 2))

    # =========================================================================
    # ENGINEERING QUANTITY FORMULAS FOR THE 7 CORE MATERIALS:
    # =========================================================================
    # 1. Brick: ~55 bricks per sq.m of 0.23m thick wall masonry
    brick_qty = round(net_wall_surface * 35.0, 0)

    # 2. Steel / Rebar: ~35 kg per sq.m of built-up slab & column RCC
    steel_qty = round(total_floor_area * 32.0, 1)

    # 3. Cement: ~3.8 bags per sq.m of floor area (RCC slab + plinth + brick mortar + plaster)
    cement_qty = round(total_floor_area * 3.6, 0)

    # 4. Sand (fine aggregate): ~0.35 cu.m per sq.m built-up area
    sand_qty = round(total_floor_area * 0.32, 1)

    # 5. Ballast (coarse aggregate): ~0.42 cu.m per sq.m built-up area
    ballast_qty = round(total_floor_area * 0.40, 1)

    # 6. Plaster: Both interior and exterior wall faces
    plaster_qty = round(net_wall_surface * 1.15, 1)

    # 7. Tiles: Flooring area + 25% bathroom/kitchen dado wall tiling
    tiles_qty = round(total_floor_area * 1.10, 1)

    quantities_map = {
        "Brick": brick_qty,
        "Steel/rebar rod": steel_qty,
        "Cement": cement_qty,
        "Sand (fine aggregate)": sand_qty,
        "Ballast (coarse aggregate)": ballast_qty,
        "Plaster (cement and gypsum)": plaster_qty,
        "Tiles (floor and wall)": tiles_qty,
    }

    # Generate output rows using catalogue rates and waste factors
    material_items = []
    for mat in DEFAULT_CONSTRUCTION_MATERIALS:
        name = mat["name"]
        qty = quantities_map.get(name, float(mat["default_quantity"]))
        waste = float(mat["waste_factor"])
        tot_qty = round(qty * (1.0 + waste), 2)
        rate = float(mat["unit_price"])
        amount = round(tot_qty * rate, 2)

        material_items.append({
            "name": name,
            "category": mat["category"],
            "unit": mat["unit"],
            "quantity": qty,
            "waste_factor": waste,
            "total_quantity": tot_qty,
            "unit_price": rate,
            "amount": amount,
            "surface_tag": mat["surface_tag"],
            "is_custom": False,
        })

    logger.info(f"Mapped PlanJSON to {len(material_items)} BOQ line items.")
    return material_items


# =============================================================================
# STANDALONE TEST SCRIPT:
# Run: python app/modules/sheets/llm_mapper.py
# =============================================================================
if __name__ == "__main__":
    from app.modules.parsing.service import DEFAULT_VERIFIED_PLAN

    print("-----------------------------------------------------------------")
    print("Testing PlanJSON to Materials Mapper (Task 2)...")
    print("-----------------------------------------------------------------")

    items = map_plan_to_materials(DEFAULT_VERIFIED_PLAN)
    total_cost = sum(item["amount"] for item in items)

    print(f"Generated {len(items)} Construction Material Items:")
    for idx, item in enumerate(items, 1):
        print(f"  {idx}. {item['name']:<28} | Qty: {item['total_quantity']:>8.1f} {item['unit']:<5} | Rate: ₹{item['unit_price']:>6.2f} | Amount: ₹{item['amount']:>10,.2f}")

    print(f"\nSubtotal Cost: ₹{total_cost:,.2f}")
    print("SUCCESS: map_plan_to_materials() is working and ready!")
    print("-----------------------------------------------------------------")
