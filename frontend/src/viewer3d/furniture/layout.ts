// furniture/layout.ts
import type { Opening, Room, Vec2, Wall } from '../types';
import { distance, pointInPolygon } from '../utils/geometry';

export interface PlacedBox {
  center: Vec2; // in world X, Z
  width: number;
  depth: number;
  angle: number; // world rotation
}

export interface KeepOut {
  type: 'door' | 'path';
  center: Vec2;
  radius: number;
}

/**
 * Checks if two 2D oriented boxes overlap (Separating Axis Theorem)
 */
export function boxesOverlap(a: PlacedBox, b: PlacedBox): boolean {
  const getCorners = (box: PlacedBox): Vec2[] => {
    const cos = Math.cos(box.angle);
    const sin = Math.sin(box.angle);
    const hw = box.width / 2;
    const hd = box.depth / 2;
    return [
      { x: box.center.x + (-hw * cos - -hd * sin), y: box.center.y + (-hw * sin + -hd * cos) },
      { x: box.center.x + (hw * cos - -hd * sin), y: box.center.y + (hw * sin + -hd * cos) },
      { x: box.center.x + (hw * cos - hd * sin), y: box.center.y + (hw * sin + hd * cos) },
      { x: box.center.x + (-hw * cos - hd * sin), y: box.center.y + (-hw * sin + hd * cos) },
    ];
  };

  const cornersA = getCorners(a);
  const cornersB = getCorners(b);

  const getAxes = (corners: Vec2[]): Vec2[] => {
    return [
      { x: -(corners[1].y - corners[0].y), y: corners[1].x - corners[0].x },
      { x: -(corners[3].y - corners[0].y), y: corners[3].x - corners[0].x },
    ];
  };

  const axes = [...getAxes(cornersA), ...getAxes(cornersB)];

  for (const axis of axes) {
    const len = Math.hypot(axis.x, axis.y);
    if (len < 1e-5) continue;
    const nx = axis.x / len;
    const ny = axis.y / len;

    let minA = Infinity, maxA = -Infinity;
    for (const c of cornersA) {
      const p = c.x * nx + c.y * ny;
      if (p < minA) minA = p;
      if (p > maxA) maxA = p;
    }

    let minB = Infinity, maxB = -Infinity;
    for (const c of cornersB) {
      const p = c.x * nx + c.y * ny;
      if (p < minB) minB = p;
      if (p > maxB) maxB = p;
    }

    if (maxA < minB || maxB < minA) {
      return false; // Separating axis found: no overlap
    }
  }

  return true;
}

/**
 * Checks if a proposed box is completely inside the room and avoids keep-outs and other items
 */
export function canPlaceBox(
  box: PlacedBox,
  roomPolygon: Vec2[],
  placedBoxes: PlacedBox[],
  keepOuts: KeepOut[]
): boolean {
  // Check room polygon containment for all 4 corners + center
  const cos = Math.cos(box.angle);
  const sin = Math.sin(box.angle);
  const hw = box.width / 2;
  const hd = box.depth / 2;

  const testPoints: Vec2[] = [
    box.center,
    { x: box.center.x + (-hw * cos - -hd * sin), y: box.center.y + (-hw * sin + -hd * cos) },
    { x: box.center.x + (hw * cos - -hd * sin), y: box.center.y + (hw * sin + -hd * cos) },
    { x: box.center.x + (hw * cos - hd * sin), y: box.center.y + (hw * sin + hd * cos) },
    { x: box.center.x + (-hw * cos - hd * sin), y: box.center.y + (-hw * sin + hd * cos) },
  ];

  for (const pt of testPoints) {
    if (!pointInPolygon(pt, roomPolygon)) {
      return false;
    }
  }

  // Check keep-out zones (door swings and 0.6m clear pathways)
  for (const ko of keepOuts) {
    if (distance(box.center, ko.center) < ko.radius + Math.min(box.width, box.depth) / 2) {
      return false;
    }
  }

  // Check overlap with existing placed furniture
  for (const placed of placedBoxes) {
    if (boxesOverlap(box, placed)) {
      return false;
    }
  }

  return true;
}

/**
 * Computes door keep-out zones for a room
 */
export function computeRoomKeepOuts(
  _room: Room,
  walls: Wall[],
  openings: Opening[]
): KeepOut[] {
  const keepOuts: KeepOut[] = [];

  for (const op of openings) {
    if (op.kind !== 'door') continue;
    const wall = walls.find((w) => w.id === op.wallId);
    if (!wall) continue;

    // Calculate door world position
    const wallLen = distance(wall.a, wall.b);
    if (wallLen < 0.1) continue;
    const t = Math.max(0, Math.min(1, op.offset / wallLen));
    const doorPos: Vec2 = {
      x: wall.a.x + (wall.b.x - wall.a.x) * t,
      y: wall.a.y + (wall.b.y - wall.a.y) * t,
    };

    // Keep out radius = door width + 0.5m clearance
    keepOuts.push({
      type: 'door',
      center: doorPos,
      radius: op.width + 0.45,
    });
  }

  return keepOuts;
}
