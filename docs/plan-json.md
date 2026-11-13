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

