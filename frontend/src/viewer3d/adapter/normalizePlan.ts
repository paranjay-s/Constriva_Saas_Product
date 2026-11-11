// adapter/normalizePlan.ts
import type { Opening, Plan, Room, RoomType, Vec2, Wall } from '../types';
import { parseFtIn, FT_TO_M } from '../utils/units';

export function normalizeRoomType(nameOrId: string = ''): RoomType {
  const s = nameOrId.toUpperCase();
  if (s.includes('BED') || s.includes('MBR')) return 'bedroom';
  if (s.includes('LIV')) return 'living';
  if (s.includes('DRG') || s.includes('DRAW')) return 'drawing';
  if (s.includes('DIN')) return 'dining';
  if (s.includes('KIT')) return 'kitchen';
  if (s.includes('TOI') || s.includes('WC') || s.includes('BATH')) return 'toilet';
  if (s.includes('WASH')) return 'wash';
  if (s.includes('PUJA') || s.includes('POOJA') || s.includes('MANDIR')) return 'puja';
  if (s.includes('PARK') || s.includes('GARAGE') || s.includes('CAR')) return 'parking';
  if (s.includes('BALCONY') || s.includes('TERRACE') || s.includes('DECK') || s.includes('SITOUT')) return 'balcony';
  if (s.includes('STORE')) return 'store';
  if (s.includes('STAIR')) return 'stairs';
  if (s.includes('PASS') || s.includes('FOYER') || s.includes('HALL') || s.includes('CORRIDOR')) return 'passage';
  if (s.includes('UTIL')) return 'utility';
  return 'other';
}

function extractPoint(pt: any): [number, number] | null {
  if (!pt) return null;
  if (Array.isArray(pt) && pt.length >= 2) {
    const x = Number(pt[0]);
    const y = Number(pt[1]);
    if (isFinite(x) && isFinite(y)) return [x, y];
  }
  if (typeof pt === 'object') {
    const x = Number(pt.x ?? pt.X ?? pt.u ?? pt.left);
    const y = Number(pt.y ?? pt.Y ?? pt.v ?? pt.top);
    if (isFinite(x) && isFinite(y)) return [x, y];
  }
  return null;
}

/**
 * Normalizes any external PlanJSON into the framework-free, meters-based Plan data model.
 */
export function normalizePlan(raw: any): Plan {
  if (!raw) {
    return {
      walls: [],
      openings: [],
      rooms: [],
      meta: { sourceUnit: 'm' },
    };
  }

  // Detect unit multiplier to convert everything once to meters
  const rawUnits = (raw.units || 'm').toLowerCase();
  let unitMultiplier = 1.0;
  if (rawUnits === 'ft' || rawUnits === 'feet') {
    unitMultiplier = FT_TO_M;
  } else if (rawUnits === 'mm' || rawUnits === 'millimeter') {
    unitMultiplier = 0.001;
  } else if (rawUnits === 'cm') {
    unitMultiplier = 0.01;
  }

  const level = (raw.levels && raw.levels[0]) ? raw.levels[0] : raw;
  const rawWalls = Array.isArray(level.walls) ? level.walls : [];
  const rawRooms = Array.isArray(level.rooms) ? level.rooms : [];
  const rawOpenings = Array.isArray(level.openings) ? level.openings : [];
  const rawFurniture = Array.isArray(level.furniture) ? level.furniture : Array.isArray(raw.furniture) ? raw.furniture : undefined;

  // 1. Calculate raw bounding box
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  for (const w of rawWalls) {
    const pA = extractPoint(w.start ?? w.a ?? w.p1 ?? w.from);
    const pB = extractPoint(w.end ?? w.b ?? w.p2 ?? w.to);
    if (pA && pB) {
      minX = Math.min(minX, pA[0] * unitMultiplier, pB[0] * unitMultiplier);
      maxX = Math.max(maxX, pA[0] * unitMultiplier, pB[0] * unitMultiplier);
      minY = Math.min(minY, pA[1] * unitMultiplier, pB[1] * unitMultiplier);
      maxY = Math.max(maxY, pA[1] * unitMultiplier, pB[1] * unitMultiplier);
    }
  }

  for (const r of rawRooms) {
    const poly = Array.isArray(r.polygon) ? r.polygon : Array.isArray(r.corners) ? r.corners : [];
    for (const p of poly) {
      const pt = extractPoint(p);
      if (pt) {
        minX = Math.min(minX, pt[0] * unitMultiplier);
        maxX = Math.max(maxX, pt[0] * unitMultiplier);
        minY = Math.min(minY, pt[1] * unitMultiplier);
        maxY = Math.max(maxY, pt[1] * unitMultiplier);
      }
    }
  }

  if (minX === Infinity) {
    minX = 0;
    maxX = 10;
    minY = 0;
    maxY = 10;
  }

  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;

  // 2. Normalize and re-center rooms
  const rooms: Room[] = [];
  for (let idx = 0; idx < rawRooms.length; idx++) {
    const r = rawRooms[idx];
    const polyRaw = Array.isArray(r.polygon) ? r.polygon : Array.isArray(r.corners) ? r.corners : [];
    if (polyRaw.length < 3) continue;

    // Filter repeated consecutive or closing points
    const polygon: Vec2[] = [];
    for (let i = 0; i < polyRaw.length; i++) {
      const pt = extractPoint(polyRaw[i]);
      if (!pt) continue;
      const px = pt[0] * unitMultiplier - centerX;
      const py = pt[1] * unitMultiplier - centerY;
      if (polygon.length > 0) {
        const prev = polygon[polygon.length - 1];
        if (Math.hypot(px - prev.x, py - prev.y) < 1e-4) continue;
      }
      polygon.push({ x: px, y: py });
    }

    // Drop repeated last point if it equals the first
    if (polygon.length >= 4) {
      const first = polygon[0];
      const last = polygon[polygon.length - 1];
      if (Math.hypot(first.x - last.x, first.y - last.y) < 1e-4) {
        polygon.pop();
      }
    }

    if (polygon.length < 3) continue;

    const label = r.name || r.label || `Room ${idx + 1}`;
    const dimsStr = r.dimensions || r.dim || label;
    const dims = parseFtIn(dimsStr) || undefined;
    const rType = r.type && typeof r.type === 'string' ? (r.type as RoomType) : normalizeRoomType(`${label} ${r.id || ''}`);

    rooms.push({
      id: r.id || `room_${idx + 1}`,
      type: rType,
      label,
      polygon,
      dims,
    });
  }

  // 3. Normalize and re-center walls
  const walls: Wall[] = [];
  const wallMap = new Map<string, Wall>();

  for (let idx = 0; idx < rawWalls.length; idx++) {
    const w = rawWalls[idx];
    const pA = extractPoint(w.start ?? w.a ?? w.p1 ?? w.from);
    const pB = extractPoint(w.end ?? w.b ?? w.p2 ?? w.to);
    if (!pA || !pB) continue;

    const ax = pA[0] * unitMultiplier - centerX;
    const ay = pA[1] * unitMultiplier - centerY;
    const bx = pB[0] * unitMultiplier - centerX;
    const by = pB[1] * unitMultiplier - centerY;

    const len = Math.hypot(bx - ax, by - ay);
    if (len < 0.05) continue;

    const thickRaw = w.thickness ? w.thickness * unitMultiplier : 0.2;
    const heightRaw = w.height ? w.height * unitMultiplier : (level.wall_height || 2.9);

    // Exterior determination if missing
    let kind: 'exterior' | 'interior' = 'interior';
    if (w.kind === 'exterior' || w.type === 'exterior') {
      kind = 'exterior';
    } else if (w.kind === 'interior' || w.type === 'interior') {
      kind = 'interior';
    } else {
      // Determine if wall is on exterior bounding box perimeter
      const eps = 0.25;
      const touchesMinX = Math.abs(ax - (minX - centerX)) < eps && Math.abs(bx - (minX - centerX)) < eps;
      const touchesMaxX = Math.abs(ax - (maxX - centerX)) < eps && Math.abs(bx - (maxX - centerX)) < eps;
      const touchesMinY = Math.abs(ay - (minY - centerY)) < eps && Math.abs(by - (minY - centerY)) < eps;
      const touchesMaxY = Math.abs(ay - (maxY - centerY)) < eps && Math.abs(by - (maxY - centerY)) < eps;
      if (touchesMinX || touchesMaxX || touchesMinY || touchesMaxY) {
        kind = 'exterior';
      }
    }

    const wallObj: Wall = {
      id: w.id || `w_${idx + 1}`,
      a: { x: ax, y: ay },
      b: { x: bx, y: by },
      thickness: thickRaw > 0.05 ? thickRaw : kind === 'exterior' ? 0.23 : 0.115,
      height: heightRaw,
      kind,
    };

    walls.push(wallObj);
    wallMap.set(wallObj.id, wallObj);
  }

  // 3b. Automatic Boundary & Partition Wall Synthesizer
  // Guarantees that adjacent rooms ALWAYS have a solid dividing partition wall!
  function isSegmentCoveredByWalls(
    p1: Vec2,
    p2: Vec2,
    existingWalls: Wall[],
    distTolerance = 0.2
  ): boolean {
    const segLen = Math.hypot(p2.x - p1.x, p2.y - p1.y);
    if (segLen < 0.2) return true;

    const segDx = (p2.x - p1.x) / segLen;
    const segDy = (p2.y - p1.y) / segLen;

    for (const w of existingWalls) {
      const wLen = Math.hypot(w.b.x - w.a.x, w.b.y - w.a.y);
      if (wLen < 0.2) continue;

      const wDx = (w.b.x - w.a.x) / wLen;
      const wDy = (w.b.y - w.a.y) / wLen;

      const dot = Math.abs(segDx * wDx + segDy * wDy);
      if (dot < 0.95) continue;

      const toP1x = p1.x - w.a.x;
      const toP1y = p1.y - w.a.y;
      const perpDist = Math.abs(toP1x * (-wDy) + toP1y * wDx);
      if (perpDist > distTolerance) continue;

      const t1 = toP1x * wDx + toP1y * wDy;
      const toP2x = p2.x - w.a.x;
      const toP2y = p2.y - w.a.y;
      const t2 = toP2x * wDx + toP2y * wDy;

      const minT = Math.min(t1, t2);
      const maxT = Math.max(t1, t2);

      const overlap = Math.max(0, Math.min(maxT, wLen) - Math.max(minT, 0));
      if (overlap >= Math.min(segLen * 0.6, wLen * 0.6) || overlap > 0.4) {
        return true;
      }
    }
    return false;
  }

  const defaultHeight = level.wall_height || 2.85;
  let synthCounter = 1;

  for (let i = 0; i < rooms.length; i++) {
    const r1 = rooms[i];
    const poly1 = r1.polygon;
    if (poly1.length < 3) continue;

    for (let e1 = 0; e1 < poly1.length; e1++) {
      const p1 = poly1[e1];
      const p2 = poly1[(e1 + 1) % poly1.length];
      const edgeLen = Math.hypot(p2.x - p1.x, p2.y - p1.y);
      if (edgeLen < 0.3) continue;

      let sharedWithOtherRoom = false;

      for (let j = 0; j < rooms.length; j++) {
        if (i === j) continue;
        const r2 = rooms[j];
        const poly2 = r2.polygon;
        if (poly2.length < 3) continue;

        for (let e2 = 0; e2 < poly2.length; e2++) {
          const q1 = poly2[e2];
          const q2 = poly2[(e2 + 1) % poly2.length];
          const qLen = Math.hypot(q2.x - q1.x, q2.y - q1.y);
          if (qLen < 0.3) continue;

          const dx1 = (p2.x - p1.x) / edgeLen;
          const dy1 = (p2.y - p1.y) / edgeLen;
          const dx2 = (q2.x - q1.x) / qLen;
          const dy2 = (q2.y - q1.y) / qLen;

          const dot = Math.abs(dx1 * dx2 + dy1 * dy2);
          if (dot < 0.95) continue;

          const perp = Math.abs((q1.x - p1.x) * (-dy1) + (q1.y - p1.y) * dx1);
          if (perp > 0.2) continue;

          const tQ1 = (q1.x - p1.x) * dx1 + (q1.y - p1.y) * dy1;
          const tQ2 = (q2.x - p1.x) * dx1 + (q2.y - p1.y) * dy1;
          const minQ = Math.min(tQ1, tQ2);
          const maxQ = Math.max(tQ1, tQ2);

          const overlapStart = Math.max(0, minQ);
          const overlapEnd = Math.min(edgeLen, maxQ);
          const overlapLen = overlapEnd - overlapStart;

          if (overlapLen > 0.35) {
            sharedWithOtherRoom = true;
            // Prevent duplicate partition walls when checked from the other room
            if (i < j) {
              const startPt: Vec2 = {
                x: p1.x + dx1 * overlapStart,
                y: p1.y + dy1 * overlapStart,
              };
              const endPt: Vec2 = {
                x: p1.x + dx1 * overlapEnd,
                y: p1.y + dy1 * overlapEnd,
              };

              if (!isSegmentCoveredByWalls(startPt, endPt, walls)) {
                const synthWall: Wall = {
                  id: `synth_partition_${r1.id}_${r2.id}_${synthCounter++}`,
                  a: startPt,
                  b: endPt,
                  thickness: 0.12,
                  height: defaultHeight,
                  kind: 'interior',
                };
                walls.push(synthWall);
                wallMap.set(synthWall.id, synthWall);
              }
            }
          }
        }
      }

      // If an indoor room edge is not shared with any other room, ensure an exterior wall covers it
      const isIndoor = r1.type !== 'balcony' && r1.type !== 'terrace' && r1.type !== 'parking';
      if (!sharedWithOtherRoom && isIndoor) {
        if (!isSegmentCoveredByWalls(p1, p2, walls, 0.22)) {
          const synthExterior: Wall = {
            id: `synth_exterior_${r1.id}_${synthCounter++}`,
            a: { x: p1.x, y: p1.y },
            b: { x: p2.x, y: p2.y },
            thickness: 0.23,
            height: defaultHeight,
            kind: 'exterior',
          };
          walls.push(synthExterior);
          wallMap.set(synthExterior.id, synthExterior);
        }
      }
    }
  }

  // 4. Normalize openings
  const openings: Opening[] = [];
  if (rawOpenings.length === 0) {
    console.warn('[Viewer3D normalizePlan] Plan has no openings in data; solid walls will be rendered.');
  }

  for (let idx = 0; idx < rawOpenings.length; idx++) {
    const o = rawOpenings[idx];
    const wall = wallMap.get(o.wall_id);
    if (!wall) continue;

    const wallLen = Math.hypot(wall.b.x - wall.a.x, wall.b.y - wall.a.y);
    const oType = (o.type || o.kind || 'door').toLowerCase();
    let kind: 'door' | 'window' | 'slider' | 'arch' = 'door';
    if (oType.includes('window') || oType.includes('win')) kind = 'window';
    else if (oType.includes('slider') || oType.includes('slide')) kind = 'slider';
    else if (oType.includes('arch')) kind = 'arch';

    const wRaw = o.width ? o.width * unitMultiplier : 0.9;
    const hRaw = o.height ? o.height * unitMultiplier : kind === 'window' ? 1.4 : 2.1;
    let sillRaw = o.sill !== undefined ? o.sill * unitMultiplier : kind === 'window' ? 0.9 : 0.0;

    // Offset in meters from wall start to opening center
    let offset = o.offset !== undefined ? o.offset * unitMultiplier : wallLen / 2;
    // If offset was given to left edge, convert to center
    if (o.offset_type === 'edge') {
      offset += wRaw / 2;
    }

    // Clamp inside wall bounds with margin
    const minCenter = wRaw / 2 + 0.05;
    const maxCenter = wallLen - wRaw / 2 - 0.05;
    if (maxCenter > minCenter) {
      offset = Math.max(minCenter, Math.min(maxCenter, offset));
    }

    openings.push({
      id: o.id || `op_${idx + 1}`,
      wallId: wall.id,
      kind,
      offset,
      width: Math.min(wRaw, wallLen - 0.1),
      height: hRaw,
      sill: Math.max(0, sillRaw),
    });
  }

  // 5. Normalize furniture if present in input
  const furniture: Plan['furniture'] = rawFurniture
    ? rawFurniture.map((f: any) => ({
        type: f.type || 'unknown',
        position: {
          x: f.position[0] * unitMultiplier - centerX,
          y: f.position[1] * unitMultiplier - centerY,
        },
        rotation: f.rotation || 0,
        size: {
          w: f.size?.w || f.size?.[0] || 1,
          d: f.size?.d || f.size?.[1] || 1,
          h: f.size?.h || f.size?.[2] || 0.8,
        },
      }))
    : undefined;

  return {
    walls,
    openings,
    rooms,
    furniture,
    meta: { sourceUnit: rawUnits === 'ft' || rawUnits === 'feet' ? 'ft' : 'm' },
  };
}

