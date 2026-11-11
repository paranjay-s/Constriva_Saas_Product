// types.ts — units are METERS, Y-up in Three.js, plan (x, y) -> world (x, z)

export type RoomType =
  | 'bedroom'
  | 'living'
  | 'drawing'
  | 'dining'
  | 'kitchen'
  | 'toilet'
  | 'wash'
  | 'puja'
  | 'parking'
  | 'balcony'
  | 'terrace'
  | 'store'
  | 'utility'
  | 'passage'
  | 'stairs'
  | 'other';

export interface Vec2 {
  x: number;
  y: number;
}

export interface Wall {
  id: string;
  a: Vec2;
  b: Vec2; // centerline endpoints
  thickness: number; // m; default 0.23 exterior, 0.115 interior
  height: number; // m; default 2.9
  kind: 'exterior' | 'interior';
}

export interface Opening {
  id: string;
  wallId: string;
  kind: 'door' | 'window' | 'slider' | 'arch';
  offset: number; // m from wall start to opening CENTER
  width: number; // m
  height: number; // m
  sill: number; // m above floor (door: 0, window: ~0.9, slider: 0)
}

export interface Room {
  id: string;
  type: RoomType;
  label?: string; // raw label, e.g. "BEDROOM 10'2\"X12'"
  polygon: Vec2[]; // closed ring, no repeated last point
  dims?: { w: number; d: number }; // m, from the label if present
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

export type ViewMode = 'iso' | 'top';
export type WallMode = 'auto' | 'full' | 'low';

export interface ViewerOptions {
  initialView?: ViewMode;
  initialWallMode?: WallMode;
  showFurniture?: boolean;
  showLabels?: boolean;
  onViewChange?: (view: ViewMode) => void;
  onRoomSelect?: (roomId: string | null) => void;
  highlightMaterialTag?: string | null;
}

export interface ViewerApi {
  loadPlan(plan: Plan): void;
  setView(v: ViewMode): void;
  setFurniture(on: boolean): void;
  setLabels(on: boolean): void;
  setWallMode(m: WallMode): void;
  setMaterialHighlight(tag: string | null): void;
  selectRoom(roomId: string | null): void;
  screenshot(): string; // PNG data URL
  dispose(): void;
}

