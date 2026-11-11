"""
=============================================================================
Construtiva Raw Material Mapper & Quantity Surveying Engine (Task 2)
=============================================================================
File: app/modules/sheets/llm_mapper.py
Purpose:
  Maps verified PlanJSON from `app/modules/parsing/llm_parser.py` into the
  7 core construction materials at THREE hierarchical levels:
    - Project-Wide Totals (`materials` & `materials_by_key`)
    - Floor-Wise / Level-Wise (`level_summaries[i]["materials_by_key"]`)
    - Room-Wise (`room_breakdown[i]["materials_by_key"]`)
  Provides 3D model highlighting metadata (surface_tag, room_ids, element_ids)
  for interactive Three.js Click-to-Verify synchronization.
=============================================================================
"""

import sys
from pathlib import Path

_backend_root = str(Path(__file__).resolve().parents[3])
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

import math
import json
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("construtiva.sheets.llm_mapper")

# =============================================================================
# 1. LOCKED-IN ENGINEERING CONSTANTS (UAE + THEKEDAAR CALIBRATED)
# =============================================================================
DEFAULT_WALL_HEIGHT_M = 3.35          # 11 ft standard ceiling height (3.35 m)
PARSER_FALLBACK_WALL_HEIGHT_M = 2.80  # Default emitted by 2D parser when height is unstated
SHARED_WALL_REDUCTION_FACTOR = 0.72   # Deduplicates shared internal walls across adjacent rooms

DOOR_OPENING_AREA_M2 = 1.89           # Standard 0.9m x 2.1m door opening area
WINDOW_OPENING_AREA_M2 = 1.44         # Standard 1.2m x 1.2m window opening area
MIN_NET_WALL_RATIO = 0.50             # Net wall area floor (at least 50% of gross wall area)

PLINTH_WALL_FACTOR = 0.25             # 25% of ground floor net wall area for substructure plinth masonry
PARAPET_HEIGHT_M = 1.00               # 1.0m high roof terrace boundary parapet wall

# Concrete Constants (4.5-inch / 0.115m slab + 35% for beams, columns & footings)
SLAB_THICKNESS_M = 0.115
RCC_STRUCTURAL_MULTIPLIER = 1.35      # 0.115 * 1.35 = 0.15525 m3 wet concrete per m2 built area
DRY_VOLUME_MULTIPLIER = 1.54          # Converts wet concrete volume to dry mix volume
M20_TOTAL_PARTS = 5.5                 # M20 nominal mix (1 : 1.5 : 3 -> 5.5 total parts)

# 1. Masonry Constants
UAE_AAC_BLOCK_AREA_M2 = 0.12          # 600mm x 200mm standard UAE AAC block
INDIA_BRICKS_PER_M2 = 55.0            # Reference Indian clay/fly-ash bricks per m2 of wall
MASONRY_WASTE_FACTOR = 1.05           # 5% breakage & cutting waste

# 2. Steel / Rebar Constants
PLINTH_STEEL_KG_PER_M2 = 34.0         # Substructure/plinth steel per m2 of ground footprint
FLOOR_STEEL_KG_PER_M2 = 22.0          # Superstructure slab/beam/column steel per m2 of floor area
STEEL_WASTE_FACTOR = 1.10             # 10% lapping, bending & cutting waste
TMT_12MM_ROD_WEIGHT_KG = 10.656       # 0.888 kg/m * 12m standard UAE TMT bar

# 3. Cement Constants (50kg OPC/SRC Bags)
CEMENT_BAGS_PER_M3 = 28.8             # 1,440 kg/m3 bulk density / 50 kg per bag
MORTAR_CEMENT_BAGS_PER_M2 = 0.10      # Thin-bed AAC adhesive / blockwork mortar
EXT_PLASTER_CEMENT_BAGS_PER_M2 = 0.14 # 18mm external/wet area cement plaster
CEMENT_WASTE_FACTOR = 1.05            # 5% handling waste

# 4. Sand Constants (Washed Marine/Crushed Sand)
MORTAR_SAND_THICKNESS_M = 0.012
EXT_PLASTER_SAND_THICKNESS_M = 0.018
TILE_BEDDING_SCREED_THICKNESS_M = 0.025
SAND_BULK_DENSITY_TONS_M3 = 1.55
SAND_WASTE_FACTOR = 1.05
CFT_PER_M3 = 35.315                   # 1 m3 = 35.315 cubic feet

# 5. Ballast / Gitti Constants (10mm/20mm Crushed Gabbro)
GITTI_BULK_DENSITY_TONS_M3 = 1.50
GITTI_WASTE_FACTOR = 1.05

# 6. Plaster Constants (65% Internal Dry Gypsum / 35% External & Wet Cement)
INTERNAL_DRY_WALL_SHARE = 0.65
EXTERNAL_WET_WALL_SHARE = 0.35
GYPSUM_WALL_THICKNESS_M = 0.012       # 12mm internal wall gypsum plaster
GYPSUM_CEILING_THICKNESS_M = 0.006    # 6mm ceiling gypsum plaster
GYPSUM_WASTE_FACTOR = 1.15            # 15% application & mixing waste
GYPSUM_DENSITY_KG_M3 = 1000.0
GYPSUM_BAG_WEIGHT_KG = 30.0           # Standard 30kg ready-mix gypsum bag

# 7. Tile Constants (600x600mm UAE Porcelain)
SKIRTING_HEIGHT_M = 0.10              # 10cm (0.10m) wall skirting
STANDARD_TILE_AREA_M2 = 0.36          # 600mm x 600mm = 0.36 m2 per tile
TILE_WASTE_STANDARD = 1.05            # 5% straight lay waste
TILE_WASTE_HERRINGBONE = 1.15         # 15% herringbone / diagonal pattern waste


# =============================================================================
# 2. POLYGON GEOMETRY & UNIVERSAL SCOPE CALCULATOR
# =============================================================================

def _extract_core_plan_json(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Unwraps database wrapper if `plan_json` is nested inside a DB record."""
    if not isinstance(payload, dict):
        raise ValueError(f"Expected dict for PlanJSON, got {type(payload)}")
    if "levels" in payload and isinstance(payload["levels"], list):
        return payload
    if "plan_json" in payload and isinstance(payload["plan_json"], dict):
        return payload["plan_json"]
    raise ValueError("Invalid PlanJSON: missing 'levels' array.")


def _get_unit_scale(plan: Dict[str, Any]) -> float:
    """Returns multiplier to normalize plan coordinates to meters ('m')."""
    units = str(plan.get("units") or "m").lower().strip()
    if units in ("ft", "feet", "foot", "'", "sq_feet", "sqft"):
        return 0.3048
    if units in ("in", "inch", "inches", '"'):
        return 0.0254
    if units in ("mm", "millimeter", "millimeters"):
        return 0.001
    if units in ("cm", "centimeter", "centimeters"):
        return 0.01
    return 1.0


def compute_polygon_area_m2(polygon: List[List[float]], unit_scale: float = 1.0) -> float:
    """Computes exact area (m²) of any N-vertex polygon using the Shoelace Theorem."""
    n = len(polygon)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        x1 = float(polygon[i][0]) * unit_scale
        y1 = float(polygon[i][1]) * unit_scale
        x2 = float(polygon[(i + 1) % n][0]) * unit_scale
        y2 = float(polygon[(i + 1) % n][1]) * unit_scale
        area += (x1 * y2) - (x2 * y1)
    return abs(area) * 0.5


def compute_polygon_perimeter_m(polygon: List[List[float]], unit_scale: float = 1.0) -> float:
    """Computes exact perimeter (m) of any N-vertex polygon."""
    n = len(polygon)
    if n < 2:
        return 0.0
    perimeter = 0.0
    for i in range(n):
        x1 = float(polygon[i][0]) * unit_scale
        y1 = float(polygon[i][1]) * unit_scale
        x2 = float(polygon[(i + 1) % n][0]) * unit_scale
        y2 = float(polygon[(i + 1) % n][1]) * unit_scale
        perimeter += math.hypot(x2 - x1, y2 - y1)
    return perimeter


def compute_bounding_dims_m(polygon: List[List[float]], unit_scale: float = 1.0) -> Tuple[float, float]:
    """Returns (length_m, breadth_m) bounding span of a room polygon."""
    if not polygon:
        return 0.0, 0.0
    xs = [float(pt[0]) * unit_scale for pt in polygon]
    ys = [float(pt[1]) * unit_scale for pt in polygon]
    return round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3)


def _classify_room_kind(room: Dict[str, Any]) -> str:
    """Returns 'indoor', 'semi_open', 'outdoor', or 'void'."""
    explicit = str(room.get("kind") or "").lower().strip()
    if explicit in ("indoor", "semi_open", "outdoor", "void"):
        return explicit

    name = str(room.get("name") or "").lower()
    if any(k in name for k in ("lawn", "garden", "yard", "driveway", "parking", "plot")):
        return "outdoor"
    if any(k in name for k in ("verandah", "veranda", "balcony", "stair", "terrace", "sitout")):
        return "semi_open"
    if any(k in name for k in ("shaft", "open", "void", "duct", "ots")):
        return "void"
    return "indoor"


def _resolve_room_height_m(
    room: Dict[str, Any],
    level: Dict[str, Any],
    global_height_override_m: Optional[float] = None,
    use_standard_11ft_default: bool = True,
) -> float:
    """Resolves wall height H_i (default 3.35m / 11ft; doubled if double-height void)."""
    room_override = room.get("ceiling_height_override") or room.get("height_m")
    if isinstance(room_override, (int, float)) and float(room_override) > 1.5:
        base_h = float(room_override)
    elif isinstance(global_height_override_m, (int, float)) and float(global_height_override_m) > 1.5:
        base_h = float(global_height_override_m)
    else:
        lvl_h = float(level.get("wall_height", DEFAULT_WALL_HEIGHT_M))
        if use_standard_11ft_default and abs(lvl_h - PARSER_FALLBACK_WALL_HEIGHT_M) < 0.05:
            base_h = DEFAULT_WALL_HEIGHT_M
        else:
            base_h = lvl_h if lvl_h > 1.5 else DEFAULT_WALL_HEIGHT_M

    if bool(room.get("is_double_height_void", False)):
        base_h *= 2.0

    return round(base_h, 3)


def _compute_7_materials_for_scope(
    a_built_m2: float,
    a_ground_share_m2: float,
    a_net_wall_m2: float,
    a_plinth_wall_m2: float,
    a_parapet_wall_m2: float,
    a_skirting_m2: float,
    w_pattern: float,
    single_tile_area_m2: float,
    tile_size_mm: str,
    pattern_key: str,
    scope_room_ids: Optional[List[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Universal 7-Material Engine used for:
      1. Individual Room scope
      2. Individual Floor (Level) scope
      3. Full Project scope
    Returns a dictionary keyed by the 7 material IDs with explicit metrics/units,
    including 3D model highlighting metadata.
    """
    room_ids_ref = scope_room_ids or []

    if a_built_m2 <= 0.0 and a_net_wall_m2 <= 0.0:
        # Outdoor lawn or open void shaft (0 structural masonry/slab/flooring materials)
        return {
            "aac_blocks": {
                "id": "aac_blocks",
                "name": "AAC Blocks (600x200mm UAE Standard)",
                "category": "Masonry & Wall Structure",
                "surface_tag": "masonry_walls",
                "highlight_3d": {"target": "walls", "room_ids": room_ids_ref, "color": "#E57373"},
                "quantity": 0,
                "unit": "pieces",
                "secondary_quantity": 0.0,
                "secondary_unit": "m2",
                "waste_multiplier": MASONRY_WASTE_FACTOR,
                "details": {
                    "single_block_area_m2": UAE_AAC_BLOCK_AREA_M2,
                    "total_masonry_area_m2": 0.0,
                    "superstructure_only_pieces": 0,
                    "india_clay_bricks_equivalent": 0,
                },
            },
            "steel_rebar": {
                "id": "steel_rebar",
                "name": "TMT Steel Rebar (BS 4449 Grade 500B / 12m Bars)",
                "category": "Reinforcement Steel",
                "surface_tag": "structural_reinforcement",
                "highlight_3d": {"target": "structure", "room_ids": room_ids_ref, "color": "#78909C"},
                "quantity": 0.0,
                "unit": "metric_tons",
                "secondary_quantity": 0,
                "secondary_unit": "rods_12m",
                "waste_multiplier": STEEL_WASTE_FACTOR,
                "details": {"total_steel_kg": 0.0, "total_steel_tons": 0.0, "tmt_12m_rods_12mm_avg": 0},
            },
            "cement": {
                "id": "cement",
                "name": "Portland / Sulfate-Resisting Cement (50kg Bags)",
                "category": "Binders & Concrete",
                "surface_tag": "concrete_and_mortar",
                "highlight_3d": {"target": "concrete", "room_ids": room_ids_ref, "color": "#9E9E9E"},
                "quantity": 0,
                "unit": "bags_50kg",
                "secondary_quantity": 0.0,
                "secondary_unit": "metric_tons",
                "waste_multiplier": CEMENT_WASTE_FACTOR,
                "details": {"rcc_structural_bags": 0.0, "block_mortar_bags": 0.0, "external_wet_plaster_bags": 0.0, "total_weight_kg": 0},
            },
            "sand": {
                "id": "sand",
                "name": "Washed Marine / Crushed Concreting Sand",
                "category": "Fine Aggregate",
                "surface_tag": "fine_aggregate",
                "highlight_3d": {"target": "plaster_and_bedding", "room_ids": room_ids_ref, "color": "#FFE082"},
                "quantity": 0.0,
                "unit": "metric_tons",
                "secondary_quantity": 0.0,
                "secondary_unit": "m3",
                "waste_multiplier": SAND_WASTE_FACTOR,
                "details": {"volume_m3": 0.0, "volume_cubic_feet": 0.0},
            },
            "ballast_gitti": {
                "id": "ballast_gitti",
                "name": "Crushed Gabbro Coarse Aggregate (10mm / 20mm Ballast)",
                "category": "Coarse Aggregate",
                "surface_tag": "coarse_aggregate",
                "highlight_3d": {"target": "concrete_aggregate", "room_ids": room_ids_ref, "color": "#616161"},
                "quantity": 0.0,
                "unit": "metric_tons",
                "secondary_quantity": 0.0,
                "secondary_unit": "m3",
                "waste_multiplier": GITTI_WASTE_FACTOR,
                "details": {"volume_m3": 0.0, "volume_cubic_feet": 0.0},
            },
            "plaster": {
                "id": "plaster",
                "name": "Internal Gypsum Plaster (30kg Bags) & External Cement Plaster",
                "category": "Wall & Ceiling Finishes",
                "surface_tag": "wall_plaster",
                "highlight_3d": {"target": "wall_surfaces", "room_ids": room_ids_ref, "color": "#ECEFF1"},
                "quantity": 0,
                "unit": "bags_30kg",
                "secondary_quantity": 0.0,
                "secondary_unit": "m2_total_coverage",
                "waste_multiplier": GYPSUM_WASTE_FACTOR,
                "details": {"internal_gypsum_area_m2": 0.0, "internal_gypsum_weight_kg": 0.0, "external_wet_cement_plaster_area_m2": 0.0},
            },
            "tiles": {
                "id": "tiles",
                "name": f"Porcelain Floor & Skirting Tiles ({tile_size_mm}mm)",
                "category": "Flooring & Skirting",
                "surface_tag": "flooring_and_skirting",
                "highlight_3d": {"target": "flooring", "room_ids": room_ids_ref, "color": "#4DB6AC"},
                "quantity": 0,
                "unit": "pieces",
                "secondary_quantity": 0.0,
                "secondary_unit": "m2",
                "waste_multiplier": w_pattern,
                "details": {"tile_size_mm": tile_size_mm, "layout_pattern": pattern_key, "total_tiled_area_with_waste_m2": 0.0},
            },
        }

    a_total_masonry = a_net_wall_m2 + a_plinth_wall_m2 + a_parapet_wall_m2
    v_wet = a_built_m2 * SLAB_THICKNESS_M * RCC_STRUCTURAL_MULTIPLIER
    v_dry = v_wet * DRY_VOLUME_MULTIPLIER

    # 1. AAC Blocks (`pieces` & `m2`)
    aac_blocks_pieces = math.ceil((a_total_masonry / UAE_AAC_BLOCK_AREA_M2) * MASONRY_WASTE_FACTOR)
    aac_superstructure_only = math.ceil((a_net_wall_m2 / UAE_AAC_BLOCK_AREA_M2) * MASONRY_WASTE_FACTOR)
    india_bricks_pieces = math.ceil(a_total_masonry * INDIA_BRICKS_PER_M2 * MASONRY_WASTE_FACTOR)

    # 2. Steel / Rebar (`metric_tons`, `kg`, & `rods_12m`)
    plinth_steel_kg = (a_ground_share_m2 * PLINTH_STEEL_KG_PER_M2) * STEEL_WASTE_FACTOR
    super_steel_kg = (a_built_m2 * FLOOR_STEEL_KG_PER_M2) * STEEL_WASTE_FACTOR
    total_steel_kg = plinth_steel_kg + super_steel_kg
    total_steel_metric_tons = round(total_steel_kg / 1000.0, 2)
    tmt_12m_rods_count = math.ceil(total_steel_kg / TMT_12MM_ROD_WEIGHT_KG)

    # 3. Cement (`bags_50kg`, `metric_tons`, & `kg`)
    bags_rcc = ((1.0 / M20_TOTAL_PARTS) * v_dry) * CEMENT_BAGS_PER_M3
    bags_mortar = a_total_masonry * MORTAR_CEMENT_BAGS_PER_M2
    bags_ext_plaster = (a_net_wall_m2 * 2.0 * EXTERNAL_WET_WALL_SHARE) * EXT_PLASTER_CEMENT_BAGS_PER_M2
    total_cement_bags_50kg = math.ceil((bags_rcc + bags_mortar + bags_ext_plaster) * CEMENT_WASTE_FACTOR)

    # 4. Sand (`metric_tons`, `m3`, & `cubic_feet`)
    v_sand_rcc_m3 = (1.5 / M20_TOTAL_PARTS) * v_dry
    v_sand_mortar_m3 = a_total_masonry * MORTAR_SAND_THICKNESS_M
    v_sand_ext_plaster_m3 = a_net_wall_m2 * 2.0 * EXTERNAL_WET_WALL_SHARE * EXT_PLASTER_SAND_THICKNESS_M
    v_sand_screed_m3 = a_built_m2 * TILE_BEDDING_SCREED_THICKNESS_M
    v_sand_m3 = v_sand_rcc_m3 + v_sand_mortar_m3 + v_sand_ext_plaster_m3 + v_sand_screed_m3
    total_sand_metric_tons = round(v_sand_m3 * SAND_BULK_DENSITY_TONS_M3 * SAND_WASTE_FACTOR, 2)
    total_sand_cubic_feet = round(v_sand_m3 * CFT_PER_M3, 1)

    # 5. Ballast / Gitti (`metric_tons`, `m3`, & `cubic_feet`)
    v_gitti_m3 = ((3.0 / M20_TOTAL_PARTS) * v_dry) * GITTI_WASTE_FACTOR
    total_gitti_metric_tons = round(v_gitti_m3 * GITTI_BULK_DENSITY_TONS_M3, 2)
    total_gitti_cubic_feet = round(v_gitti_m3 * CFT_PER_M3, 1)

    # 6. Plaster (`bags_30kg`, `kg`, & `m2_total_coverage`)
    a_gypsum_m2 = (a_net_wall_m2 * 2.0 * INTERNAL_DRY_WALL_SHARE) + a_built_m2
    v_gypsum_m3 = (
        (a_net_wall_m2 * 2.0 * INTERNAL_DRY_WALL_SHARE * GYPSUM_WALL_THICKNESS_M)
        + (a_built_m2 * GYPSUM_CEILING_THICKNESS_M)
    ) * GYPSUM_WASTE_FACTOR
    gypsum_weight_kg = round(v_gypsum_m3 * GYPSUM_DENSITY_KG_M3, 1)
    gypsum_weight_tons = round(gypsum_weight_kg / 1000.0, 2)
    gypsum_bags_30kg = math.ceil(gypsum_weight_kg / GYPSUM_BAG_WEIGHT_KG)
    a_ext_cement_plaster_m2 = round(a_net_wall_m2 * 2.0 * EXTERNAL_WET_WALL_SHARE, 2)

    # 7. Tiles (`pieces` & `m2`)
    a_tile_total_m2 = round((a_built_m2 + a_skirting_m2) * w_pattern, 2)
    total_tile_pieces = math.ceil(a_tile_total_m2 / single_tile_area_m2)

    return {
        "aac_blocks": {
            "id": "aac_blocks",
            "name": "AAC Blocks (600x200mm UAE Standard)",
            "category": "Masonry & Wall Structure",
            "surface_tag": "masonry_walls",
            "highlight_3d": {"target": "walls", "room_ids": room_ids_ref, "color": "#E57373"},
            "quantity": aac_blocks_pieces,
            "unit": "pieces",
            "secondary_quantity": round(a_total_masonry, 2),
            "secondary_unit": "m2",
            "waste_multiplier": MASONRY_WASTE_FACTOR,
            "details": {
                "single_block_area_m2": UAE_AAC_BLOCK_AREA_M2,
                "total_masonry_area_m2": round(a_total_masonry, 2),
                "net_superstructure_wall_m2": round(a_net_wall_m2, 2),
                "plinth_wall_area_m2": round(a_plinth_wall_m2, 2),
                "parapet_wall_area_m2": round(a_parapet_wall_m2, 2),
                "superstructure_only_pieces": aac_superstructure_only,
                "india_clay_bricks_equivalent": india_bricks_pieces,
            },
        },
        "steel_rebar": {
            "id": "steel_rebar",
            "name": "TMT Steel Rebar (BS 4449 Grade 500B / 12m Bars)",
            "category": "Reinforcement Steel",
            "surface_tag": "structural_reinforcement",
            "highlight_3d": {"target": "structure", "room_ids": room_ids_ref, "color": "#78909C"},
            "quantity": total_steel_metric_tons,
            "unit": "metric_tons",
            "secondary_quantity": tmt_12m_rods_count,
            "secondary_unit": "rods_12m",
            "waste_multiplier": STEEL_WASTE_FACTOR,
            "details": {
                "total_steel_kg": round(total_steel_kg, 1),
                "total_steel_tons": total_steel_metric_tons,
                "tmt_12m_rods_12mm_avg": tmt_12m_rods_count,
                "plinth_steel_kg_with_waste": round(plinth_steel_kg, 1),
                "superstructure_steel_kg_with_waste": round(super_steel_kg, 1),
            },
        },
        "cement": {
            "id": "cement",
            "name": "Portland / Sulfate-Resisting Cement (50kg Bags)",
            "category": "Binders & Concrete",
            "surface_tag": "concrete_and_mortar",
            "highlight_3d": {"target": "concrete", "room_ids": room_ids_ref, "color": "#9E9E9E"},
            "quantity": total_cement_bags_50kg,
            "unit": "bags_50kg",
            "secondary_quantity": round((total_cement_bags_50kg * 50.0) / 1000.0, 2),
            "secondary_unit": "metric_tons",
            "waste_multiplier": CEMENT_WASTE_FACTOR,
            "details": {
                "rcc_structural_bags": round(bags_rcc, 1),
                "block_mortar_bags": round(bags_mortar, 1),
                "external_wet_plaster_bags": round(bags_ext_plaster, 1),
                "total_weight_kg": total_cement_bags_50kg * 50,
            },
        },
        "sand": {
            "id": "sand",
            "name": "Washed Marine / Crushed Concreting Sand",
            "category": "Fine Aggregate",
            "surface_tag": "fine_aggregate",
            "highlight_3d": {"target": "plaster_and_bedding", "room_ids": room_ids_ref, "color": "#FFE082"},
            "quantity": total_sand_metric_tons,
            "unit": "metric_tons",
            "secondary_quantity": round(v_sand_m3, 2),
            "secondary_unit": "m3",
            "waste_multiplier": SAND_WASTE_FACTOR,
            "details": {
                "volume_m3": round(v_sand_m3, 2),
                "volume_cubic_feet": total_sand_cubic_feet,
                "rcc_sand_m3": round(v_sand_rcc_m3, 2),
                "mortar_sand_m3": round(v_sand_mortar_m3, 2),
                "external_plaster_sand_m3": round(v_sand_ext_plaster_m3, 2),
                "floor_screed_sand_m3": round(v_sand_screed_m3, 2),
            },
        },
        "ballast_gitti": {
            "id": "ballast_gitti",
            "name": "Crushed Gabbro Coarse Aggregate (10mm / 20mm Ballast)",
            "category": "Coarse Aggregate",
            "surface_tag": "coarse_aggregate",
            "highlight_3d": {"target": "concrete_aggregate", "room_ids": room_ids_ref, "color": "#616161"},
            "quantity": total_gitti_metric_tons,
            "unit": "metric_tons",
            "secondary_quantity": round(v_gitti_m3, 2),
            "secondary_unit": "m3",
            "waste_multiplier": GITTI_WASTE_FACTOR,
            "details": {
                "volume_m3": round(v_gitti_m3, 2),
                "volume_cubic_feet": total_gitti_cubic_feet,
                "bulk_density_tons_m3": GITTI_BULK_DENSITY_TONS_M3,
            },
        },
        "plaster": {
            "id": "plaster",
            "name": "Internal Gypsum Plaster (30kg Bags) & External Cement Plaster",
            "category": "Wall & Ceiling Finishes",
            "surface_tag": "wall_plaster",
            "highlight_3d": {"target": "wall_surfaces", "room_ids": room_ids_ref, "color": "#ECEFF1"},
            "quantity": gypsum_bags_30kg,
            "unit": "bags_30kg",
            "secondary_quantity": round(a_gypsum_m2 + a_ext_cement_plaster_m2, 2),
            "secondary_unit": "m2_total_coverage",
            "waste_multiplier": GYPSUM_WASTE_FACTOR,
            "details": {
                "internal_gypsum_area_m2": round(a_gypsum_m2, 2),
                "internal_gypsum_volume_m3": round(v_gypsum_m3, 3),
                "internal_gypsum_weight_kg": gypsum_weight_kg,
                "internal_gypsum_metric_tons": gypsum_weight_tons,
                "internal_gypsum_bags_30kg": gypsum_bags_30kg,
                "external_wet_cement_plaster_area_m2": a_ext_cement_plaster_m2,
            },
        },
        "tiles": {
            "id": "tiles",
            "name": f"Porcelain Floor & Skirting Tiles ({tile_size_mm}mm)",
            "category": "Flooring & Skirting",
            "surface_tag": "flooring_and_skirting",
            "highlight_3d": {"target": "flooring", "room_ids": room_ids_ref, "color": "#4DB6AC"},
            "quantity": total_tile_pieces,
            "unit": "pieces",
            "secondary_quantity": a_tile_total_m2,
            "secondary_unit": "m2",
            "waste_multiplier": w_pattern,
            "details": {
                "tile_size_mm": tile_size_mm,
                "single_tile_area_m2": single_tile_area_m2,
                "layout_pattern": pattern_key,
                "net_floor_area_m2": round(a_built_m2, 2),
                "skirting_area_m2": round(a_skirting_m2, 2),
                "total_tiled_area_with_waste_m2": a_tile_total_m2,
            },
        },
    }


# =============================================================================
# 3. MAIN TASK 2 FUNCTION: PlanJSON ➔ ROOM, FLOOR & PROJECT RAW MATERIALS
# =============================================================================

def map_plan_to_materials(
    plan_payload: Dict[str, Any],
    tile_pattern: str = "standard",
    tile_size_mm: str = "600x600",
    global_ceiling_height_m: Optional[float] = None,
    use_standard_11ft_default: bool = True,
) -> Dict[str, Any]:
    """
    Task 2 Primary Entrypoint:
    Computes the 7 raw materials with explicit metrics at:
      - Project-Wide level (`materials` & `materials_by_key`)
      - Floor-Wise level (`level_summaries[i]["materials"]` & `materials_by_key`)
      - Room-Wise level (`room_breakdown[i]["materials"]` & `materials_by_key`)
    """
    plan = _extract_core_plan_json(plan_payload)
    unit_scale = _get_unit_scale(plan)
    levels = plan.get("levels", [])
    if not levels:
        raise ValueError("PlanJSON contains no levels to calculate materials.")

    pattern_key = str(tile_pattern or "standard").lower().strip()
    w_pattern = (
        TILE_WASTE_HERRINGBONE
        if pattern_key in ("herringbone", "diagonal", "chevron", "complex")
        else TILE_WASTE_STANDARD
    )
    tile_size_map = {"600x600": 0.36, "800x800": 0.64, "1200x600": 0.72}
    single_tile_area_m2 = tile_size_map.get(tile_size_mm, STANDARD_TILE_AREA_M2)

    num_levels = len(levels)
    level_summaries: List[Dict[str, Any]] = []
    room_breakdown: List[Dict[str, Any]] = []

    a_ground = 0.0
    a_built_total = 0.0
    a_net_wall_total = 0.0
    a_net_wall_ground = 0.0
    a_skirting_total = 0.0

    total_doors_all_levels = 0
    total_windows_all_levels = 0
    total_columns_all_levels = 0
    all_built_room_ids: List[str] = []

    for lvl_idx, lvl in enumerate(levels):
        rooms = lvl.get("rooms", [])
        openings = lvl.get("openings", [])
        columns = lvl.get("columns", [])
        walls = lvl.get("walls", [])

        lvl_built_area = 0.0
        lvl_gross_wall_area = 0.0
        lvl_skirting_area = 0.0
        lvl_room_records: List[Dict[str, Any]] = []
        lvl_built_room_ids: List[str] = []

        # Pass 1: Measure every room on this floor
        for r in rooms:
            poly = r.get("polygon", [])
            if not isinstance(poly, list) or len(poly) < 3:
                continue

            r_id = str(r.get("id", f"room_{len(room_breakdown) + 1}"))
            r_kind = _classify_room_kind(r)
            area_m2 = compute_polygon_area_m2(poly, unit_scale)
            perim_m = compute_polygon_perimeter_m(poly, unit_scale)
            len_m, brd_m = compute_bounding_dims_m(poly, unit_scale)
            h_room = _resolve_room_height_m(
                r, lvl, global_ceiling_height_m, use_standard_11ft_default
            )

            counts_as_built = r_kind in ("indoor", "semi_open")
            r_gross_wall = (perim_m * SHARED_WALL_REDUCTION_FACTOR * h_room) if counts_as_built else 0.0
            r_skirting = (perim_m * SKIRTING_HEIGHT_M) if counts_as_built else 0.0

            if counts_as_built:
                lvl_built_area += area_m2
                lvl_gross_wall_area += r_gross_wall
                lvl_skirting_area += r_skirting
                lvl_built_room_ids.append(r_id)
                all_built_room_ids.append(r_id)

            lvl_room_records.append({
                "raw_room": r,
                "id": r_id,
                "kind": r_kind,
                "poly": poly,
                "area_m2": area_m2,
                "perim_m": perim_m,
                "len_m": len_m,
                "brd_m": brd_m,
                "h_room": h_room,
                "counts_as_built": counts_as_built,
                "r_gross_wall": r_gross_wall,
                "r_skirting": r_skirting,
            })

        # Fallback if a level has walls but 0 rooms
        if lvl_built_area <= 0.0 and walls:
            xs = [float(pt[0]) * unit_scale for w in walls for pt in (w["start"], w["end"])]
            ys = [float(pt[1]) * unit_scale for w in walls for pt in (w["start"], w["end"])]
            lvl_built_area = (max(xs) - min(xs)) * (max(ys) - min(ys))
            h_default = _resolve_room_height_m({}, lvl, global_ceiling_height_m, use_standard_11ft_default)
            total_wall_len = sum(
                math.hypot(
                    (float(w["end"][0]) - float(w["start"][0])) * unit_scale,
                    (float(w["end"][1]) - float(w["start"][1])) * unit_scale,
                )
                for w in walls
            )
            lvl_gross_wall_area = total_wall_len * h_default
            lvl_skirting_area = total_wall_len * SKIRTING_HEIGHT_M

        lvl_doors = sum(1 for op in openings if str(op.get("type", "")).lower() == "door")
        lvl_windows = sum(1 for op in openings if str(op.get("type", "")).lower() == "window")
        lvl_openings_area = (lvl_doors * DOOR_OPENING_AREA_M2) + (lvl_windows * WINDOW_OPENING_AREA_M2)

        lvl_net_wall_area = max(
            lvl_gross_wall_area - lvl_openings_area,
            MIN_NET_WALL_RATIO * lvl_gross_wall_area,
        )

        if lvl_idx == 0:
            a_ground = lvl_built_area
            a_net_wall_ground = lvl_net_wall_area

        # Plinth belongs to Ground Floor (lvl_idx == 0); Parapet belongs to Top Floor (lvl_idx == num_levels - 1)
        lvl_plinth_wall = (PLINTH_WALL_FACTOR * lvl_net_wall_area) if lvl_idx == 0 else 0.0
        lvl_parapet_wall = (4.0 * math.sqrt(a_ground) * PARAPET_HEIGHT_M) if (lvl_idx == num_levels - 1) else 0.0
        lvl_ground_steel_area = lvl_built_area if lvl_idx == 0 else 0.0

        # Pass 2: Compute Room-Wise 7 Raw Materials for every room on this floor
        for rec in lvl_room_records:
            r = rec["raw_room"]
            r_id = rec["id"]
            if rec["counts_as_built"] and lvl_gross_wall_area > 0 and lvl_built_area > 0:
                wall_share = rec["r_gross_wall"] / lvl_gross_wall_area
                area_share = rec["area_m2"] / lvl_built_area

                r_net_wall = lvl_net_wall_area * wall_share
                r_plinth_share = lvl_plinth_wall * wall_share
                r_parapet_share = lvl_parapet_wall * area_share
                r_ground_steel_share = lvl_ground_steel_area * area_share

                room_mats_by_key = _compute_7_materials_for_scope(
                    a_built_m2=rec["area_m2"],
                    a_ground_share_m2=r_ground_steel_share,
                    a_net_wall_m2=r_net_wall,
                    a_plinth_wall_m2=r_plinth_share,
                    a_parapet_wall_m2=r_parapet_share,
                    a_skirting_m2=rec["r_skirting"],
                    w_pattern=w_pattern,
                    single_tile_area_m2=single_tile_area_m2,
                    tile_size_mm=tile_size_mm,
                    pattern_key=pattern_key,
                    scope_room_ids=[r_id],
                )
            else:
                r_net_wall = 0.0
                room_mats_by_key = _compute_7_materials_for_scope(
                    0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                    w_pattern, single_tile_area_m2, tile_size_mm, pattern_key,
                    scope_room_ids=[r_id],
                )

            room_breakdown.append({
                "level_index": lvl_idx,
                "id": r_id,
                "name": r.get("name", "Room"),
                "kind": rec["kind"],
                "vertices_count": len(rec["poly"]),
                "is_complex_polygon": len(rec["poly"]) > 4,
                "length_m": round(rec["len_m"], 2),
                "breadth_m": round(rec["brd_m"], 2),
                "perimeter_m": round(rec["perim_m"], 2),
                "area_m2": round(rec["area_m2"], 2),
                "area_sqft": round(rec["area_m2"] * 10.7639, 2),
                "height_m": rec["h_room"],
                "net_wall_area_m2": round(r_net_wall, 2),
                "included_in_built_area": rec["counts_as_built"],
                "materials": list(room_mats_by_key.values()),
                "materials_by_key": room_mats_by_key,
            })

        # Compute Floor-Wise (Level-Wise) 7 Raw Materials
        lvl_mats_by_key = _compute_7_materials_for_scope(
            a_built_m2=lvl_built_area,
            a_ground_share_m2=lvl_ground_steel_area,
            a_net_wall_m2=lvl_net_wall_area,
            a_plinth_wall_m2=lvl_plinth_wall,
            a_parapet_wall_m2=lvl_parapet_wall,
            a_skirting_m2=lvl_skirting_area,
            w_pattern=w_pattern,
            single_tile_area_m2=single_tile_area_m2,
            tile_size_mm=tile_size_mm,
            pattern_key=pattern_key,
            scope_room_ids=lvl_built_room_ids,
        )

        level_summaries.append({
            "level_index": lvl_idx,
            "level_name": f"Level {lvl_idx + 1}" if num_levels > 1 else (plan.get("subject") or "Ground Floor"),
            "elevation_m": float(lvl.get("elevation", 0.0)),
            "built_area_m2": round(lvl_built_area, 2),
            "built_area_sqft": round(lvl_built_area * 10.7639, 2),
            "gross_wall_area_m2": round(lvl_gross_wall_area, 2),
            "openings_area_m2": round(lvl_openings_area, 2),
            "net_wall_area_m2": round(lvl_net_wall_area, 2),
            "plinth_wall_area_m2": round(lvl_plinth_wall, 2),
            "parapet_wall_area_m2": round(lvl_parapet_wall, 2),
            "doors_count": lvl_doors,
            "windows_count": lvl_windows,
            "columns_count": len(columns),
            "materials": list(lvl_mats_by_key.values()),
            "materials_by_key": lvl_mats_by_key,
        })

        a_built_total += lvl_built_area
        a_net_wall_total += lvl_net_wall_area
        a_skirting_total += lvl_skirting_area
        total_doors_all_levels += lvl_doors
        total_windows_all_levels += lvl_windows
        total_columns_all_levels += len(columns)

    # Project-Wide Totals
    a_plinth_wall_total = PLINTH_WALL_FACTOR * a_net_wall_ground
    a_parapet_wall_total = 4.0 * math.sqrt(a_ground) * PARAPET_HEIGHT_M
    a_total_masonry = a_net_wall_total + a_plinth_wall_total + a_parapet_wall_total
    v_wet_total = a_built_total * SLAB_THICKNESS_M * RCC_STRUCTURAL_MULTIPLIER
    v_dry_total = v_wet_total * DRY_VOLUME_MULTIPLIER

    project_materials_by_key = _compute_7_materials_for_scope(
        a_built_m2=a_built_total,
        a_ground_share_m2=a_ground,
        a_net_wall_m2=a_net_wall_total,
        a_plinth_wall_m2=a_plinth_wall_total,
        a_parapet_wall_m2=a_parapet_wall_total,
        a_skirting_m2=a_skirting_total,
        w_pattern=w_pattern,
        single_tile_area_m2=single_tile_area_m2,
        tile_size_mm=tile_size_mm,
        pattern_key=pattern_key,
        scope_room_ids=all_built_room_ids,
    )

    return {
        "project_metadata": {
            "project_title": plan.get("project_title") or "NA",
            "subject": plan.get("subject") or "NA",
            "client": plan.get("client") or "NA",
            "architect": plan.get("architect") or "NA",
            "units": "m",
            "scale_source": plan.get("scale_source", "dimension_label"),
            "levels_count": num_levels,
        },
        "geometry_summary": {
            "a_ground_m2": round(a_ground, 2),
            "a_ground_sqft": round(a_ground * 10.7639, 2),
            "a_built_total_m2": round(a_built_total, 2),
            "a_built_total_sqft": round(a_built_total * 10.7639, 2),
            "a_net_wall_m2": round(a_net_wall_total, 2),
            "a_plinth_wall_m2": round(a_plinth_wall_total, 2),
            "a_parapet_wall_m2": round(a_parapet_wall_total, 2),
            "a_total_masonry_m2": round(a_total_masonry, 2),
            "v_wet_concrete_m3": round(v_wet_total, 2),
            "v_dry_concrete_m3": round(v_dry_total, 2),
            "total_doors": total_doors_all_levels,
            "total_windows": total_windows_all_levels,
            "total_columns": total_columns_all_levels,
        },
        "materials": list(project_materials_by_key.values()),
        "materials_by_key": project_materials_by_key,
        "level_summaries": level_summaries,
        "room_breakdown": room_breakdown,
    }


# Aliases for downstream imports
calculate_raw_materials_from_plan = map_plan_to_materials
generate_material_sheet = map_plan_to_materials
