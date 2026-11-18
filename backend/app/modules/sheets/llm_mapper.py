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
import re
import logging
from typing import Dict, Any, List, Optional, Tuple

from app.modules.plans.room_kind import is_open_void_label
from app.modules.plans.room_types import stored_or_derived_boq_type
from app.modules.sheets.boq_rows import build_boq_rows
from app.modules.sheets.formulas import calculation_warnings, compute_items
from app.modules.sheets.primitives import (
    LevelFact,
    OpeningFact,
    PlanFacts,
    Primitives,
    RoomFact,
    ceil,
    derive_primitives,
)
from app.modules.sheets.constants import (  # noqa: F401  (re-exported)
    CEMENT_BAGS_PER_M3,
    CEMENT_WASTE_FACTOR,
    CFT_PER_M3,
    DEFAULT_WALL_HEIGHT_M,
    DOOR_OPENING_AREA_M2,
    DRY_VOLUME_MULTIPLIER,
    EXT_PLASTER_CEMENT_BAGS_PER_M2,
    EXT_PLASTER_SAND_THICKNESS_M,
    FLOOR_STEEL_KG_PER_M2,
    GITTI_BULK_DENSITY_TONS_M3,
    GITTI_WASTE_FACTOR,
    GYPSUM_BAG_WEIGHT_KG,
    GYPSUM_CEILING_THICKNESS_M,
    GYPSUM_DENSITY_KG_M3,
    GYPSUM_WALL_THICKNESS_M,
    GYPSUM_WASTE_FACTOR,
    INDIA_BRICKS_PER_M2,
    M20_TOTAL_PARTS,
    MASONRY_WASTE_FACTOR,
    MIN_NET_WALL_RATIO,
    MORTAR_CEMENT_BAGS_PER_M2,
    MORTAR_SAND_THICKNESS_M,
    PARAPET_HEIGHT_M,
    PARSER_FALLBACK_WALL_HEIGHT_M,
    PLINTH_STEEL_KG_PER_M2,
    PLINTH_WALL_FACTOR,
    RCC_STRUCTURAL_MULTIPLIER,
    SAND_BULK_DENSITY_TONS_M3,
    SAND_WASTE_FACTOR,
    SHARED_WALL_REDUCTION_FACTOR,
    SKIRTING_HEIGHT_M,
    SLAB_THICKNESS_M,
    STANDARD_TILE_AREA_M2,
    STEEL_WASTE_FACTOR,
    TILE_BEDDING_SCREED_THICKNESS_M,
    TILE_WASTE_HERRINGBONE,
    TILE_WASTE_STANDARD,
    TMT_12MM_ROD_WEIGHT_KG,
    UAE_AAC_BLOCK_AREA_M2,
    WINDOW_OPENING_AREA_M2,
)

logger = logging.getLogger("construtiva.sheets.llm_mapper")


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
    # "open" alone must not match: "Open Kitchen" is a room. See plans/room_kind.py.
    if any(k in name for k in ("shaft", "void", "duct", "ots")) or is_open_void_label(name):
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
        lvl_h = float(level.get("wall_height") or DEFAULT_WALL_HEIGHT_M)
        source = level.get("wall_height_source")
        if source == "stated":
            # Schema 2.0: the drawing states this height, so it is used as given.
            base_h = lvl_h if lvl_h > 1.5 else DEFAULT_WALL_HEIGHT_M
        elif use_standard_11ft_default and (
            source == "default" or abs(lvl_h - PARSER_FALLBACK_WALL_HEIGHT_M) < 0.05
        ):
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
    *,
    s_gyp: float = 0.0,
    s_cem: float = 1.0,
) -> Dict[str, Dict[str, Any]]:
    """
    Universal 7-Material Engine used for:
      1. Individual Room scope
      2. Individual Floor (Level) scope
      3. Full Project scope
    Returns a dictionary keyed by the 7 material IDs with explicit metrics/units,
    including 3D model highlighting metadata.

    `s_gyp` and `s_cem` are the plan's shares of wall faces that get gypsum plaster and
    cement plaster (spec section 3; they add up to 1). They are computed once per plan
    from the wall model and passed to every scope, so room and level values add up to
    the project totals:
      gypsum-plastered wall area of a scope = 2 x s_gyp x a_net_wall
      cement-plastered area of a scope      = 2 x s_cem x a_net_wall + 2 x a_parapet_wall
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
    # The wall model (spec section 3): which wall faces of this scope get which plaster.
    a_gyp_wall_m2 = 2.0 * s_gyp * a_net_wall_m2
    a_cem_plaster_m2 = 2.0 * s_cem * a_net_wall_m2 + 2.0 * a_parapet_wall_m2

    # 1. AAC Blocks (`pieces` & `m2`)
    aac_blocks_pieces = ceil((a_total_masonry / UAE_AAC_BLOCK_AREA_M2) * MASONRY_WASTE_FACTOR)
    aac_superstructure_only = ceil((a_net_wall_m2 / UAE_AAC_BLOCK_AREA_M2) * MASONRY_WASTE_FACTOR)
    india_bricks_pieces = ceil(a_total_masonry * INDIA_BRICKS_PER_M2 * MASONRY_WASTE_FACTOR)

    # 2. Steel / Rebar (`metric_tons`, `kg`, & `rods_12m`)
    plinth_steel_kg = (a_ground_share_m2 * PLINTH_STEEL_KG_PER_M2) * STEEL_WASTE_FACTOR
    super_steel_kg = (a_built_m2 * FLOOR_STEEL_KG_PER_M2) * STEEL_WASTE_FACTOR
    total_steel_kg = plinth_steel_kg + super_steel_kg
    total_steel_metric_tons = round(total_steel_kg / 1000.0, 2)
    tmt_12m_rods_count = ceil(total_steel_kg / TMT_12MM_ROD_WEIGHT_KG)

    # 3. Cement (`bags_50kg`, `metric_tons`, & `kg`)
    bags_rcc = ((1.0 / M20_TOTAL_PARTS) * v_dry) * CEMENT_BAGS_PER_M3
    bags_mortar = a_total_masonry * MORTAR_CEMENT_BAGS_PER_M2
    bags_ext_plaster = a_cem_plaster_m2 * EXT_PLASTER_CEMENT_BAGS_PER_M2
    total_cement_bags_50kg = ceil((bags_rcc + bags_mortar + bags_ext_plaster) * CEMENT_WASTE_FACTOR)

    # 4. Sand (`metric_tons`, `m3`, & `cubic_feet`)
    v_sand_rcc_m3 = (1.5 / M20_TOTAL_PARTS) * v_dry
    v_sand_mortar_m3 = a_total_masonry * MORTAR_SAND_THICKNESS_M
    v_sand_ext_plaster_m3 = a_cem_plaster_m2 * EXT_PLASTER_SAND_THICKNESS_M
    v_sand_screed_m3 = a_built_m2 * TILE_BEDDING_SCREED_THICKNESS_M
    v_sand_m3 = v_sand_rcc_m3 + v_sand_mortar_m3 + v_sand_ext_plaster_m3 + v_sand_screed_m3
    total_sand_metric_tons = round(v_sand_m3 * SAND_BULK_DENSITY_TONS_M3 * SAND_WASTE_FACTOR, 2)
    total_sand_cubic_feet = round(v_sand_m3 * CFT_PER_M3, 1)

    # 5. Ballast / Gitti (`metric_tons`, `m3`, & `cubic_feet`)
    v_gitti_m3 = ((3.0 / M20_TOTAL_PARTS) * v_dry) * GITTI_WASTE_FACTOR
    total_gitti_metric_tons = round(v_gitti_m3 * GITTI_BULK_DENSITY_TONS_M3, 2)
    total_gitti_cubic_feet = round(v_gitti_m3 * CFT_PER_M3, 1)

    # 6. Plaster (`bags_30kg`, `kg`, & `m2_total_coverage`)
    a_gypsum_m2 = a_gyp_wall_m2 + a_built_m2
    v_gypsum_m3 = (
        (a_gyp_wall_m2 * GYPSUM_WALL_THICKNESS_M)
        + (a_built_m2 * GYPSUM_CEILING_THICKNESS_M)
    ) * GYPSUM_WASTE_FACTOR
    gypsum_weight_kg = round(v_gypsum_m3 * GYPSUM_DENSITY_KG_M3, 1)
    gypsum_weight_tons = round(gypsum_weight_kg / 1000.0, 2)
    gypsum_bags_30kg = ceil(v_gypsum_m3 * GYPSUM_DENSITY_KG_M3 / GYPSUM_BAG_WEIGHT_KG)
    a_ext_cement_plaster_m2 = round(a_cem_plaster_m2, 2)

    # 7. Tiles (`pieces` & `m2`)
    tile_area_exact_m2 = (a_built_m2 + a_skirting_m2) * w_pattern
    a_tile_total_m2 = round(tile_area_exact_m2, 2)
    total_tile_pieces = ceil(tile_area_exact_m2 / single_tile_area_m2)

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
                "internal_gypsum_wall_area_m2": round(a_gyp_wall_m2, 2),
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

def _tile_dims_mm(tile_size_mm: str) -> tuple[float, float]:
    """(a, b) in mm of a tile size such as "600x600"; 600 x 600 when it cannot be read."""
    match = re.fullmatch(
        r"\s*(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*", str(tile_size_mm or "")
    )
    if match:
        a, b = float(match.group(1)), float(match.group(2))
        if a > 0 and b > 0:
            return a, b
    return 600.0, 600.0


def _opening_size_m(value: Any, unit_scale: float) -> float | None:
    """A positive opening size in metres, or None when the plan gives none."""
    if isinstance(value, bool):
        return None
    try:
        size = float(value) * unit_scale
    except (TypeError, ValueError):
        return None
    return size if math.isfinite(size) and size > 0 else None


def _box_dims_m(points: list[tuple[float, float]]) -> tuple[float, float]:
    """(width, depth) of the bounding box of points already in metres."""
    if not points:
        return 0.0, 0.0
    xs = [pt[0] for pt in points]
    ys = [pt[1] for pt in points]
    return max(xs) - min(xs), max(ys) - min(ys)


def _measure_level(
    lvl: dict[str, Any],
    lvl_idx: int,
    unit_scale: float,
    global_ceiling_height_m: float | None,
    use_standard_11ft_default: bool,
    warnings: list[str],
    room_serial_start: int,
) -> dict[str, Any]:
    """Everything measured on one level: rooms, wall areas, openings and bounding boxes.

    `unit_scale` is applied to every coordinate before anything is measured.
    """
    rooms = lvl.get("rooms", [])
    openings = lvl.get("openings", [])
    walls = lvl.get("walls", [])

    built_area = 0.0
    gross_wall_area = 0.0
    skirting_area = 0.0
    records: list[dict[str, Any]] = []
    built_points: list[tuple[float, float]] = []
    all_points: list[tuple[float, float]] = []

    for r in rooms:
        poly = r.get("polygon", [])
        if not isinstance(poly, list) or len(poly) < 3:
            continue

        r_id = str(r.get("id", f"room_{room_serial_start + len(records) + 1}"))
        r_kind = _classify_room_kind(r)
        area_m2 = compute_polygon_area_m2(poly, unit_scale)
        perim_m = compute_polygon_perimeter_m(poly, unit_scale)
        len_m, brd_m = compute_bounding_dims_m(poly, unit_scale)
        h_room = _resolve_room_height_m(r, lvl, global_ceiling_height_m, use_standard_11ft_default)
        points = [(float(pt[0]) * unit_scale, float(pt[1]) * unit_scale) for pt in poly]

        counts_as_built = r_kind in ("indoor", "semi_open")
        # Indoor rooms only. A plan stored without `boq_type` gets it from the name.
        r_boq_type = (
            stored_or_derived_boq_type(r.get("name"), r.get("boq_type"))
            if r_kind == "indoor"
            else None
        )
        r_gross_wall = (perim_m * SHARED_WALL_REDUCTION_FACTOR * h_room) if counts_as_built else 0.0
        r_skirting = (perim_m * SKIRTING_HEIGHT_M) if counts_as_built else 0.0

        # An outline with no area is not a room: it is listed, but nothing is counted for it.
        has_area = area_m2 > 0.0
        if has_area:
            all_points.extend(points)
        if counts_as_built and has_area:
            built_area += area_m2
            gross_wall_area += r_gross_wall
            skirting_area += r_skirting
            built_points.extend(points)

        records.append({
            "raw_room": r,
            "id": r_id,
            "name": str(r.get("name") or "Room"),
            "kind": r_kind,
            "boq_type": r_boq_type,
            "poly": poly,
            "area_m2": area_m2,
            "perim_m": perim_m,
            "len_m": len_m,
            "brd_m": brd_m,
            "h_room": h_room,
            "counts_as_built": counts_as_built,
            "has_area": has_area,
            "r_gross_wall": r_gross_wall if has_area else 0.0,
            "r_skirting": r_skirting if has_area else 0.0,
        })

    label = lvl.get("name") or f"Level {lvl_idx + 1}"
    height = _resolve_room_height_m({}, lvl, global_ceiling_height_m, use_standard_11ft_default)
    if (
        global_ceiling_height_m is None
        and use_standard_11ft_default
        and lvl.get("wall_height_source") != "stated"
        and abs(
            float(lvl.get("wall_height") or PARSER_FALLBACK_WALL_HEIGHT_M)
            - PARSER_FALLBACK_WALL_HEIGHT_M
        )
        < 0.05
    ):
        warnings.append(
            f"{label}: the drawing states no ceiling height; {DEFAULT_WALL_HEIGHT_M} m was assumed."
        )

    # The exterior outline: the bounding box of the built rooms, or of the walls when the
    # level has walls but no usable rooms.
    width, depth = _box_dims_m(built_points)
    if built_area <= 0.0 and walls:
        warnings.append(
            f"{label}: no usable rooms were found; areas were estimated from the wall outline."
        )
        wall_points = [
            (float(pt[0]) * unit_scale, float(pt[1]) * unit_scale)
            for w in walls
            for pt in (w["start"], w["end"])
        ]
        width, depth = _box_dims_m(wall_points)
        built_area = width * depth
        total_wall_len = sum(
            math.hypot(
                (float(w["end"][0]) - float(w["start"][0])) * unit_scale,
                (float(w["end"][1]) - float(w["start"][1])) * unit_scale,
            )
            for w in walls
        )
        gross_wall_area = total_wall_len * height
        # No rooms, so no room perimeters: the level has floor tiles but no skirting.
        skirting_area = 0.0

    opening_facts: list[OpeningFact] = []
    for op in openings:
        op_type = str(op.get("type", "")).lower()
        if op_type in ("door", "window"):
            opening_facts.append(
                OpeningFact(
                    type=op_type,
                    width=_opening_size_m(op.get("width"), unit_scale),
                    height=_opening_size_m(op.get("height"), unit_scale),
                )
            )
    doors = sum(1 for o in opening_facts if o.type == "door")
    windows = sum(1 for o in opening_facts if o.type == "window")
    openings_area = (doors * DOOR_OPENING_AREA_M2) + (windows * WINDOW_OPENING_AREA_M2)

    net_wall_area = max(gross_wall_area - openings_area, MIN_NET_WALL_RATIO * gross_wall_area)
    if gross_wall_area > 0 and openings_area > (1.0 - MIN_NET_WALL_RATIO) * gross_wall_area:
        warnings.append(
            f"{label}: openings exceed {int((1.0 - MIN_NET_WALL_RATIO) * 100)}% of the wall area; "
            "the net wall area was held at the minimum."
        )

    return {
        "label": label,
        "records": records,
        "built_area": built_area,
        "gross_wall_area": gross_wall_area,
        "skirting_area": skirting_area,
        "openings_area": openings_area,
        "net_wall_area": net_wall_area,
        "height": height,
        "width": width,
        "depth": depth,
        "all_rooms_box": _box_dims_m(all_points),
        "openings": opening_facts,
        "doors": doors,
        "windows": windows,
        "columns": len(lvl.get("columns", [])),
    }


def _derived_summary(p: Primitives) -> dict[str, Any]:
    """The derived quantities of spec section 3, for display and checking."""

    def r(value: float) -> float:
        return round(value, 4)

    return {
        "A_built": r(p.a_built), "A_in": r(p.a_in), "A_ground": r(p.a_ground),
        "A_netwall": r(p.a_netwall), "A_netwall_0": r(p.a_netwall_0),
        "N_door": p.n_door, "N_win": p.n_win, "L": p.L,
        "A_bath": r(p.a_bath), "P_bath": r(p.p_bath), "N_bath": p.n_bath, "N_shower": p.n_shower,
        "A_kit": r(p.a_kit), "P_kit": r(p.p_kit), "N_kit": p.n_kit,
        "A_lau": r(p.a_lau), "P_lau": r(p.p_lau), "N_lau": p.n_lau,
        "A_wet": r(p.a_wet), "P_wet": r(p.p_wet), "A_dry": r(p.a_dry),
        "N_bed": p.n_bed, "N_liv": p.n_liv, "N_din": p.n_din, "N_ac": p.n_ac, "N_wh": p.n_wh,
        "P_ext": [r(v) for v in p.p_ext], "roof_level": p.roof_level,
        "A_roof": r(p.a_roof), "P_roof": r(p.p_roof), "d_roof": r(p.d_roof),
        "G_ext": r(p.g_ext), "A_ext": r(p.a_ext), "A_int": r(p.a_int),
        "A_plinth": r(p.a_plinth), "A_parapet": r(p.a_parapet), "A_masonry": r(p.a_masonry),
        "T_wall": r(p.t_wall), "T_floor": r(p.t_floor),
        "A_gyp_wall": r(p.a_gyp_wall), "A_cem": r(p.a_cem),
        "s_gyp": round(p.s_gyp, 6), "s_cem": round(p.s_cem, 6),
        "E_net": r(p.e_net), "V_dry": r(p.v_dry),
        "A_pave": r(p.a_pave), "P_pave": r(p.p_pave), "P_site": r(p.p_site),
        "open_plan_kitchens": p.open_plan_kitchens,
    }


def map_plan_to_materials(
    plan_payload: dict[str, Any],
    tile_pattern: str = "standard",
    tile_size_mm: str = "600x600",
    global_ceiling_height_m: float | None = None,
    use_standard_11ft_default: bool = True,
    false_ceiling_share: float = 1.0,
    plot_perimeter_m: float | None = None,
) -> dict[str, Any]:
    """
    Task 2 Primary Entrypoint: PlanJSON -> the bill of quantities.

    Follows docs/materials_formula_spec.md:
      - `items`: every row of the bill (59 items, 64 rows), at project scope.
      - The seven core materials (items 1 to 7) are also given per level and per room:
          Project-Wide level (`materials` & `materials_by_key`)
          Floor-Wise level (`level_summaries[i]["materials"]` & `materials_by_key`)
          Room-Wise level (`room_breakdown[i]["materials"]` & `materials_by_key`)

    `false_ceiling_share` (f_fc, 0 to 1) is the share of the dry indoor area that gets a
    false ceiling. `plot_perimeter_m`, when given, is used for the site hoarding.
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
    tile_a_mm, tile_b_mm = _tile_dims_mm(tile_size_mm)
    single_tile_area_m2 = tile_a_mm * tile_b_mm / 1_000_000.0

    num_levels = len(levels)
    warnings: list[str] = [str(w) for w in (plan.get("warnings") or []) if isinstance(w, str)]

    # ---- Pass 1: measure every level, in the order the plan lists them.
    measured: list[dict[str, Any]] = []
    rooms_seen = 0
    for lvl_idx, lvl in enumerate(levels):
        level = _measure_level(
            lvl, lvl_idx, unit_scale, global_ceiling_height_m, use_standard_11ft_default,
            warnings, rooms_seen,
        )
        rooms_seen += len(level["records"])
        measured.append(level)

    # ---- The plan's derived quantities (spec section 3), computed once.
    site_width, site_depth = measured[0]["all_rooms_box"]
    building_type = str(plan.get("building_type") or "villa").lower().strip()
    facts = PlanFacts(
        levels=tuple(
            LevelFact(
                built_area=level["built_area"],
                width=level["width"],
                depth=level["depth"],
                height=level["height"],
            )
            for level in measured
        ),
        rooms=tuple(
            RoomFact(
                name=rec["name"],
                kind=rec["kind"],
                area=rec["area_m2"],
                perimeter=rec["perim_m"],
                boq_type=rec["boq_type"],
                level=lvl_idx,
            )
            for lvl_idx, level in enumerate(measured)
            for rec in level["records"]
            if rec["has_area"]
        ),
        openings=tuple(o for level in measured for o in level["openings"]),
        a_netwall=sum(level["net_wall_area"] for level in measured),
        a_netwall_0=measured[0]["net_wall_area"],
        site_width=site_width,
        site_depth=site_depth,
        building_type=building_type,
        f_fc=min(max(float(false_ceiling_share), 0.0), 1.0),
        plot_perimeter=(
            float(plot_perimeter_m) if plot_perimeter_m and plot_perimeter_m > 0 else None
        ),
        tile_a_mm=tile_a_mm,
        tile_b_mm=tile_b_mm,
        tile_waste=w_pattern,
    )
    p = derive_primitives(facts)

    def scope(**areas: Any) -> dict[str, dict[str, Any]]:
        return _compute_7_materials_for_scope(
            w_pattern=w_pattern,
            single_tile_area_m2=single_tile_area_m2,
            tile_size_mm=tile_size_mm,
            pattern_key=pattern_key,
            s_gyp=p.s_gyp,
            s_cem=p.s_cem,
            **areas,
        )

    # ---- Pass 2: the seven core materials per room and per level.
    level_summaries: list[dict[str, Any]] = []
    room_breakdown: list[dict[str, Any]] = []
    all_built_room_ids: list[str] = []
    built_rooms_count = 0

    for lvl_idx, (lvl, level) in enumerate(zip(levels, measured, strict=True)):
        lvl_built_area = level["built_area"]
        lvl_gross_wall_area = level["gross_wall_area"]
        lvl_net_wall_area = level["net_wall_area"]
        # The plinth belongs to the ground level; the top level carries the parapet.
        lvl_plinth_wall = p.a_plinth if lvl_idx == 0 else 0.0
        lvl_parapet_wall = p.a_parapet if lvl_idx == num_levels - 1 else 0.0
        lvl_ground_steel_area = lvl_built_area if lvl_idx == 0 else 0.0
        lvl_built_room_ids: list[str] = []

        for rec in level["records"]:
            r = rec["raw_room"]
            r_id = rec["id"]
            if rec["counts_as_built"]:
                lvl_built_room_ids.append(r_id)
                all_built_room_ids.append(r_id)
                built_rooms_count += 1
            if rec["counts_as_built"] and lvl_gross_wall_area > 0 and lvl_built_area > 0:
                wall_share = rec["r_gross_wall"] / lvl_gross_wall_area
                area_share = rec["area_m2"] / lvl_built_area
                r_net_wall = lvl_net_wall_area * wall_share
                room_mats_by_key = scope(
                    a_built_m2=rec["area_m2"],
                    a_ground_share_m2=lvl_ground_steel_area * area_share,
                    a_net_wall_m2=r_net_wall,
                    a_plinth_wall_m2=lvl_plinth_wall * wall_share,
                    a_parapet_wall_m2=lvl_parapet_wall * area_share,
                    a_skirting_m2=rec["r_skirting"],
                    scope_room_ids=[r_id],
                )
            else:
                r_net_wall = 0.0
                room_mats_by_key = scope(
                    a_built_m2=0.0,
                    a_ground_share_m2=0.0,
                    a_net_wall_m2=0.0,
                    a_plinth_wall_m2=0.0,
                    a_parapet_wall_m2=0.0,
                    a_skirting_m2=0.0,
                    scope_room_ids=[r_id],
                )

            room_breakdown.append({
                "level_index": lvl_idx,
                "id": r_id,
                "name": r.get("name", "Room"),
                "kind": rec["kind"],
                "boq_type": rec["boq_type"],
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

        lvl_mats_by_key = scope(
            a_built_m2=lvl_built_area,
            a_ground_share_m2=lvl_ground_steel_area,
            a_net_wall_m2=lvl_net_wall_area,
            a_plinth_wall_m2=lvl_plinth_wall,
            a_parapet_wall_m2=lvl_parapet_wall,
            a_skirting_m2=level["skirting_area"],
            scope_room_ids=lvl_built_room_ids,
        )

        level_summaries.append({
            "level_index": lvl_idx,
            "level_name": (
                f"Level {lvl_idx + 1}"
                if num_levels > 1
                else (plan.get("subject") or "Ground Floor")
            ),
            "elevation_m": float(lvl.get("elevation", 0.0)),
            "built_area_m2": round(lvl_built_area, 2),
            "built_area_sqft": round(lvl_built_area * 10.7639, 2),
            "gross_wall_area_m2": round(lvl_gross_wall_area, 2),
            "openings_area_m2": round(level["openings_area"], 2),
            "net_wall_area_m2": round(lvl_net_wall_area, 2),
            "plinth_wall_area_m2": round(lvl_plinth_wall, 2),
            "parapet_wall_area_m2": round(lvl_parapet_wall, 2),
            "exterior_perimeter_m": round(p.p_ext[lvl_idx], 2),
            "wall_height_m": level["height"],
            "doors_count": level["doors"],
            "windows_count": level["windows"],
            "columns_count": level["columns"],
            "materials": list(lvl_mats_by_key.values()),
            "materials_by_key": lvl_mats_by_key,
        })

    # ---- Project totals, from project-level quantities (never by adding up rooms).
    project_materials_by_key = scope(
        a_built_m2=p.a_built,
        a_ground_share_m2=p.a_ground,
        a_net_wall_m2=p.a_netwall,
        a_plinth_wall_m2=p.a_plinth,
        a_parapet_wall_m2=p.a_parapet,
        a_skirting_m2=SKIRTING_HEIGHT_M * p.sum_p_built,
        scope_room_ids=all_built_room_ids,
    )
    v_wet_total = p.a_built * SLAB_THICKNESS_M * RCC_STRUCTURAL_MULTIPLIER

    warnings.extend(calculation_warnings(p, facts))
    seen_warnings: set = set()
    warnings = [w for w in warnings if not (w in seen_warnings or seen_warnings.add(w))]

    return {
        "project_metadata": {
            "project_title": plan.get("project_title") or "NA",
            "subject": plan.get("subject") or "NA",
            "client": plan.get("client") or "NA",
            "architect": plan.get("architect") or "NA",
            "units": "m",
            "scale_source": plan.get("scale_source", "dimension_label"),
            "levels_count": num_levels,
            "building_type": plan.get("building_type") or "other",
            "schema_version": plan.get("schema_version") or "1.0",
        },
        "geometry_summary": {
            "a_ground_m2": round(p.a_ground, 2),
            "a_ground_sqft": round(p.a_ground * 10.7639, 2),
            "a_built_total_m2": round(p.a_built, 2),
            "a_built_total_sqft": round(p.a_built * 10.7639, 2),
            "a_net_wall_m2": round(p.a_netwall, 2),
            "a_plinth_wall_m2": round(p.a_plinth, 2),
            "a_parapet_wall_m2": round(p.a_parapet, 2),
            "a_total_masonry_m2": round(p.a_masonry, 2),
            "a_exterior_wall_m2": round(p.a_ext, 2),
            "a_interior_wall_m2": round(p.a_int, 2),
            "a_gypsum_wall_faces_m2": round(p.a_gyp_wall, 2),
            "a_cement_plaster_m2": round(p.a_cem, 2),
            "a_roof_m2": round(p.a_roof, 2),
            "v_wet_concrete_m3": round(v_wet_total, 2),
            "v_dry_concrete_m3": round(p.v_dry, 2),
            "total_doors": p.n_door,
            "total_windows": p.n_win,
            "total_columns": sum(level["columns"] for level in measured),
            "levels_count": num_levels,
            "rooms_count": built_rooms_count,
            "bathrooms_count": p.n_bath,
            "kitchens_count": p.n_kit,
            "bedrooms_count": p.n_bed,
        },
        "derived_quantities": _derived_summary(p),
        "items": build_boq_rows(compute_items(p, facts), project_materials_by_key),
        "warnings": warnings,
        "materials": list(project_materials_by_key.values()),
        "materials_by_key": project_materials_by_key,
        "level_summaries": level_summaries,
        "room_breakdown": room_breakdown,
    }


# Aliases for downstream imports
calculate_raw_materials_from_plan = map_plan_to_materials
generate_material_sheet = map_plan_to_materials
