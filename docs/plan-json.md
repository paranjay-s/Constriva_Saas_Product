# Plan JSON Data Contract

This document specifies the input PlanJSON format derived from architectural drawings in Constriva and how it maps to our internal framework-free `Plan` type in `frontend/src/viewer3d/types.ts`.

## 1. Input PlanJSON Format (Source Schema)

Units are in meters (`"m"`). Coordinates on 2D floor plans are `(x, y)` where `y` corresponds to depth/length on the building grid.

```json
{
  "version": 1,
  "units": "m",
  "scale_source": "dimension_label",
  "project_title": "Executive 2-BHK Modern Residence",
  "levels": [
    {
      "elevation": 0.0,
      "wall_height": 2.8,
      "walls": [
        {
          "id": "w_001",
          "start": [0.0, 0.0],
          "end": [4.27, 0.0],
          "thickness": 0.23,
          "height": 2.8,
          "kind": "exterior",
          "type": "exterior"
        }
      ],
      "openings": [
        {
          "id": "door_001",
          "wall_id": "w_001",
          "type": "door",
          "offset": 1.2,
          "width": 0.9,
          "height": 2.1,
          "sill": 0.0
        }
      ],
      "rooms": [
        {
          "id": "bed_master",
          "name": "MASTER BEDROOM 14' X 12'8\"",
          "dimensions": "14' X 12'8\"",
          "polygon": [
            [0.0, 7.92],
            [4.27, 7.92],
            [4.27, 11.89],
            [0.0, 11.89]
          ]
        }
      ],
      "columns": [
        {
          "id": "col_001",
          "position": [0.0, 0.0],
          "width": 0.23,
          "depth": 0.23
        }
      ]
    }
  ]
}
```

## 1a. Schema 2.0 fields

The model is defined once, in `backend/app/modules/plans/schemas.py` (`SCHEMA_VERSION = "2.0"`). Schema 2.0 only adds fields. No 1.x key was renamed or removed, so a 1.x document still validates and every reader of 1.x keys still finds them.

| Where | Field | Meaning |
|---|---|---|
| plan | `schema_version` | `"2.0"` |
| plan | `building_type` | `villa`, `apartment` or `other` |
| plan | `scale_source` | adds `scale_bar` and `stated_scale`; the 1.x values `scale_text` and `user_reference` stay valid |
| plan | `warnings` | plain-language warnings, e.g. implausible scale |
| plan | `parser` | which parser run produced the plan: PDF sha256, parser, prompt and model |
| level | `index`, `name` | position from the lowest floor (0) and the floor's printed title |
| level | `wall_height_source` | `stated` when the drawing gives the height, else `default` |
| room | `boq_kind` | how the material calculator counts the room: `indoor`, `semi_open`, `outdoor` or `void`. Starts from `kind`; parking and driveways are `outdoor`, a semi-open bathroom, kitchen or laundry is `indoor`. `kind` itself is never changed |
| room | `boq_type` | what the room is used for, for the material calculator: `BATH`, `KITCHEN`, `LAUNDRY`, `CIRC`, `LIVING`, `DINING`, `STORE`, `BED`, `STUDY` or `OTHER`. Only rooms whose `boq_kind` is `indoor`; `null` on every other kind |
| room | `height_m`, `is_double_height_void` | per-room ceiling height, when it differs from the level |
| wall | `is_exterior` | mirrors `kind` (`exterior` / `interior`); the model keeps the two in step |
| opening | `sill_height` | mirrors `sill`; the model keeps the two in step |
| opening | `position` | centre of the opening on its wall, derived from the wall and `offset` |

Notes:

- `wall_height` holds `2.8` when the drawing states no height (`wall_height_source: "default"`). The 3D viewer draws walls at that height; the material calculator uses its own standard ceiling height (3.35 m) instead.
- `offset` is measured along the wall from its `start` to the centre of the opening.
- Parser output uses stable ids: `L0-R01` (room), `L0-W01` (wall), `L0-O01` (opening), `L0-C01` (column), where the first number is the level index.
- `boq_type` and `type` are different keys with different owners. `boq_type` is written by the parser's normaliser from the keyword rules in `backend/app/modules/plans/room_types.py` (section 2 of [materials_formula_spec.md](materials_formula_spec.md)); the rules win, and the parser model's own answer is used only when they return `OTHER`. `type` belongs to the 3D adapter (`viewer3d/adapter/normalizePlan.ts`), which reads it as its own lowercase room type. Nothing in the parser or the calculator reads, writes or changes `type`.
- `boq_kind` and `kind` are different keys too. `kind` is what the 3D code reads (`PlanViewer.tsx`, `buildFloors.ts`) and the BOQ never changes it. `boq_kind` is derived next to it by the same module (section 2.1 of the spec), so a covered parking area can be semi-open in 3D and paved outdoor area in the bill.
- A plan stored before `boq_kind` or `boq_type` existed still calculates: the calculator derives both from the room's `kind` and name when a key is missing.
- Keys this schema does not define are kept when a stored plan is validated or upgraded, so keys other readers own (`room.type`, `wall.height`, `level.furniture`) survive.

## 2. Internal Target `Plan` Type (`frontend/src/viewer3d/types.ts`)

Units are strictly in **METERS**, coordinates map to Three.js world space:
- Plan `(x, y)` -> Three.js World `(x, 0, z)` with Y-up.

```ts
export type RoomType =
  | 'bedroom' | 'living' | 'drawing' | 'dining' | 'kitchen' | 'toilet' | 'wash'
  | 'puja' | 'parking' | 'balcony' | 'terrace' | 'store' | 'utility'
  | 'passage' | 'stairs' | 'other';

export interface Vec2 { x: number; y: number }

export interface Wall {
  id: string;
  a: Vec2; b: Vec2;
  thickness: number;
  height: number;
  kind: 'exterior' | 'interior';
}

export interface Opening {
  id: string;
  wallId: string;
  kind: 'door' | 'window' | 'slider' | 'arch';
  offset: number; // m from wall start to opening center
  width: number;
  height: number;
  sill: number;
}

export interface Room {
  id: string;
  type: RoomType;
  label?: string;
  polygon: Vec2[];
  dims?: { w: number; d: number };
}

export interface FurnitureItem {
  type: string;
  position: Vec2;
  rotation: number;
  size: { w: number; d: number; h: number };
}

export interface Plan {
  walls: Wall[];
  openings: Opening[];
  rooms: Room[];
  furniture?: FurnitureItem[];
  meta: { sourceUnit: 'ft' | 'm' | 'mm' };
}
```

