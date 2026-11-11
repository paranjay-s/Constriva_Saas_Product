"""
=============================================================================
Construtiva Precision Architectural PlanJSON Generator (Revision 3)
=============================================================================
Full architectural compliance with all user review criteria:
1. Left column heights re-measured from drawing (wash top wall ~7.05, recessed
   bed ~7.05-10.5, common toilet ~10.5-12.2, master bed south ~12.2, left rear ~15.75,
   attached toilet ~13.25-15.75).
2. Deleted w_rear_jog_mid (left rear and right bed rear wall level at y=15.75).
3. Top-right block fixed: Passage (x ~8.45-9.5, y ~8.0-12.4), Wash (x ~8.45-11.12,
   y ~12.4-14.15), Toilets (x ~8.45-11.12, y ~14.15-16.65, each 1.22m x 2.44m),
   Store (x ~9.5-11.12, y ~8.0-9.3), Open shaft (x ~9.5-11.12, y ~9.3-12.4).
4. Missing elements added: East wall of 9'x15' bed at x=8.45 (y ~11.13-15.75),
   extended spine wall to y=15.75, filled gap between kitchen and drawing hall,
   assigned lobby/dress strip between common toilet and passage, recess jog
   thickness set to 0.12m.
5. Windows clamped and properly positioned (13 total), including passage-shaft window.
6. Added columns array for all 24 blue structural columns.
7. Added doors with inferred: true.
8. Added explicit kind fields on all walls and rooms.
9. Computed confidence derived from validate.py suite.
=============================================================================
"""

import sys
import json
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.modules.plans.schemas import PlanJSON
from app.modules.parsing.validate import (
    compute_plan_confidence,
    validate_bounding_box,
    validate_y_axis_orientation,
    validate_room_dimensions_vs_labels,
    validate_l_shaped_rooms,
    validate_overlaps_and_gaps,
    validate_wall_connectivity,
    validate_openings,
    validate_room_wall_coverage,
)


def generate_precision_plan() -> dict:
    # -------------------------------------------------------------------------
    # ROOMS (23 exact spaces with verified geometry and explicit kind)
    # -------------------------------------------------------------------------
    rooms = [
        # Front Strip (Y: 0.0 -> 2.44m)
        {
            "id": "room_staircase",
            "name": "Staircase (UP/DN)",
            "kind": "semi_open",
            "polygon": [[0.0, 0.0], [4.11, 0.0], [4.11, 2.44], [0.0, 2.44]],
        },
        {
            "id": "room_verandah",
            "name": "VERANDAH 12'6\" X 8'",
            "kind": "semi_open",
            "polygon": [[4.11, 0.0], [7.87, 0.0], [7.87, 2.44], [4.11, 2.44]],
        },
        {
            "id": "room_lawn",
            "name": "LAWN 10'8\" X 8'",
            "kind": "outdoor",
            "polygon": [[7.87, 0.0], [11.12, 0.0], [11.12, 2.44], [7.87, 2.44]],
        },

        # Left Wing
        {
            "id": "room_kitchen_left",
            "name": "KIT. 6'9\" X 10'",
            "kind": "indoor",
            "polygon": [[0.0, 2.44], [2.06, 2.44], [2.06, 5.49], [0.0, 5.49]],
        },
        {
            "id": "room_wash_left",
            "name": "WASH 7' X 4'",
            "kind": "indoor",
            "polygon": [[0.0, 5.49], [2.06, 5.49], [2.06, 7.05], [0.0, 7.05]],
        },
        {
            "id": "room_drg_dn_left",
            "name": "DRG./DN. 11' X 14'",
            "kind": "indoor",
            "polygon": [[2.06, 2.44], [5.41, 2.44], [5.41, 7.05], [2.06, 7.05]],
        },
        {
            "id": "room_bed_mid_left",
            "name": "BED. 9'8\" X 11' (Recessed)",
            "kind": "indoor",
            "polygon": [[1.44, 7.05], [4.39, 7.05], [4.39, 10.50], [1.44, 10.50]],
        },
        {
            "id": "room_passage_left",
            "name": "PASSAGE 3'4\" WD.",
            "kind": "indoor",
            "polygon": [[4.39, 7.05], [5.41, 7.05], [5.41, 12.20], [4.39, 12.20]],
        },
        {
            "id": "room_toilet_common_left",
            "name": "TOI. 9' X 5'",
            "kind": "indoor",
            "polygon": [[0.0, 10.50], [2.74, 10.50], [2.74, 12.20], [0.0, 12.20]],
        },
        {
            "id": "room_lobby_dress_left",
            "name": "PASSAGE / DRESS 5'5\" X 5'6\"",
            "kind": "indoor",
            "polygon": [[2.74, 10.50], [4.39, 10.50], [4.39, 12.20], [2.74, 12.20]],
        },
        # L-SHAPED Master Bedroom wrapping under attached toilet to spine wall
        {
            "id": "room_bed_master_left",
            "name": "BED. 12'8\" X 11' (L-Shaped)",
            "kind": "indoor",
            "polygon": [
                [0.0, 12.20],
                [5.41, 12.20],
                [5.41, 13.25],
                [3.86, 13.25],
                [3.86, 15.75],
                [0.0, 15.75],
            ],
        },
        {
            "id": "room_toilet_attached_left",
            "name": "TOI. 4'9\" X 8'",
            "kind": "indoor",
            "polygon": [[3.86, 13.25], [5.41, 13.25], [5.41, 15.75], [3.86, 15.75]],
        },

        # Right Wing
        {
            "id": "room_kitchen_right",
            "name": "KIT. 7'6\" X 9'6\"",
            "kind": "indoor",
            "polygon": [[5.41, 2.44], [7.70, 2.44], [7.70, 5.34], [5.41, 5.34]],
        },
        {
            "id": "room_dining_right",
            "name": "DIN. 9' X 8'",
            "kind": "indoor",
            "polygon": [[5.41, 5.34], [8.45, 5.34], [8.45, 8.00], [5.41, 8.00]],
        },
        {
            "id": "room_drg_right",
            "name": "DRG. 10' X 17'6\"",
            "kind": "indoor",
            "polygon": [
                [7.70, 2.44],
                [11.12, 2.44],
                [11.12, 8.00],
                [8.45, 8.00],
                [8.45, 5.34],
                [7.70, 5.34],
            ],
        },
        {
            "id": "room_bed_mid_right",
            "name": "BED. 9' X 11'",
            "kind": "indoor",
            "polygon": [[5.41, 8.00], [8.45, 8.00], [8.45, 11.13], [5.41, 11.13]],
        },
        {
            "id": "room_passage_right",
            "name": "PASSAGE 3'4\" WD.",
            "kind": "indoor",
            "polygon": [[8.45, 8.00], [9.50, 8.00], [9.50, 12.40], [8.45, 12.40]],
        },
        {
            "id": "room_store",
            "name": "STORE 4'8\" X 4'",
            "kind": "indoor",
            "polygon": [[9.50, 8.00], [11.12, 8.00], [11.12, 9.30], [9.50, 9.30]],
        },
        {
            "id": "room_open_shaft",
            "name": "OPEN 4'8\" X 9'",
            "kind": "void",
            "polygon": [[9.50, 9.30], [11.12, 9.30], [11.12, 12.40], [9.50, 12.40]],
        },
        {
            "id": "room_bed_master_right",
            "name": "BED. 9' X 15'",
            "kind": "indoor",
            "polygon": [[5.41, 11.13], [8.45, 11.13], [8.45, 15.75], [5.41, 15.75]],
        },
        {
            "id": "room_wash_right",
            "name": "WASH 8'6\" X 6'",
            "kind": "indoor",
            "polygon": [[8.45, 12.40], [11.12, 12.40], [11.12, 14.15], [8.45, 14.15]],
        },
        {
            "id": "room_toilet_top_right_1",
            "name": "TOI. 4' X 8' (1)",
            "kind": "indoor",
            "polygon": [[8.45, 14.15], [9.78, 14.15], [9.78, 16.65], [8.45, 16.65]],
        },
        {
            "id": "room_toilet_top_right_2",
            "name": "TOI. 4' X 8' (2)",
            "kind": "indoor",
            "polygon": [[9.78, 14.15], [11.12, 14.15], [11.12, 16.65], [9.78, 16.65]],
        },
    ]

    # -------------------------------------------------------------------------
    # WALLS (Perimeter exterior & interior partitions with explicit kinds)
    # -------------------------------------------------------------------------
    walls = [
        # Front Boundary
        {"id": "w_front_boundary", "start": [0.0, 0.0], "end": [11.12, 0.0], "thickness": 0.23, "kind": "exterior"},
        {"id": "w_front_divider_stair", "start": [4.11, 0.0], "end": [4.11, 2.44], "thickness": 0.12, "kind": "interior"},
        {"id": "w_front_divider_lawn", "start": [7.87, 0.0], "end": [7.87, 2.44], "thickness": 0.12, "kind": "interior"},
        {"id": "w_front_plinth", "start": [0.0, 2.44], "end": [11.12, 2.44], "thickness": 0.23, "kind": "exterior"},

        # Left Boundary & Recess
        {"id": "w_left_ext_lower", "start": [0.0, 0.0], "end": [0.0, 7.05], "thickness": 0.23, "kind": "exterior"},
        {"id": "w_recess_jog_in", "start": [0.0, 7.05], "end": [1.44, 7.05], "thickness": 0.12, "kind": "exterior"},
        {"id": "w_recess_west_wall", "start": [1.44, 7.05], "end": [1.44, 10.50], "thickness": 0.23, "kind": "exterior"},
        {"id": "w_recess_jog_out", "start": [1.44, 10.50], "end": [0.0, 10.50], "thickness": 0.12, "kind": "exterior"},
        {"id": "w_left_ext_upper", "start": [0.0, 10.50], "end": [0.0, 15.75], "thickness": 0.23, "kind": "exterior"},

        # Right Boundary (Straight 0 to 16.65m)
        {"id": "w_right_ext", "start": [11.12, 0.0], "end": [11.12, 16.65], "thickness": 0.23, "kind": "exterior"},

        # Rear Boundary Steps (left rear & right bed rear flush at y=15.75)
        {"id": "w_rear_master_left", "start": [0.0, 15.75], "end": [5.41, 15.75], "thickness": 0.23, "kind": "exterior"},
        {"id": "w_rear_bed_mid_right", "start": [5.41, 15.75], "end": [8.45, 15.75], "thickness": 0.23, "kind": "exterior"},
        {"id": "w_rear_jog_right", "start": [8.45, 15.75], "end": [8.45, 16.65], "thickness": 0.23, "kind": "exterior"},
        {"id": "w_rear_toilets_top_right", "start": [8.45, 16.65], "end": [11.12, 16.65], "thickness": 0.23, "kind": "exterior"},

        # Central Spine Wall (extended to new rear wall at 15.75)
        {"id": "w_spine_main", "start": [5.41, 2.44], "end": [5.41, 15.75], "thickness": 0.23, "kind": "interior"},

        # Left Wing Internal Walls
        {"id": "w_kit_left_north", "start": [0.0, 5.49], "end": [2.06, 5.49], "thickness": 0.12, "kind": "interior"},
        {"id": "w_kit_left_east", "start": [2.06, 2.44], "end": [2.06, 7.05], "thickness": 0.12, "kind": "interior"},
        {"id": "w_wash_left_north", "start": [0.0, 7.05], "end": [2.06, 7.05], "thickness": 0.12, "kind": "interior"},
        {"id": "w_drg_left_north", "start": [2.06, 7.05], "end": [5.41, 7.05], "thickness": 0.12, "kind": "interior"},
        {"id": "w_bed_mid_left_north", "start": [1.44, 10.50], "end": [4.39, 10.50], "thickness": 0.12, "kind": "interior"},
        {"id": "w_bed_mid_left_east", "start": [4.39, 7.05], "end": [4.39, 10.50], "thickness": 0.12, "kind": "interior"},
        {"id": "w_toi_common_east", "start": [2.74, 10.50], "end": [2.74, 12.20], "thickness": 0.12, "kind": "interior"},
        {"id": "w_lobby_dress_east", "start": [4.39, 10.50], "end": [4.39, 12.20], "thickness": 0.12, "kind": "interior"},
        {"id": "w_master_bed_south", "start": [0.0, 12.20], "end": [5.41, 12.20], "thickness": 0.12, "kind": "interior"},
        {"id": "w_toi_attached_west", "start": [3.86, 13.25], "end": [3.86, 15.75], "thickness": 0.12, "kind": "interior"},
        {"id": "w_toi_attached_south", "start": [3.86, 13.25], "end": [5.41, 13.25], "thickness": 0.12, "kind": "interior"},

        # Right Wing Internal Walls
        {"id": "w_kit_right_north", "start": [5.41, 5.34], "end": [7.70, 5.34], "thickness": 0.12, "kind": "interior"},
        {"id": "w_kit_right_east", "start": [7.70, 2.44], "end": [7.70, 5.34], "thickness": 0.12, "kind": "interior"},
        {"id": "w_din_south", "start": [7.70, 5.34], "end": [8.45, 5.34], "thickness": 0.12, "kind": "interior"},
        {"id": "w_drg_din_cased_opening", "start": [8.45, 5.34], "end": [8.45, 8.00], "thickness": 0.12, "kind": "interior", "inferred": True},
        {"id": "w_drg_din_north", "start": [5.41, 8.00], "end": [11.12, 8.00], "thickness": 0.12, "kind": "interior"},
        {"id": "w_bed_mid_right_north", "start": [5.41, 11.13], "end": [8.45, 11.13], "thickness": 0.12, "kind": "interior"},
        {"id": "w_bed_mid_right_east", "start": [8.45, 8.00], "end": [8.45, 11.13], "thickness": 0.12, "kind": "interior"},
        {"id": "w_bed_master_right_east", "start": [8.45, 11.13], "end": [8.45, 15.75], "thickness": 0.12, "kind": "interior"},
        {"id": "w_store_north", "start": [9.50, 9.30], "end": [11.12, 9.30], "thickness": 0.12, "kind": "interior"},
        {"id": "w_shaft_north", "start": [9.50, 12.40], "end": [11.12, 12.40], "thickness": 0.12, "kind": "interior"},
        {"id": "w_passage_right_east", "start": [9.50, 8.00], "end": [9.50, 12.40], "thickness": 0.12, "kind": "interior"},
        {"id": "w_passage_wash_divider", "start": [8.45, 12.40], "end": [9.50, 12.40], "thickness": 0.12, "kind": "interior", "inferred": True},
        {"id": "w_wash_right_north", "start": [8.45, 14.15], "end": [11.12, 14.15], "thickness": 0.12, "kind": "interior"},
        {"id": "w_toilets_divider_right", "start": [9.78, 14.15], "end": [9.78, 16.65], "thickness": 0.12, "kind": "interior"},
    ]

    # -------------------------------------------------------------------------
    # WINDOWS (Exact 13 architectural windows correctly clamped & positioned)
    # -------------------------------------------------------------------------
    windows = [
        # Front windows (Kitchen left, DRG/DN left, Kitchen right, DRG right)
        {"id": "win_kit_left_front", "wall_id": "w_front_plinth", "type": "window", "offset": 0.5, "width": 1.2, "height": 1.2, "sill": 0.9, "inferred": False},
        {"id": "win_drg_left_front", "wall_id": "w_front_plinth", "type": "window", "offset": 2.7, "width": 1.3, "height": 1.4, "sill": 0.9, "inferred": False},
        {"id": "win_kit_right_front", "wall_id": "w_front_plinth", "type": "window", "offset": 5.9, "width": 1.2, "height": 1.2, "sill": 0.9, "inferred": False},
        {"id": "win_drg_right_front", "wall_id": "w_front_plinth", "type": "window", "offset": 8.8, "width": 1.3, "height": 1.5, "sill": 0.9, "inferred": False},

        # Recessed west window of bed 9'8"x11'
        {"id": "win_bed_mid_left_recess", "wall_id": "w_recess_west_wall", "type": "window", "offset": 0.8, "width": 1.7, "height": 1.4, "sill": 0.9, "inferred": False},

        # Toilet 9'x5' south ventilator (facing into open recess slot)
        {"id": "win_toi_common_south", "wall_id": "w_recess_jog_out", "type": "window", "offset": 0.3, "width": 0.8, "height": 0.6, "sill": 1.8, "inferred": False},

        # Rear windows of master bed and attached toilet
        {"id": "win_master_left_rear", "wall_id": "w_rear_master_left", "type": "window", "offset": 1.2, "width": 1.5, "height": 1.4, "sill": 0.9, "inferred": False},
        {"id": "win_toi_attached_rear", "wall_id": "w_rear_master_left", "type": "window", "offset": 4.2, "width": 0.8, "height": 0.6, "sill": 1.8, "inferred": False},

        # Window between Bed 9'x11' and open shaft
        {"id": "win_bed_mid_right_shaft", "wall_id": "w_bed_mid_right_east", "type": "window", "offset": 1.0, "width": 1.2, "height": 1.2, "sill": 0.9, "inferred": False},

        # Right master bed rear window (clamped)
        {"id": "win_bed_master_right_rear", "wall_id": "w_rear_bed_mid_right", "type": "window", "offset": 0.8, "width": 1.3, "height": 1.4, "sill": 0.9, "inferred": False},

        # Window between Passage and Open Shaft at x≈9.50
        {"id": "win_passage_shaft", "wall_id": "w_passage_right_east", "type": "window", "offset": 1.8, "width": 1.0, "height": 1.2, "sill": 0.9, "inferred": False},

        # Wash right south window facing into open shaft
        {"id": "win_wash_south", "wall_id": "w_shaft_north", "type": "window", "offset": 0.2, "width": 1.2, "height": 1.2, "sill": 0.9, "inferred": False},

        # Top-right toilets rear ventilators
        {"id": "win_toi_top_right_vents", "wall_id": "w_rear_toilets_top_right", "type": "window", "offset": 0.5, "width": 1.5, "height": 0.6, "sill": 1.8, "inferred": False},
    ]

    # -------------------------------------------------------------------------
    # DOORS (Inferred access points tagged with inferred: true)
    # -------------------------------------------------------------------------
    doors = [
        {"id": "op_door_verandah_drg", "wall_id": "w_front_plinth", "type": "door", "offset": 4.5, "width": 1.0, "height": 2.1, "sill": 0.0, "inferred": True},
        {"id": "op_door_kit_left", "wall_id": "w_kit_left_east", "type": "door", "offset": 1.2, "width": 0.9, "height": 2.1, "sill": 0.0, "inferred": True},
        {"id": "op_door_wash_left", "wall_id": "w_kit_left_north", "type": "door", "offset": 0.5, "width": 0.8, "height": 2.1, "sill": 0.0, "inferred": True},
        {"id": "op_door_bed_mid_left", "wall_id": "w_bed_mid_left_east", "type": "door", "offset": 1.2, "width": 0.9, "height": 2.1, "sill": 0.0, "inferred": True},
        {"id": "op_door_toi_common", "wall_id": "w_toi_common_east", "type": "door", "offset": 0.4, "width": 0.8, "height": 2.1, "sill": 0.0, "inferred": True},
        {"id": "op_door_master_left", "wall_id": "w_master_bed_south", "type": "door", "offset": 4.0, "width": 1.0, "height": 2.1, "sill": 0.0, "inferred": True},
        {"id": "op_door_toi_attached", "wall_id": "w_toi_attached_south", "type": "door", "offset": 0.3, "width": 0.8, "height": 2.1, "sill": 0.0, "inferred": True},
        {"id": "op_door_kit_right", "wall_id": "w_kit_right_east", "type": "door", "offset": 1.0, "width": 0.9, "height": 2.1, "sill": 0.0, "inferred": True},
        {"id": "op_door_bed_mid_right", "wall_id": "w_bed_mid_right_north", "type": "door", "offset": 1.5, "width": 0.9, "height": 2.1, "sill": 0.0, "inferred": True},
        {"id": "op_door_bed_master_right", "wall_id": "w_bed_mid_right_north", "type": "door", "offset": 0.3, "width": 0.9, "height": 2.1, "sill": 0.0, "inferred": True},
        {"id": "op_door_store", "wall_id": "w_passage_right_east", "type": "door", "offset": 0.5, "width": 0.8, "height": 2.1, "sill": 0.0, "inferred": True},
        {"id": "op_door_wash_right", "wall_id": "w_passage_wash_divider", "type": "door", "offset": 0.15, "width": 0.8, "height": 2.1, "sill": 0.0, "inferred": True},
        {"id": "op_door_toi_1", "wall_id": "w_wash_right_north", "type": "door", "offset": 0.3, "width": 0.8, "height": 2.1, "sill": 0.0, "inferred": True},
        {"id": "op_door_toi_2", "wall_id": "w_wash_right_north", "type": "door", "offset": 1.5, "width": 0.8, "height": 2.1, "sill": 0.0, "inferred": True},
    ]

    openings = windows + doors

    # -------------------------------------------------------------------------
    # COLUMNS (24 Blue Structural RCC Columns from the Blueprint)
    # -------------------------------------------------------------------------
    columns = [
        # Front Boundary line (y = 0.0)
        {"id": "col_01", "position": [0.0, 0.0], "width": 0.23, "depth": 0.23},
        {"id": "col_02", "position": [4.11, 0.0], "width": 0.23, "depth": 0.23},
        {"id": "col_03", "position": [11.12, 0.0], "width": 0.23, "depth": 0.23},

        # Front Plinth line (y = 2.44)
        {"id": "col_04", "position": [0.0, 2.44], "width": 0.23, "depth": 0.23},
        {"id": "col_05", "position": [4.11, 2.44], "width": 0.23, "depth": 0.23},
        {"id": "col_06", "position": [5.41, 2.44], "width": 0.23, "depth": 0.23},
        {"id": "col_07", "position": [11.12, 2.44], "width": 0.23, "depth": 0.23},

        # Mid Grid 1 (y ≈ 7.05)
        {"id": "col_08", "position": [0.0, 7.05], "width": 0.23, "depth": 0.23},
        {"id": "col_09", "position": [1.44, 7.05], "width": 0.23, "depth": 0.23},
        {"id": "col_10", "position": [5.41, 7.05], "width": 0.23, "depth": 0.23},
        {"id": "col_11", "position": [11.12, 8.00], "width": 0.23, "depth": 0.23},

        # Mid Grid 2 (y ≈ 10.50 / 11.13)
        {"id": "col_12", "position": [1.44, 10.50], "width": 0.23, "depth": 0.23},
        {"id": "col_13", "position": [5.41, 11.13], "width": 0.23, "depth": 0.23},
        {"id": "col_14", "position": [8.45, 11.13], "width": 0.23, "depth": 0.23},
        {"id": "col_15", "position": [11.12, 12.40], "width": 0.23, "depth": 0.23},

        # Mid Grid 3 (y ≈ 12.20 / 12.40)
        {"id": "col_16", "position": [0.0, 12.20], "width": 0.23, "depth": 0.23},
        {"id": "col_17", "position": [3.86, 12.20], "width": 0.23, "depth": 0.23},
        {"id": "col_18", "position": [8.45, 12.40], "width": 0.23, "depth": 0.23},
        {"id": "col_19", "position": [11.12, 14.15], "width": 0.23, "depth": 0.23},

        # Rear Line (y ≈ 15.75)
        {"id": "col_20", "position": [0.0, 15.75], "width": 0.23, "depth": 0.23},
        {"id": "col_21", "position": [3.86, 15.75], "width": 0.23, "depth": 0.23},
        {"id": "col_22", "position": [5.41, 15.75], "width": 0.23, "depth": 0.23},
        {"id": "col_23", "position": [8.45, 15.75], "width": 0.23, "depth": 0.23},

        # Top-Right Toilets Rear (y ≈ 16.65)
        {"id": "col_24", "position": [8.45, 16.65], "width": 0.23, "depth": 0.23},
        {"id": "col_25", "position": [11.12, 16.65], "width": 0.23, "depth": 0.23},
    ]

    plan_dict = {
        "version": 1,
        "units": "m",
        "scale_source": "dimension_label",
        "project_title": "36'6\" X 55' (E) AT SHALIMAR GREENS",
        "subject": "SECOND FLOOR PLAN",
        "client": "SMT. GEETA GAUD",
        "architect": "Er. VIKAS PATODI",
        "levels": [
            {
                "elevation": 0.0,
                "wall_height": 2.8,
                "walls": walls,
                "openings": openings,
                "rooms": rooms,
                "columns": columns,
            }
        ],
    }

    # Compute objective confidence from validator suite
    conf = compute_plan_confidence(plan_dict)
    plan_dict["confidence"] = conf
    return plan_dict


def main():
    plan_dict = generate_precision_plan()

    # Validate schema
    validated = PlanJSON(**plan_dict)
    data = validated.model_dump()

    # Run full validator suite to inspect diagnostics
    bb = validate_bounding_box(data)
    yo = validate_y_axis_orientation(data)
    rm = validate_room_dimensions_vs_labels(data)
    ls = validate_l_shaped_rooms(data)
    og = validate_overlaps_and_gaps(data)
    wc = validate_wall_connectivity(data)
    op = validate_openings(data)
    cov = validate_room_wall_coverage(data)

    print("-------------------------------------------------------")
    print("VALIDATION SUITE RESULTS:")
    print("-------------------------------------------------------")
    print(f"Bounding Box:     {'PASS' if bb['passed'] else 'FAIL'} (Measured {bb['measured_width']}m x {bb['measured_height']}m vs 11.12m x 16.76m)")
    print(f"Y-Axis Origin:    {'PASS' if yo['passed'] else 'FAIL'} (Upright, non-mirrored)")
    print(f"Room Dimensions:  {'PASS' if rm['passed'] else 'FAIL'} ({rm['matched_count']}/{rm['total_labeled_rooms']} matched)")
    print(f"L-Shaped Rooms:   {'PASS' if ls['passed'] else 'FAIL'} ({ls['l_shaped_rooms_found']} validated)")
    print(f"Overlaps & Gaps:  {'PASS' if og['passed'] else 'FAIL'} ({og['overlap_count']} overlaps)")
    print(f"Wall Connection:  {'PASS' if wc['passed'] else 'FAIL'} ({wc['connectivity_ratio']*100}% connected)")
    print(f"Openings Bounds:  {'PASS' if op['passed'] else 'FAIL'} ({op['error_count']} errors)")
    print(f"Wall Coverage:    {'PASS' if cov['passed'] else 'FAIL'} (Average coverage {cov['average_covered_fraction']*100}%)")
    print(f"Computed Conf.:   {data['confidence']['overall']} (Bounding: {data['confidence']['bounding_box_fidelity']}, Conn: {data['confidence']['wall_connectivity']}, Coverage: {data['confidence']['wall_coverage']})")
    print("-------------------------------------------------------")

    # Write to extracted_plan.json
    out_file = backend_dir / "extracted_plan.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"SUCCESS: Exported to {out_file}")


if __name__ == "__main__":
    main()
