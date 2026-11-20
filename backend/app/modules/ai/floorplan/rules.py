"""Drawing and planning rules for the floor plan generator (one place to tune them).

All lengths are in cm, areas in m2. Values are practical residential minimums; adjust
here only, never inline in pipeline code.
"""

from typing import NamedTuple

WALL_EXTERIOR_CM = 23
WALL_INTERIOR_CM = 12


class MinSize(NamedTuple):
    area_m2: float
    short_side_cm: int


# Minimum size per room type, measured on wall centre lines. Living spaces follow the Dubai
# Building Code K.5.3.1 Table K.2 (10.5 m2 and 3.0 m net, inside the walls): on centre lines
# that is about 3.2 m and 11.5 m2 with the walls' halves (to be confirmed by an engineer).
MIN_ROOM: dict[str, MinSize] = {
    "master_bedroom": MinSize(12.0, 320),
    "bedroom": MinSize(11.5, 320),
    "living": MinSize(12.0, 320),
    "family_hall": MinSize(12.0, 320),
    "dining": MinSize(11.5, 320),
    "kitchen": MinSize(6.0, 200),
    "bath": MinSize(2.8, 120),
    "toilet": MinSize(1.2, 90),
    "dress": MinSize(2.5, 120),
    "store": MinSize(1.5, 100),
    "maid_room": MinSize(6.2, 230),
    "study": MinSize(11.5, 320),
    "lobby": MinSize(0.0, 100),
    "passage": MinSize(0.0, 100),
    "foyer": MinSize(2.5, 120),
    "utility": MinSize(2.0, 120),
    "stair": MinSize(4.5, 100),
    "courtyard": MinSize(6.0, 200),
    "garden": MinSize(0.0, 100),
    "balcony": MinSize(1.5, 100),
    "parking": MinSize(12.5, 250),
    "pool": MinSize(30.0, 420),  # water at least 3 x 6 m plus a walkway around it
    "deck": MinSize(4.0, 180),
    "shaft": MinSize(0.0, 0),
    "majlis": MinSize(11.5, 320),
    "prayer": MinSize(4.0, 180),
    "puja": MinSize(2.5, 150),
    "bar": MinSize(6.0, 210),
    "gym": MinSize(9.0, 270),
    "driver_room": MinSize(6.2, 230),
    "lift": MinSize(2.2, 140),
    "lawn": MinSize(0.0, 100),
    "driveway": MinSize(0.0, 300),
    "dock": MinSize(0.0, 300),
    "other": MinSize(0.0, 0),
}

# Typical comfortable size per room type (m2): fallback targets when the LLM is not
# available, and the starting point before scaling to the plot.
TYPICAL_ROOM_M2: dict[str, float] = {
    "master_bedroom": 16.0,
    "bedroom": 12.5,
    "living": 20.0,
    "family_hall": 18.0,
    "dining": 11.0,
    "kitchen": 9.0,
    "bath": 4.0,
    "toilet": 2.0,
    "dress": 4.0,
    "store": 3.0,
    "maid_room": 8.0,
    "study": 9.0,
    "lobby": 10.0,
    "passage": 6.0,
    "foyer": 5.0,
    "utility": 3.5,
    "stair": 8.0,
    "courtyard": 25.0,
    "garden": 20.0,
    "balcony": 4.0,
    "parking": 15.0,
    "pool": 40.0,
    "deck": 9.0,
    "shaft": 1.0,
    "majlis": 24.0,
    "prayer": 7.0,
    "puja": 5.0,
    "bar": 10.0,
    "gym": 14.0,
    "driver_room": 9.0,
    "lift": 2.8,
    "lawn": 30.0,
    "driveway": 25.0,
    "dock": 30.0,
    "other": 6.0,
}

# Feasibility: minimum room areas plus this share for walls and circulation must fit.
CIRCULATION_FACTOR = 0.18
# Default plot shape when only an area is given (width : depth).
DEFAULT_PLOT_RATIO = (2, 3)
# Share of the plot the program targets when sizing rooms (rest: walls, open space).
PROGRAM_PLOT_SHARE = (0.75, 0.88)

# Openings
DOOR_MIN_WIDTH_CM = 70
OPENING_END_CLEARANCE_CM = 12  # keep openings clear of the perpendicular wall at each end

# Spaces that absorb leftover plot area. Only their minimum size is checked, and they are
# left out of the total-area comparison with the program.
AREA_FLEXIBLE_TYPES = frozenset(
    {"lobby", "passage", "garden", "lawn", "courtyard", "parking", "driveway", "balcony", "shaft"}
)
# Swimming pool: the room is water plus a paved walkway; the walkway is this wide (cm),
# narrower only on a small pool room. Pool and deck targets are capped as a share
# of the plot.
POOL_WALKWAY_CM = (60, 100)
POOL_PLOT_SHARE_MAX = 0.25

# Open areas that must stay a sensible size (max multiple of their program target).
# The garden is the only open area that absorbs all leftover plot space.
OPEN_AREA_CAP: dict[str, float] = {
    "parking": 1.4,
    "courtyard": 1.5,
    "balcony": 1.5,
    "pool": 1.3,
    "deck": 1.5,
}
PARKING_PER_CAR_M2 = (13.5, 18.0)  # one car space incl. door clearance (min, max)
COURTYARD_PLOT_SHARE = (0.05, 0.15)  # courtyard target as a share of the plot
ROOM_SCALE_UP_MAX = 1.4  # rooms may grow up to this factor to use a large plot (no target)
# Largest sensible size (m2) per room type when rooms grow to meet a built-up target;
# types not listed (living, family hall, majlis, dining, bar, gym, circulation) take the rest.
MAX_ROOM_M2: dict[str, float] = {
    "master_bedroom": 45.0,
    "bedroom": 30.0,
    "bath": 12.0,
    "toilet": 5.0,
    "dress": 15.0,
    "kitchen": 30.0,
    "store": 10.0,
    "utility": 12.0,
    "stair": 18.0,
    "maid_room": 14.0,
    "driver_room": 14.0,
    "study": 22.0,
    "foyer": 25.0,
    "prayer": 20.0,
    "puja": 12.0,
    "lift": 6.0,
}
GARDEN_MIN_SPARE = 0.05  # spare plot share above which a garden is added to take it
# Circulation may grow, but only up to this multiple of its target (open areas grow freely).
CIRCULATION_MAX_FACTOR = 1.6
# Leftover gaps become open-to-sky shafts; above this total area the validator warns.
SHAFT_WARN_M2 = 3.0

# Validator tolerances
ROOM_AREA_TOLERANCE = 0.25  # each room within +/-25 % of its program target
TOTAL_AREA_TOLERANCE = 0.15  # sum of rooms within +/-15 % of the program total
MIN_PLOT_COVERAGE = 0.90  # below this, unused plot area is reported as a warning
OVERLAP_EPS_CM2 = 1.0


# ---------------------------------------------------------------- building model (mm)
# Values from the Dubai Building Code 2021 Part K (docs/pro/2d/RULES.md), to be confirmed
# against the Dubai Building Code by an engineer.
DOOR_HEIGHT_MM = 2100
MAIN_DOOR_HEIGHT_MM = 2400
STAIR_MAX_RISER_MM = 180  # K.5.5.2.3: 100-180 mm
STAIR_MIN_RISER_MM = 100
STAIR_TREAD_MM = 290  # K.5.5.2.3: going at least 280 mm
STAIR_MIN_TREAD_MM = 280
STAIR_MIN_WIDTH_MM = 1000  # K.5.5.2.2
STAIR_HEADROOM_MM = 2300  # K.5.5.2.10
# window height and sill (mm) by room type; openable sill at least 900 mm (K.5.4.2)
WINDOW_SPEC_MM: dict[str, tuple[int, int]] = {
    "default": (1500, 900),
    "bath": (600, 1500),
    "toilet": (600, 1500),
    "utility": (900, 1200),
    "store": (600, 1500),
    "kitchen": (1200, 1050),
}
