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
