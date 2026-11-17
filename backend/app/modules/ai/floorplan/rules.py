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


# Minimum clear size per room type (measured on wall centre lines).
MIN_ROOM: dict[str, MinSize] = {
    "master_bedroom": MinSize(12.0, 300),
    "bedroom": MinSize(9.5, 270),
    "living": MinSize(12.0, 300),
    "family_hall": MinSize(12.0, 300),
    "dining": MinSize(7.5, 240),
    "kitchen": MinSize(5.5, 180),
    "bath": MinSize(2.8, 120),
    "toilet": MinSize(1.2, 90),
    "dress": MinSize(2.5, 120),
    "store": MinSize(1.5, 100),
    "maid_room": MinSize(6.0, 210),
    "study": MinSize(6.0, 210),
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
    {"lobby", "passage", "garden", "courtyard", "parking", "balcony", "shaft"}
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
ROOM_SCALE_UP_MAX = 1.4  # rooms may grow up to this factor to use a large plot
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
