import type { MaterialQuantityItem, PlanJSON } from '../types';

export const DEFAULT_ARCHITECTURAL_PLAN: PlanJSON = {
  "version": 1,
  "units": "m",
  "scale_source": "dimension_label",
  "project_title": "Dual Independent 2-BHK Rental Units (Vikas Patodi Blueprint Standard)",
  "subject": "ARCHITECTURAL CAD WORKING DRAWING",
  "client": "SMT. GEETA GAUD",
  "architect": "AI CAD ARCHITECT",
  "levels": [
    {
      "elevation": 0.0,
      "wall_height": 2.8,
      "walls": [
        {
          "id": "w_001",
          "start": [
            0.0,
            0.0
          ],
          "end": [
            3.5,
            0.0
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 3.5,
          "inferred": false,
          "rooms": [
            "flat2_bed_master"
          ]
        },
        {
          "id": "w_002",
          "start": [
            3.5,
            0.0
          ],
          "end": [
            4.72,
            0.0
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 1.22,
          "inferred": false,
          "rooms": [
            "flat2_toi_master"
          ]
        },
        {
          "id": "w_003",
          "start": [
            4.72,
            0.0
          ],
          "end": [
            7.67,
            0.0
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 2.95,
          "inferred": false,
          "rooms": [
            "flat2_kit"
          ]
        },
        {
          "id": "w_004",
          "start": [
            7.67,
            0.0
          ],
          "end": [
            11.12,
            0.0
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 3.45,
          "inferred": false,
          "rooms": [
            "flat2_wash"
          ]
        },
        {
          "id": "w_005",
          "start": [
            7.67,
            1.22
          ],
          "end": [
            11.12,
            1.22
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 3.45,
          "inferred": false,
          "rooms": [
            "flat2_wash",
            "flat2_bed2"
          ]
        },
        {
          "id": "w_006",
          "start": [
            3.5,
            2.29
          ],
          "end": [
            4.72,
            2.29
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.22,
          "inferred": false,
          "rooms": [
            "flat2_toi_master",
            "flat2_passage"
          ]
        },
        {
          "id": "w_007",
          "start": [
            4.72,
            2.44
          ],
          "end": [
            7.67,
            2.44
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 2.95,
          "inferred": false,
          "rooms": [
            "flat2_kit",
            "flat2_passage"
          ]
        },
        {
          "id": "w_008",
          "start": [
            0.0,
            3.5
          ],
          "end": [
            3.5,
            3.5
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 3.5,
          "inferred": false,
          "rooms": [
            "flat2_bed_master"
          ]
        },
        {
          "id": "w_009",
          "start": [
            0.0,
            4.42
          ],
          "end": [
            1.37,
            4.42
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 1.37,
          "inferred": false,
          "rooms": [
            "flat1_toi_bed2"
          ]
        },
        {
          "id": "w_010",
          "start": [
            1.37,
            4.42
          ],
          "end": [
            3.5,
            4.42
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 2.13,
          "inferred": false,
          "rooms": [
            "flat1_bed2"
          ]
        },
        {
          "id": "w_011",
          "start": [
            3.5,
            4.42
          ],
          "end": [
            5.43,
            4.42
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.93,
          "inferred": false,
          "rooms": [
            "flat2_passage",
            "flat1_bed2"
          ]
        },
        {
          "id": "w_012",
          "start": [
            5.43,
            4.42
          ],
          "end": [
            7.67,
            4.42
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 2.24,
          "inferred": false,
          "rooms": [
            "flat2_passage",
            "flat2_living"
          ]
        },
        {
          "id": "w_013",
          "start": [
            7.67,
            4.42
          ],
          "end": [
            9.45,
            4.42
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.78,
          "inferred": false,
          "rooms": [
            "flat2_bed2",
            "flat2_living"
          ]
        },
        {
          "id": "w_014",
          "start": [
            9.45,
            4.42
          ],
          "end": [
            11.12,
            4.42
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 1.67,
          "inferred": false,
          "rooms": [
            "flat2_bed2",
            "open_shaft"
          ]
        },
        {
          "id": "w_015",
          "start": [
            0.0,
            6.15
          ],
          "end": [
            1.37,
            6.15
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 1.37,
          "inferred": false,
          "rooms": [
            "flat1_toi_bed2",
            "flat1_duct1"
          ]
        },
        {
          "id": "w_016",
          "start": [
            9.45,
            7.16
          ],
          "end": [
            11.12,
            7.16
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 1.67,
          "inferred": false,
          "rooms": [
            "open_shaft",
            "side_passage"
          ]
        },
        {
          "id": "w_017",
          "start": [
            0.0,
            7.26
          ],
          "end": [
            1.37,
            7.26
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 1.37,
          "inferred": false,
          "rooms": [
            "flat1_duct1",
            "flat1_wash_kit"
          ]
        },
        {
          "id": "w_018",
          "start": [
            1.37,
            7.26
          ],
          "end": [
            4.42,
            7.26
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 3.05,
          "inferred": false,
          "rooms": [
            "flat1_bed2",
            "flat1_kit"
          ]
        },
        {
          "id": "w_019",
          "start": [
            4.42,
            7.26
          ],
          "end": [
            5.43,
            7.26
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.01,
          "inferred": false,
          "rooms": [
            "flat1_bed2",
            "passage_main"
          ]
        },
        {
          "id": "w_020",
          "start": [
            0.0,
            9.4
          ],
          "end": [
            1.37,
            9.4
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.37,
          "inferred": false,
          "rooms": [
            "flat1_wash_kit",
            "flat1_wash_util"
          ]
        },
        {
          "id": "w_021",
          "start": [
            1.37,
            9.4
          ],
          "end": [
            2.59,
            9.4
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.22,
          "inferred": false,
          "rooms": [
            "flat1_kit",
            "flat1_wash_util"
          ]
        },
        {
          "id": "w_022",
          "start": [
            2.59,
            9.4
          ],
          "end": [
            4.42,
            9.4
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.83,
          "inferred": false,
          "rooms": [
            "flat1_kit",
            "flat1_toi_comm"
          ]
        },
        {
          "id": "w_023",
          "start": [
            5.43,
            9.45
          ],
          "end": [
            9.45,
            9.45
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 4.02,
          "inferred": false,
          "rooms": [
            "flat2_living",
            "flat1_living"
          ]
        },
        {
          "id": "w_024",
          "start": [
            0.0,
            10.82
          ],
          "end": [
            1.37,
            10.82
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.37,
          "inferred": false,
          "rooms": [
            "flat1_wash_util",
            "flat1_toi1"
          ]
        },
        {
          "id": "w_025",
          "start": [
            1.37,
            10.82
          ],
          "end": [
            2.59,
            10.82
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.22,
          "inferred": false,
          "rooms": [
            "flat1_wash_util",
            "flat1_bed1"
          ]
        },
        {
          "id": "w_026",
          "start": [
            2.59,
            10.82
          ],
          "end": [
            4.42,
            10.82
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.83,
          "inferred": false,
          "rooms": [
            "flat1_toi_comm",
            "flat1_bed1"
          ]
        },
        {
          "id": "w_027",
          "start": [
            4.42,
            10.82
          ],
          "end": [
            5.43,
            10.82
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.01,
          "inferred": false,
          "rooms": [
            "passage_main",
            "flat1_bed1"
          ]
        },
        {
          "id": "w_028",
          "start": [
            0.0,
            13.87
          ],
          "end": [
            1.37,
            13.87
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.37,
          "inferred": false,
          "rooms": [
            "flat1_toi1",
            "staircase"
          ]
        },
        {
          "id": "w_029",
          "start": [
            1.37,
            13.87
          ],
          "end": [
            4.12,
            13.87
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 2.75,
          "inferred": false,
          "rooms": [
            "flat1_bed1",
            "staircase"
          ]
        },
        {
          "id": "w_030",
          "start": [
            4.12,
            13.87
          ],
          "end": [
            5.43,
            13.87
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.31,
          "inferred": false,
          "rooms": [
            "flat1_bed1",
            "verandah_front"
          ]
        },
        {
          "id": "w_031",
          "start": [
            5.43,
            13.87
          ],
          "end": [
            9.45,
            13.87
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 4.02,
          "inferred": false,
          "rooms": [
            "flat1_living",
            "verandah_front"
          ]
        },
        {
          "id": "w_032",
          "start": [
            9.45,
            13.87
          ],
          "end": [
            11.12,
            13.87
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.67,
          "inferred": false,
          "rooms": [
            "side_passage",
            "verandah_front"
          ]
        },
        {
          "id": "w_033",
          "start": [
            4.12,
            15.49
          ],
          "end": [
            7.16,
            15.49
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 3.04,
          "inferred": false,
          "rooms": [
            "verandah_front"
          ]
        },
        {
          "id": "w_034",
          "start": [
            7.16,
            15.49
          ],
          "end": [
            11.12,
            15.49
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 3.96,
          "inferred": false,
          "rooms": [
            "verandah_front",
            "lawn_front"
          ]
        },
        {
          "id": "w_035",
          "start": [
            0.0,
            16.76
          ],
          "end": [
            4.12,
            16.76
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 4.12,
          "inferred": false,
          "rooms": [
            "staircase"
          ]
        },
        {
          "id": "w_036",
          "start": [
            0.0,
            0.0
          ],
          "end": [
            0.0,
            3.5
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 3.5,
          "inferred": false,
          "rooms": [
            "flat2_bed_master"
          ]
        },
        {
          "id": "w_037",
          "start": [
            0.0,
            4.42
          ],
          "end": [
            0.0,
            6.15
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 1.73,
          "inferred": false,
          "rooms": [
            "flat1_toi_bed2"
          ]
        },
        {
          "id": "w_038",
          "start": [
            0.0,
            7.26
          ],
          "end": [
            0.0,
            9.4
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 2.14,
          "inferred": false,
          "rooms": [
            "flat1_wash_kit"
          ]
        },
        {
          "id": "w_039",
          "start": [
            0.0,
            9.4
          ],
          "end": [
            0.0,
            10.82
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 1.42,
          "inferred": false,
          "rooms": [
            "flat1_wash_util"
          ]
        },
        {
          "id": "w_040",
          "start": [
            0.0,
            10.82
          ],
          "end": [
            0.0,
            13.87
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 3.05,
          "inferred": false,
          "rooms": [
            "flat1_toi1"
          ]
        },
        {
          "id": "w_041",
          "start": [
            0.0,
            13.87
          ],
          "end": [
            0.0,
            16.76
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 2.89,
          "inferred": false,
          "rooms": [
            "staircase"
          ]
        },
        {
          "id": "w_042",
          "start": [
            1.37,
            4.42
          ],
          "end": [
            1.37,
            6.15
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.73,
          "inferred": false,
          "rooms": [
            "flat1_toi_bed2",
            "flat1_bed2"
          ]
        },
        {
          "id": "w_043",
          "start": [
            1.37,
            6.15
          ],
          "end": [
            1.37,
            7.26
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 1.11,
          "inferred": false,
          "rooms": [
            "flat1_duct1",
            "flat1_bed2"
          ]
        },
        {
          "id": "w_044",
          "start": [
            1.37,
            7.26
          ],
          "end": [
            1.37,
            9.4
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 2.14,
          "inferred": false,
          "rooms": [
            "flat1_wash_kit",
            "flat1_kit"
          ]
        },
        {
          "id": "w_045",
          "start": [
            1.37,
            10.82
          ],
          "end": [
            1.37,
            13.87
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 3.05,
          "inferred": false,
          "rooms": [
            "flat1_toi1",
            "flat1_bed1"
          ]
        },
        {
          "id": "w_046",
          "start": [
            2.59,
            9.4
          ],
          "end": [
            2.59,
            10.82
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.42,
          "inferred": false,
          "rooms": [
            "flat1_wash_util",
            "flat1_toi_comm"
          ]
        },
        {
          "id": "w_047",
          "start": [
            3.5,
            0.0
          ],
          "end": [
            3.5,
            2.29
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 2.29,
          "inferred": false,
          "rooms": [
            "flat2_bed_master",
            "flat2_toi_master"
          ]
        },
        {
          "id": "w_048",
          "start": [
            3.5,
            2.29
          ],
          "end": [
            3.5,
            3.5
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.21,
          "inferred": false,
          "rooms": [
            "flat2_bed_master",
            "flat2_passage"
          ]
        },
        {
          "id": "w_049",
          "start": [
            3.5,
            3.5
          ],
          "end": [
            3.5,
            4.42
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 0.92,
          "inferred": false,
          "rooms": [
            "flat2_passage"
          ]
        },
        {
          "id": "w_050",
          "start": [
            4.12,
            13.87
          ],
          "end": [
            4.12,
            15.49
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.62,
          "inferred": false,
          "rooms": [
            "staircase",
            "verandah_front"
          ]
        },
        {
          "id": "w_051",
          "start": [
            4.12,
            15.49
          ],
          "end": [
            4.12,
            16.76
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 1.27,
          "inferred": false,
          "rooms": [
            "staircase"
          ]
        },
        {
          "id": "w_052",
          "start": [
            4.42,
            7.26
          ],
          "end": [
            4.42,
            9.4
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 2.14,
          "inferred": false,
          "rooms": [
            "flat1_kit",
            "passage_main"
          ]
        },
        {
          "id": "w_053",
          "start": [
            4.42,
            9.4
          ],
          "end": [
            4.42,
            10.82
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.42,
          "inferred": false,
          "rooms": [
            "flat1_toi_comm",
            "passage_main"
          ]
        },
        {
          "id": "w_054",
          "start": [
            4.72,
            0.0
          ],
          "end": [
            4.72,
            2.29
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 2.29,
          "inferred": false,
          "rooms": [
            "flat2_toi_master",
            "flat2_kit"
          ]
        },
        {
          "id": "w_055",
          "start": [
            4.72,
            2.29
          ],
          "end": [
            4.72,
            2.44
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 0.15,
          "inferred": false,
          "rooms": [
            "flat2_passage",
            "flat2_kit"
          ]
        },
        {
          "id": "w_056",
          "start": [
            5.43,
            4.42
          ],
          "end": [
            5.43,
            7.26
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 2.84,
          "inferred": false,
          "rooms": [
            "flat1_bed2",
            "flat2_living"
          ]
        },
        {
          "id": "w_057",
          "start": [
            5.43,
            7.26
          ],
          "end": [
            5.43,
            9.45
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 2.19,
          "inferred": false,
          "rooms": [
            "passage_main",
            "flat2_living"
          ]
        },
        {
          "id": "w_058",
          "start": [
            5.43,
            9.45
          ],
          "end": [
            5.43,
            10.82
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.37,
          "inferred": false,
          "rooms": [
            "passage_main",
            "flat1_living"
          ]
        },
        {
          "id": "w_059",
          "start": [
            5.43,
            10.82
          ],
          "end": [
            5.43,
            13.87
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 3.05,
          "inferred": false,
          "rooms": [
            "flat1_bed1",
            "flat1_living"
          ]
        },
        {
          "id": "w_060",
          "start": [
            7.67,
            0.0
          ],
          "end": [
            7.67,
            1.22
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.22,
          "inferred": false,
          "rooms": [
            "flat2_kit",
            "flat2_wash"
          ]
        },
        {
          "id": "w_061",
          "start": [
            7.67,
            1.22
          ],
          "end": [
            7.67,
            2.44
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.22,
          "inferred": false,
          "rooms": [
            "flat2_kit",
            "flat2_bed2"
          ]
        },
        {
          "id": "w_062",
          "start": [
            7.67,
            2.44
          ],
          "end": [
            7.67,
            4.42
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 1.98,
          "inferred": false,
          "rooms": [
            "flat2_passage",
            "flat2_bed2"
          ]
        },
        {
          "id": "w_063",
          "start": [
            9.45,
            4.42
          ],
          "end": [
            9.45,
            7.16
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 2.74,
          "inferred": false,
          "rooms": [
            "flat2_living",
            "open_shaft"
          ]
        },
        {
          "id": "w_064",
          "start": [
            9.45,
            7.16
          ],
          "end": [
            9.45,
            9.45
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 2.29,
          "inferred": false,
          "rooms": [
            "flat2_living",
            "side_passage"
          ]
        },
        {
          "id": "w_065",
          "start": [
            9.45,
            9.45
          ],
          "end": [
            9.45,
            13.87
          ],
          "thickness": 0.12,
          "height": 2.8,
          "kind": "interior",
          "type": "interior",
          "length": 4.42,
          "inferred": false,
          "rooms": [
            "flat1_living",
            "side_passage"
          ]
        },
        {
          "id": "w_066",
          "start": [
            11.12,
            0.0
          ],
          "end": [
            11.12,
            1.22
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 1.22,
          "inferred": false,
          "rooms": [
            "flat2_wash"
          ]
        },
        {
          "id": "w_067",
          "start": [
            11.12,
            1.22
          ],
          "end": [
            11.12,
            4.42
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 3.2,
          "inferred": false,
          "rooms": [
            "flat2_bed2"
          ]
        },
        {
          "id": "w_068",
          "start": [
            11.12,
            7.16
          ],
          "end": [
            11.12,
            13.87
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 6.71,
          "inferred": false,
          "rooms": [
            "side_passage"
          ]
        },
        {
          "id": "w_069",
          "start": [
            11.12,
            13.87
          ],
          "end": [
            11.12,
            15.49
          ],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior",
          "length": 1.62,
          "inferred": false,
          "rooms": [
            "verandah_front"
          ]
        }
      ],
      "openings": [
        {
          "id": "door_001",
          "wall_id": "w_031",
          "type": "door",
          "offset": 1.51,
          "width": 1.0,
          "height": 2.1,
          "sill": 0.0,
          "inferred": false
        },
        {
          "id": "door_002",
          "wall_id": "w_050",
          "type": "door",
          "offset": 0.36,
          "width": 0.9,
          "height": 2.1,
          "sill": 0.0,
          "inferred": false
        },
        {
          "id": "door_003",
          "wall_id": "w_064",
          "type": "door",
          "offset": 0.67,
          "width": 0.95,
          "height": 2.1,
          "sill": 0.0,
          "inferred": false
        },
        {
          "id": "door_004",
          "wall_id": "w_059",
          "type": "door",
          "offset": 1.1,
          "width": 0.85,
          "height": 2.1,
          "sill": 0.0,
          "inferred": false
        },
        {
          "id": "door_005",
          "wall_id": "w_045",
          "type": "door",
          "offset": 1.15,
          "width": 0.75,
          "height": 2.1,
          "sill": 0.0,
          "inferred": false
        },
        {
          "id": "door_006",
          "wall_id": "w_058",
          "type": "door",
          "offset": 0.24,
          "width": 0.9,
          "height": 2.1,
          "sill": 0.0,
          "inferred": false
        },
        {
          "id": "door_007",
          "wall_id": "w_019",
          "type": "door",
          "offset": 0.2,
          "width": 0.85,
          "height": 2.1,
          "sill": 0.0,
          "inferred": false
        },
        {
          "id": "door_008",
          "wall_id": "w_052",
          "type": "door",
          "offset": 0.65,
          "width": 0.85,
          "height": 2.1,
          "sill": 0.0,
          "inferred": false
        },
        {
          "id": "door_009",
          "wall_id": "w_044",
          "type": "door",
          "offset": 0.7,
          "width": 0.75,
          "height": 2.1,
          "sill": 0.0,
          "inferred": false
        },
        {
          "id": "door_010",
          "wall_id": "w_053",
          "type": "door",
          "offset": 0.33,
          "width": 0.75,
          "height": 2.1,
          "sill": 0.0,
          "inferred": false
        },
        {
          "id": "door_011",
          "wall_id": "w_042",
          "type": "door",
          "offset": 0.49,
          "width": 0.75,
          "height": 2.1,
          "sill": 0.0,
          "inferred": false
        },
        {
          "id": "door_012",
          "wall_id": "w_012",
          "type": "door",
          "offset": 0.67,
          "width": 0.9,
          "height": 2.1,
          "sill": 0.0,
          "inferred": false
        },
        {
          "id": "door_013",
          "wall_id": "w_048",
          "type": "door",
          "offset": 0.2,
          "width": 0.85,
          "height": 2.1,
          "sill": 0.0,
          "inferred": false
        },
        {
          "id": "door_014",
          "wall_id": "w_047",
          "type": "door",
          "offset": 0.77,
          "width": 0.75,
          "height": 2.1,
          "sill": 0.0,
          "inferred": false
        },
        {
          "id": "door_015",
          "wall_id": "w_062",
          "type": "door",
          "offset": 0.56,
          "width": 0.85,
          "height": 2.1,
          "sill": 0.0,
          "inferred": false
        },
        {
          "id": "door_016",
          "wall_id": "w_007",
          "type": "door",
          "offset": 1.05,
          "width": 0.85,
          "height": 2.1,
          "sill": 0.0,
          "inferred": false
        },
        {
          "id": "door_017",
          "wall_id": "w_060",
          "type": "door",
          "offset": 0.23,
          "width": 0.75,
          "height": 2.1,
          "sill": 0.0,
          "inferred": false
        },
        {
          "id": "door_018",
          "wall_id": "w_020",
          "type": "door",
          "offset": 0.2,
          "width": 0.85,
          "height": 2.1,
          "sill": 0.0,
          "inferred": false
        },
        {
          "id": "win_019",
          "wall_id": "w_001",
          "type": "window",
          "offset": 1.15,
          "width": 1.2,
          "height": 1.4,
          "sill": 0.9,
          "inferred": false
        },
        {
          "id": "win_020",
          "wall_id": "w_003",
          "type": "window",
          "offset": 0.88,
          "width": 1.2,
          "height": 1.4,
          "sill": 0.9,
          "inferred": false
        },
        {
          "id": "win_021",
          "wall_id": "w_014",
          "type": "window",
          "offset": 0.23,
          "width": 1.2,
          "height": 1.4,
          "sill": 0.9,
          "inferred": false
        },
        {
          "id": "win_022",
          "wall_id": "w_010",
          "type": "window",
          "offset": 0.46,
          "width": 1.2,
          "height": 1.4,
          "sill": 0.9,
          "inferred": false
        },
        {
          "id": "win_023",
          "wall_id": "w_063",
          "type": "window",
          "offset": 0.77,
          "width": 1.2,
          "height": 1.4,
          "sill": 0.9,
          "inferred": false
        }
      ],
      "rooms": [
        {
          "id": "flat2_bed_master",
          "name": "BED ROOM",
          "category": "Bedroom",
          "kind": "indoor",
          "polygon": [
            [
              0.0,
              0.0
            ],
            [
              3.5,
              0.0
            ],
            [
              3.5,
              3.5
            ],
            [
              0.0,
              3.5
            ]
          ],
          "tag": "bedroom",
          "dimensions": "11' X 11'"
        },
        {
          "id": "flat2_toi_master",
          "name": "TOI.",
          "category": "Toilet",
          "kind": "indoor",
          "polygon": [
            [
              3.5,
              0.0
            ],
            [
              4.72,
              0.0
            ],
            [
              4.72,
              2.29
            ],
            [
              3.5,
              2.29
            ]
          ],
          "tag": "toilet",
          "dimensions": "4' X 7'6\""
        },
        {
          "id": "flat2_kit",
          "name": "KIT.",
          "category": "Kitchen",
          "kind": "indoor",
          "polygon": [
            [
              4.72,
              0.0
            ],
            [
              7.67,
              0.0
            ],
            [
              7.67,
              2.44
            ],
            [
              4.72,
              2.44
            ]
          ],
          "tag": "kitchen",
          "dimensions": "9'8\" X 8'"
        },
        {
          "id": "flat2_wash",
          "name": "WASH",
          "category": "Utility",
          "kind": "indoor",
          "polygon": [
            [
              7.67,
              0.0
            ],
            [
              11.12,
              0.0
            ],
            [
              11.12,
              1.22
            ],
            [
              7.67,
              1.22
            ]
          ],
          "tag": "wash",
          "dimensions": "13'8\" X 4'"
        },
        {
          "id": "flat2_bed2",
          "name": "BED.",
          "category": "Bedroom",
          "kind": "indoor",
          "polygon": [
            [
              7.67,
              1.22
            ],
            [
              11.12,
              1.22
            ],
            [
              11.12,
              4.42
            ],
            [
              7.67,
              4.42
            ]
          ],
          "tag": "bedroom",
          "dimensions": "9'6\" X 10'6\""
        },
        {
          "id": "flat2_passage",
          "name": "PASSAGE",
          "category": "Circulation",
          "kind": "indoor",
          "polygon": [
            [
              3.5,
              2.29
            ],
            [
              7.67,
              2.29
            ],
            [
              7.67,
              4.42
            ],
            [
              3.5,
              4.42
            ]
          ],
          "tag": "passage",
          "dimensions": "3'4\" WD."
        },
        {
          "id": "flat1_toi_bed2",
          "name": "TOI.",
          "category": "Toilet",
          "kind": "indoor",
          "polygon": [
            [
              0.0,
              4.42
            ],
            [
              1.37,
              4.42
            ],
            [
              1.37,
              6.15
            ],
            [
              0.0,
              6.15
            ]
          ],
          "tag": "toilet",
          "dimensions": "4'6\" X 5'8\""
        },
        {
          "id": "flat1_duct1",
          "name": "DUCT",
          "category": "Void",
          "kind": "outdoor",
          "polygon": [
            [
              0.0,
              6.15
            ],
            [
              1.37,
              6.15
            ],
            [
              1.37,
              7.26
            ],
            [
              0.0,
              7.26
            ]
          ],
          "tag": "open",
          "dimensions": "4'6\" X 3'8\""
        },
        {
          "id": "flat1_bed2",
          "name": "BEDROOM",
          "category": "Bedroom",
          "kind": "indoor",
          "polygon": [
            [
              1.37,
              4.42
            ],
            [
              5.43,
              4.42
            ],
            [
              5.43,
              7.26
            ],
            [
              1.37,
              7.26
            ]
          ],
          "tag": "bedroom",
          "dimensions": "13'4\" X 9'4\""
        },
        {
          "id": "flat2_living",
          "name": "DRG./DIN.",
          "category": "Living",
          "kind": "indoor",
          "polygon": [
            [
              5.43,
              4.42
            ],
            [
              9.45,
              4.42
            ],
            [
              9.45,
              9.45
            ],
            [
              5.43,
              9.45
            ]
          ],
          "tag": "living",
          "dimensions": "11'9\" X 16'6\""
        },
        {
          "id": "open_shaft",
          "name": "OPEN",
          "category": "Void",
          "kind": "outdoor",
          "polygon": [
            [
              9.45,
              4.42
            ],
            [
              11.12,
              4.42
            ],
            [
              11.12,
              7.16
            ],
            [
              9.45,
              7.16
            ]
          ],
          "tag": "open",
          "dimensions": "5' X 9'"
        },
        {
          "id": "flat1_kit",
          "name": "KIT.",
          "category": "Kitchen",
          "kind": "indoor",
          "polygon": [
            [
              1.37,
              7.26
            ],
            [
              4.42,
              7.26
            ],
            [
              4.42,
              9.4
            ],
            [
              1.37,
              9.4
            ]
          ],
          "tag": "kitchen",
          "dimensions": "10' X 7'"
        },
        {
          "id": "flat1_wash_kit",
          "name": "WASH",
          "category": "Utility",
          "kind": "indoor",
          "polygon": [
            [
              0.0,
              7.26
            ],
            [
              1.37,
              7.26
            ],
            [
              1.37,
              9.4
            ],
            [
              0.0,
              9.4
            ]
          ],
          "tag": "wash",
          "dimensions": "4'6\" X 7'"
        },
        {
          "id": "flat1_wash_util",
          "name": "WASH",
          "category": "Utility",
          "kind": "indoor",
          "polygon": [
            [
              0.0,
              9.4
            ],
            [
              2.59,
              9.4
            ],
            [
              2.59,
              10.82
            ],
            [
              0.0,
              10.82
            ]
          ],
          "tag": "wash",
          "dimensions": "8'4\" X 4'8\""
        },
        {
          "id": "flat1_toi_comm",
          "name": "TOI.",
          "category": "Toilet",
          "kind": "indoor",
          "polygon": [
            [
              2.59,
              9.4
            ],
            [
              4.42,
              9.4
            ],
            [
              4.42,
              10.82
            ],
            [
              2.59,
              10.82
            ]
          ],
          "tag": "toilet",
          "dimensions": "6' X 4'4\""
        },
        {
          "id": "passage_main",
          "name": "PASSAGE",
          "category": "Circulation",
          "kind": "indoor",
          "polygon": [
            [
              4.42,
              7.26
            ],
            [
              5.43,
              7.26
            ],
            [
              5.43,
              10.82
            ],
            [
              4.42,
              10.82
            ]
          ],
          "tag": "passage",
          "dimensions": "3'6\" WD."
        },
        {
          "id": "flat1_toi1",
          "name": "TOI.",
          "category": "Toilet",
          "kind": "indoor",
          "polygon": [
            [
              0.0,
              10.82
            ],
            [
              1.37,
              10.82
            ],
            [
              1.37,
              13.87
            ],
            [
              0.0,
              13.87
            ]
          ],
          "tag": "toilet",
          "dimensions": "4'6\" X 10'"
        },
        {
          "id": "flat1_bed1",
          "name": "BEDROOM",
          "category": "Bedroom",
          "kind": "indoor",
          "polygon": [
            [
              1.37,
              10.82
            ],
            [
              5.43,
              10.82
            ],
            [
              5.43,
              13.87
            ],
            [
              1.37,
              13.87
            ]
          ],
          "tag": "bedroom",
          "dimensions": "13'4\" X 9'6\""
        },
        {
          "id": "flat1_living",
          "name": "DRG./DIN.",
          "category": "Living",
          "kind": "indoor",
          "polygon": [
            [
              5.43,
              9.45
            ],
            [
              9.45,
              9.45
            ],
            [
              9.45,
              13.87
            ],
            [
              5.43,
              13.87
            ]
          ],
          "tag": "living",
          "dimensions": "12'4\" X 14'"
        },
        {
          "id": "side_passage",
          "name": "PASSAGE",
          "category": "Circulation",
          "kind": "indoor",
          "polygon": [
            [
              9.45,
              7.16
            ],
            [
              11.12,
              7.16
            ],
            [
              11.12,
              13.87
            ],
            [
              9.45,
              13.87
            ]
          ],
          "tag": "passage",
          "dimensions": "4'6\" WD."
        },
        {
          "id": "staircase",
          "name": "STAIRCASE",
          "category": "Circulation",
          "kind": "semi_open",
          "polygon": [
            [
              0.0,
              13.87
            ],
            [
              4.12,
              13.87
            ],
            [
              4.12,
              16.76
            ],
            [
              0.0,
              16.76
            ]
          ],
          "tag": "stairs",
          "dimensions": "UP / DN"
        },
        {
          "id": "verandah_front",
          "name": "VERANDAH",
          "category": "Outdoor",
          "kind": "semi_open",
          "polygon": [
            [
              4.12,
              13.87
            ],
            [
              11.12,
              13.87
            ],
            [
              11.12,
              15.49
            ],
            [
              4.12,
              15.49
            ]
          ],
          "tag": "verandah",
          "dimensions": "23' X 4'4\""
        },
        {
          "id": "lawn_front",
          "name": "LAWN",
          "category": "Garden",
          "kind": "outdoor",
          "polygon": [
            [
              7.16,
              15.49
            ],
            [
              11.12,
              15.49
            ],
            [
              11.12,
              16.76
            ],
            [
              7.16,
              16.76
            ]
          ],
          "tag": "lawn",
          "dimensions": "4' WD."
        }
      ],
      "columns": [
        {
          "id": "col_001",
          "position": [
            0.0,
            0.0
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_002",
          "position": [
            0.0,
            3.5
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_003",
          "position": [
            0.0,
            6.15
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_004",
          "position": [
            0.0,
            9.4
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_005",
          "position": [
            0.0,
            13.87
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_006",
          "position": [
            0.0,
            16.76
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_007",
          "position": [
            2.59,
            9.4
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_008",
          "position": [
            3.5,
            0.0
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_009",
          "position": [
            3.5,
            2.29
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_010",
          "position": [
            3.5,
            4.42
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_011",
          "position": [
            4.12,
            13.87
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_012",
          "position": [
            4.12,
            16.76
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_013",
          "position": [
            4.42,
            7.26
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_014",
          "position": [
            5.43,
            9.45
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_015",
          "position": [
            7.16,
            15.49
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_016",
          "position": [
            7.67,
            0.0
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_017",
          "position": [
            7.67,
            2.44
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_018",
          "position": [
            9.45,
            7.16
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_019",
          "position": [
            9.45,
            9.45
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_020",
          "position": [
            9.45,
            13.87
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_021",
          "position": [
            11.12,
            0.0
          ],
          "width": 0.23,
          "depth": 0.23
        },
        {
          "id": "col_022",
          "position": [
            11.12,
            4.42
          ],
          "width": 0.23,
          "depth": 0.23
        }
      ]
    }
  ],
  "confidence": {
    "overall": 0.83,
    "bounding_box_fidelity": 1.0,
    "wall_connectivity": 1.0,
    "wall_coverage": 0.96,
    "openings_validity": 1.0,
    "room_dimensions_fidelity": 1.0,
    "inferred_elements_ratio": 0.0
  }
};

export const INITIAL_MATERIAL_ITEMS: MaterialQuantityItem[] = [
  {
    id: 'mat_1',
    materialName: 'Marble Flooring',
    totalArea: '42 m²',
    quantity: '45 m²',
    category: 'Finishes',
    rate: 1850,
    unit: 'm²',
    estimatedAmount: 83250,
    surfaceTag: 'marble',
  },
  {
    id: 'mat_2',
    materialName: 'Wall Paint (Textured)',
    totalArea: '86 m²',
    quantity: '18 L',
    category: 'Finishes',
    rate: 2600,
    unit: 'L',
    estimatedAmount: 46800,
    surfaceTag: 'paint',
  },
  {
    id: 'mat_3',
    materialName: 'Oak Wood Flooring',
    totalArea: '24 m²',
    quantity: '26 m²',
    category: 'Woodwork',
    rate: 3400,
    unit: 'm²',
    estimatedAmount: 88400,
    surfaceTag: 'wood',
  },
  {
    id: 'mat_4',
    materialName: 'Ceramic Bathroom Tiles',
    totalArea: '18 m²',
    quantity: '20 m²',
    category: 'Finishes',
    rate: 950,
    unit: 'm²',
    estimatedAmount: 19000,
    surfaceTag: 'tiles',
  },
  {
    id: 'mat_5',
    materialName: 'Ready-Mix Concrete (Grade M25)',
    totalArea: '65 m²',
    quantity: '3.2 m³',
    category: 'Structural',
    rate: 6800,
    unit: 'm³',
    estimatedAmount: 21760,
    surfaceTag: 'concrete',
  },
  {
    id: 'mat_6',
    materialName: 'TMT Steel Rebar (Fe 550D)',
    totalArea: 'Building Core',
    quantity: '5.2 Tons',
    category: 'Structural',
    rate: 64000,
    unit: 'Ton',
    estimatedAmount: 332800,
    surfaceTag: 'concrete',
  },
  {
    id: 'mat_7',
    materialName: 'Portland Pozzolana Cement',
    totalArea: 'Masonry & Slab',
    quantity: '380 Bags',
    category: 'Structural',
    rate: 395,
    unit: 'Bag',
    estimatedAmount: 150100,
    surfaceTag: 'concrete',
  },
  {
    id: 'mat_8',
    materialName: 'Coarse Sand (River Reti)',
    totalArea: 'Mortar & Concrete',
    quantity: '28 Tons',
    category: 'Raw Aggregate',
    rate: 1800,
    unit: 'Ton',
    estimatedAmount: 50400,
    surfaceTag: 'concrete',
  },
  {
    id: 'mat_9',
    materialName: 'Crushed Stone Aggregate (Gitti)',
    totalArea: 'Sub-base & RCC',
    quantity: '34 Tons',
    category: 'Raw Aggregate',
    rate: 1450,
    unit: 'Ton',
    estimatedAmount: 49300,
    surfaceTag: 'concrete',
  },
  {
    id: 'mat_10',
    materialName: 'Red Clay Bricks (First Class)',
    totalArea: 'Partition Walls',
    quantity: '9,500 Pcs',
    category: 'Masonry',
    rate: 11,
    unit: 'Pc',
    estimatedAmount: 104500,
    surfaceTag: 'paint',
  },
];

