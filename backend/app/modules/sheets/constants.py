"""Engineering constants of the material calculator. The one place to recalibrate.

Every factor the quantity formulas use is defined here and nowhere else. `llm_mapper`
imports them all, so `from app.modules.sheets.llm_mapper import X` keeps working.

The concrete, steel and mix constants are calibrated values. Change them only with a
quantity surveyor.
"""

from app.modules.plans.schemas import UNSTATED_WALL_HEIGHT_M

DEFAULT_WALL_HEIGHT_M = 3.35          # 11 ft standard ceiling height (3.35 m)
# What the parser writes into `wall_height` when the drawing states no height.
PARSER_FALLBACK_WALL_HEIGHT_M = UNSTATED_WALL_HEIGHT_M
SHARED_WALL_REDUCTION_FACTOR = 0.72   # Deduplicates shared internal walls across adjacent rooms

DOOR_OPENING_AREA_M2 = 1.89           # Standard 0.9m x 2.1m door opening area
WINDOW_OPENING_AREA_M2 = 1.44         # Standard 1.2m x 1.2m window opening area
MIN_NET_WALL_RATIO = 0.50             # Net wall area floor (at least 50% of gross wall area)

# 25% of ground floor net wall area for substructure plinth masonry
PLINTH_WALL_FACTOR = 0.25
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

# 6. Plaster Constants. The gypsum / cement split of the wall faces is not a constant:
# it is s_gyp / s_cem, computed per plan from the wall model (sheets/primitives.py).
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
# Items 8 to 59 and the derived quantities (docs/materials_formula_spec.md).
# Every number of sections 2 to 4 of the spec is named here and used nowhere else.
# =============================================================================

# --- Derived quantities (section 3)
SHOWER_MIN_BATH_AREA_M2 = 2.5         # a bathroom this large has a shower
OPEN_PLAN_KITCHEN_MAX_M2 = 12.0       # kitchen portion of an open-plan room: min(12, A/3)
AC_AREA_PER_UNIT_M2 = 40.0            # one AC unit per 40 m2 of room
AC_MIN_ROOM_AREA_M2 = 6.0             # smaller rooms get no AC unit
BATH_WALL_TILE_FACTOR = 2.07          # skirting to 2.40 m, 10% off for openings: 2.30 x 0.90
SPLASHBACK_TILE_FACTOR = 0.30         # 0.60 m splashback on half the perimeter

# Two bounding boxes overlap when they share more than this in both directions.
BOX_OVERLAP_MIN_M = 0.05

# --- Default opening sizes when a plan gives none (section 1)
DEFAULT_DOOR_WIDTH_M = 0.90
DEFAULT_DOOR_HEIGHT_M = 2.10
DEFAULT_WINDOW_WIDTH_M = 1.20
DEFAULT_WINDOW_HEIGHT_M = 1.20

# --- Group B: civil, finishing and waterproofing (8 to 23)
ROOF_UPSTAND_M = 0.30                 # roof membrane turned up the parapet
PU_FOAM_WASTE = 1.05
BITUMEN_ROOF_PRIMER_L_PER_M2 = 0.30
BITUMEN_PLINTH_L_PER_M2 = 0.50        # two coats at 0.25 L/m2
FOOTING_SHARE_OF_FOOTPRINT = 0.50     # footings taken as half the footprint
BITUMEN_WASTE = 1.05
SCREED_BASE_THICKNESS_M = 0.05
SCREED_SLOPE_M_PER_M = 0.0025
SCREED_MIN_THICKNESS_M = 0.06
SCREED_MAX_THICKNESS_M = 0.15
SCREED_WASTE = 1.05
WATERPROOF_ROOF_KG_PER_M2 = 1.2
WATERPROOF_WET_KG_PER_M2 = 1.5
WET_AREA_UPSTAND_M = 0.30
SHOWER_WALL_AREA_M2 = 3.0
WATERPROOF_WASTE = 1.05
WALL_TILE_WASTE = 1.10
GROUT_FACTOR = 51.0                   # g = 51 x (a + b) / (a x b): 3 mm joint, 10 mm depth
GROUT_WALL_KG_PER_M2 = 0.255          # the same formula for 300 x 600 wall tiles
GROUT_WASTE = 1.10
SOLVENT_L_PER_M2 = 0.08
THRESHOLD_LENGTH_M = 0.90
WINDOW_SILL_OVERHANG_M = 0.10
STONE_WASTE = 1.05
NICHE_M2_PER_SHOWER = 0.40
NICHE_M2_PER_LIVING_ROOM = 1.50
NICHE_WASTE = 1.10
PAINT_COATS = 2
INTERIOR_PAINT_M2_PER_L = 9.0
PRIMER_M2_PER_L = 10.0
PAINT_WASTE = 1.05
GYPSUM_BOARD_WASTE = 1.10
GYPSUM_BOARD_AREA_M2 = 2.88           # 1.2 x 2.4 m board
EXTERIOR_PLASTER_WASTE = 1.05
EXTERIOR_PAINT_M2_PER_L = 6.5
PAVING_WASTE = 1.05
KERB_SHARE_OF_PERIMETER = 0.75
KERB_WASTE = 1.05
KERB_PIECE_LENGTH_M = 0.915

# --- Group C: architectural components (24 to 31)
AC_UNITS_PER_CANOPY = 2
CURTAIN_WALL_MIN_WIDTH_M = 2.20       # a window this wide is priced as curtain wall
CURTAIN_WALL_DEFAULT_HEIGHT_M = 2.40
GLASS_DOOR_MIN_WIDTH_M = 1.40         # a door this wide is an internal glass door
GATE_SETS = 2

# --- Group D: electrical and HVAC (32 to 43)
CABLE_M_PER_M2 = 14.5
CABLE_WASTE = 1.10
CABLE_COIL_LENGTH_M = 91.4
SOCKETS_MIN_PER_ROOM = 2
SOCKET_SPACING_M = 4.0
KITCHEN_SOCKETS_MIN = 6
KITCHEN_SOCKET_SPACING_M = 2.0
OPEN_PLAN_KITCHEN_SOCKETS = 6
BATH_SOCKETS = 1
LAUNDRY_SOCKETS = 2
CIRCULATION_SOCKET_SPACING_M = 10.0
STORE_SOCKETS = 1
SECOND_SWITCH_MIN_AREA_M2 = 20.0      # a room larger than this gets a second light switch
SOCKETS_PER_CIRCUIT = 6
LIGHTS_PER_CIRCUIT = 10
DEVICES_PER_DISTRIBUTION_BOARD = 3
SPOTLIGHT_AREA_DRY_M2 = 3.0
SPOTLIGHT_AREA_WET_M2 = 2.0
SPOTLIGHT_AREA_SEMI_OPEN_M2 = 6.0
BATH_LIGHT_AREA_M2 = 2.0
LED_STRIP_SHARE_OF_PERIMETER = 0.75
LED_STRIP_M_PER_BATH = 2.5
LED_STRIP_WASTE = 1.05

# --- Group E: plumbing and sanitary (44 to 57)
AC_DRAIN_M_PER_UNIT = 8.5
AC_DRAIN_WASTE = 1.05
ANGLE_VALVES_PER_BATH = 6
ANGLE_VALVES_PER_KITCHEN = 5
ANGLE_VALVES_PER_LAUNDRY = 1
ISOLATION_VALVES_PER_WET_ROOM = 2
ISOLATION_VALVES_MAIN = 4
HOSE_BIBS = 2
PUMP_SETS = 2
WATER_TANKS = 2
TANK_SIZE_STEP_L = 500
GROUND_TANK_L_PER_BEDROOM = 600
ROOF_TANK_L_PER_BEDROOM = 400
ROOF_AREA_PER_OUTLET_M2 = 60.0
ROOF_OUTLETS_MIN = 2
MANHOLE_SPACING_M = 12.0
MANHOLES_MIN = 4

# --- Group F: site setup (58, 59)
HOARDING_OFFSET_M = 24.0              # hoarding stands 3 m off the building on every side
HOARDING_WASTE = 1.05
