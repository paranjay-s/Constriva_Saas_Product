import type { Room, Wall } from '../../../types';

interface Segment {
  start: [number, number];
  end: [number, number];
  roomId: string;
  isOutdoor: boolean;
}

/**
 * Ensures that all rooms have enclosing walls.
 * If interior partition walls are missing or incomplete in the plan data,
 * this function detects shared boundaries between adjacent rooms
 * and synthesizes interior wall meshes (thickness: 0.12m).
 */
export function ensureCompleteWalls(walls: Wall[], rooms: Room[]): Wall[] {
  const existingInteriorCount = walls.filter(
    (w) => w.kind === 'interior' || (w as any).type === 'interior'
  ).length;

  // If there are already at least 8 interior walls, the plan is structurally complete
  if (existingInteriorCount >= 8 && walls.length >= 15) {
    return walls;
  }

  const resultWalls: Wall[] = [...walls];
  const wallIdSet = new Set(walls.map((w) => w.id));

  // Helper to check if a line segment is already covered by existing walls
  const isSegmentCovered = (x1: number, y1: number, x2: number, y2: number): boolean => {
    const isH = Math.abs(y1 - y2) < 0.08;
    const isV = Math.abs(x1 - x2) < 0.08;

    for (const w of resultWalls) {
      const wx1 = Math.min(w.start[0], w.end[0]);
      const wx2 = Math.max(w.start[0], w.end[0]);
      const wy1 = Math.min(w.start[1], w.end[1]);
      const wy2 = Math.max(w.start[1], w.end[1]);

      if (isH && Math.abs(wy1 - wy2) < 0.08 && Math.abs(y1 - wy1) < 0.18) {
        const overlap = Math.max(0, Math.min(x2, wx2) - Math.max(x1, wx1));
        if (overlap > 0.35) return true;
      } else if (isV && Math.abs(wx1 - wx2) < 0.08 && Math.abs(x1 - wx1) < 0.18) {
        const overlap = Math.max(0, Math.min(y2, wy2) - Math.max(y1, wy1));
        if (overlap > 0.35) return true;
      }
    }
    return false;
  };

  // Collect polygon edges
  const hSegments: Segment[] = [];
  const vSegments: Segment[] = [];

  for (const r of rooms) {
    const pts = r.polygon || [];
    if (pts.length < 3) continue;

    const lowerName = (r.name || '').toLowerCase();
    const isOutdoor =
      r.kind === 'outdoor' ||
      r.kind === 'void' ||
      lowerName.includes('lawn') ||
      lowerName.includes('open') ||
      lowerName.includes('shaft') ||
      lowerName.includes('duct');

    for (let i = 0; i < pts.length; i++) {
      const p1 = pts[i];
      const p2 = pts[(i + 1) % pts.length];
      const x1 = Math.round(p1[0] * 100) / 100;
      const y1 = Math.round(p1[1] * 100) / 100;
      const x2 = Math.round(p2[0] * 100) / 100;
      const y2 = Math.round(p2[1] * 100) / 100;

      if (Math.abs(x1 - x2) < 0.05 && Math.abs(y1 - y2) < 0.05) continue;

      if (Math.abs(y1 - y2) < 0.08) {
        // Horizontal
        const minX = Math.min(x1, x2);
        const maxX = Math.max(x1, x2);
        hSegments.push({
          start: [minX, (y1 + y2) / 2],
          end: [maxX, (y1 + y2) / 2],
          roomId: r.id,
          isOutdoor,
        });
      } else if (Math.abs(x1 - x2) < 0.08) {
        // Vertical
        const minY = Math.min(y1, y2);
        const maxY = Math.max(y1, y2);
        vSegments.push({
          start: [(x1 + x2) / 2, minY],
          end: [(x1 + x2) / 2, maxY],
          roomId: r.id,
          isOutdoor,
        });
      }
    }
  }

  let counter = 1;

  // Process horizontal segments: group by approximate Y
  const hGroups = new Map<number, Segment[]>();
  for (const s of hSegments) {
    const key = Math.round(s.start[1] * 10) / 10;
    if (!hGroups.has(key)) hGroups.set(key, []);
    hGroups.get(key)!.push(s);
  }

  for (const [, group] of hGroups.entries()) {
    const xs = Array.from(
      new Set([...group.map((s) => s.start[0]), ...group.map((s) => s.end[0])])
    ).sort((a, b) => a - b);

    for (let i = 0; i < xs.length - 1; i++) {
      const xa = xs[i];
      const xb = xs[i + 1];
      if (xb - xa < 0.25) continue;
      const mid = (xa + xb) / 2;

      const matching = group.filter((s) => s.start[0] <= mid && s.end[0] >= mid);
      if (matching.length === 0) continue;

      const allOutdoor = matching.every((s) => s.isOutdoor);
      if (allOutdoor) continue;

      const yMean = matching.reduce((sum, s) => sum + s.start[1], 0) / matching.length;
      if (isSegmentCovered(xa, yMean, xb, yMean)) continue;

      const rIds = Array.from(new Set(matching.map((s) => s.roomId)));
      const isInterior = rIds.length > 1 && !matching.some((s) => s.isOutdoor);

      const id = `syn_wall_h_${counter++}`;
      if (!wallIdSet.has(id)) {
        wallIdSet.add(id);
        resultWalls.push({
          id,
          start: [Math.round(xa * 100) / 100, Math.round(yMean * 100) / 100],
          end: [Math.round(xb * 100) / 100, Math.round(yMean * 100) / 100],
          thickness: isInterior ? 0.12 : 0.23,
          height: 2.8,
          kind: isInterior ? 'interior' : 'exterior',
          type: isInterior ? 'interior' : 'exterior',
          length: Math.round((xb - xa) * 100) / 100,
          inferred: true,
          rooms: rIds,
        } as any);
      }
    }
  }

  // Process vertical segments: group by approximate X
  const vGroups = new Map<number, Segment[]>();
  for (const s of vSegments) {
    const key = Math.round(s.start[0] * 10) / 10;
    if (!vGroups.has(key)) vGroups.set(key, []);
    vGroups.get(key)!.push(s);
  }

  for (const [, group] of vGroups.entries()) {
    const ys = Array.from(
      new Set([...group.map((s) => s.start[1]), ...group.map((s) => s.end[1])])
    ).sort((a, b) => a - b);

    for (let i = 0; i < ys.length - 1; i++) {
      const ya = ys[i];
      const yb = ys[i + 1];
      if (yb - ya < 0.25) continue;
      const mid = (ya + yb) / 2;

      const matching = group.filter((s) => s.start[1] <= mid && s.end[1] >= mid);
      if (matching.length === 0) continue;

      const allOutdoor = matching.every((s) => s.isOutdoor);
      if (allOutdoor) continue;

      const xMean = matching.reduce((sum, s) => sum + s.start[0], 0) / matching.length;
      if (isSegmentCovered(xMean, ya, xMean, yb)) continue;

      const rIds = Array.from(new Set(matching.map((s) => s.roomId)));
      const isInterior = rIds.length > 1 && !matching.some((s) => s.isOutdoor);

      const id = `syn_wall_v_${counter++}`;
      if (!wallIdSet.has(id)) {
        wallIdSet.add(id);
        resultWalls.push({
          id,
          start: [Math.round(xMean * 100) / 100, Math.round(ya * 100) / 100],
          end: [Math.round(xMean * 100) / 100, Math.round(yb * 100) / 100],
          thickness: isInterior ? 0.12 : 0.23,
          height: 2.8,
          kind: isInterior ? 'interior' : 'exterior',
          type: isInterior ? 'interior' : 'exterior',
          length: Math.round((yb - ya) * 100) / 100,
          inferred: true,
          rooms: rIds,
        } as any);
      }
    }
  }

  return resultWalls;
}

/**
 * Filters out stray rooms whose coordinates lie outside the main building footprint.
 * Prevents floating rogue slabs from appearing in the void behind the rear wall.
 */
export function filterValidRooms(rooms: Room[], walls: Wall[]): Room[] {
  if (rooms.length <= 1) return rooms;

  // Determine bounding box of the building from walls or the majority cluster
  let minX = Infinity;
  let maxX = -Infinity;
  let minZ = Infinity;
  let maxZ = -Infinity;

  for (const w of walls) {
    minX = Math.min(minX, w.start[0], w.end[0]);
    maxX = Math.max(maxX, w.start[0], w.end[0]);
    minZ = Math.min(minZ, w.start[1], w.end[1]);
    maxZ = Math.max(maxZ, w.start[1], w.end[1]);
  }

  // If walls bounding box is not valid, calculate from room polygons
  if (minX === Infinity || maxX - minX < 2) {
    const allX = rooms.flatMap((r) => (r.polygon || []).map((p) => p[0]));
    const allZ = rooms.flatMap((r) => (r.polygon || []).map((p) => p[1]));
    if (allX.length === 0) return rooms;
    minX = Math.min(...allX);
    maxX = Math.max(...allX);
    minZ = Math.min(...allZ);
    maxZ = Math.max(...allZ);
  }

  // Strict tolerance: 0.10m (to allow for exterior wall thickness alignment)
  const margin = 0.1;
  const boundMinX = minX - margin;
  const boundMaxX = maxX + margin;
  const boundMinZ = minZ - margin;
  const boundMaxZ = maxZ + margin;

  return rooms.filter((r) => {
    const pts = r.polygon || [];
    if (pts.length < 3) return false;

    // Calculate center
    const cx = pts.reduce((sum, p) => sum + p[0], 0) / pts.length;
    const cz = pts.reduce((sum, p) => sum + p[1], 0) / pts.length;

    // Room center must be within the building bounding box
    if (cx < boundMinX || cx > boundMaxX || cz < boundMinZ || cz > boundMaxZ) {
      return false;
    }

    // Room cannot lie completely outside the exterior wall perimeter
    const allOutside = pts.every(
      ([x, z]) => x < minX - 0.1 || x > maxX + 0.1 || z < minZ - 0.1 || z > maxZ + 0.1
    );
    if (allOutside) return false;

    return true;
  });
}
