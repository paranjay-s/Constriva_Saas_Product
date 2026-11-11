// utils/geometry.ts
import type { Vec2 } from '../types';

export function distance(a: Vec2, b: Vec2): number {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  return Math.hypot(dx, dy);
}

/**
 * Calculates absolute signed area of a 2D polygon using Shoelace formula
 */
export function polygonArea(polygon: Vec2[]): number {
  const n = polygon.length;
  if (n < 3) return 0;
  let area = 0;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    area += polygon[i].x * polygon[j].y;
    area -= polygon[j].x * polygon[i].y;
  }
  return Math.abs(area) / 2;
}

/**
 * Computes polygon centroid
 */
export function polygonCentroid(polygon: Vec2[]): Vec2 {
  const n = polygon.length;
  if (n === 0) return { x: 0, y: 0 };
  if (n === 1) return { ...polygon[0] };
  if (n === 2) return { x: (polygon[0].x + polygon[1].x) / 2, y: (polygon[0].y + polygon[1].y) / 2 };

  let cx = 0;
  let cy = 0;
  let signedArea = 0;

  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    const a = polygon[i].x * polygon[j].y - polygon[j].x * polygon[i].y;
    signedArea += a;
    cx += (polygon[i].x + polygon[j].x) * a;
    cy += (polygon[i].y + polygon[j].y) * a;
  }

  signedArea *= 0.5;
  if (Math.abs(signedArea) < 1e-6) {
    // Fallback to arithmetic mean for degenerate polygons
    const sx = polygon.reduce((s, p) => s + p.x, 0) / n;
    const sy = polygon.reduce((s, p) => s + p.y, 0) / n;
    return { x: sx, y: sy };
  }

  return {
    x: cx / (6 * signedArea),
    y: cy / (6 * signedArea),
  };
}

/**
 * Axis-aligned bounding box of a polygon
 */
export function polygonBounds(polygon: Vec2[]): {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
  width: number;
  depth: number;
} {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  for (const p of polygon) {
    if (p.x < minX) minX = p.x;
    if (p.x > maxX) maxX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.y > maxY) maxY = p.y;
  }

  if (minX === Infinity) {
    return { minX: 0, maxX: 0, minY: 0, maxY: 0, width: 0, depth: 0 };
  }

  return {
    minX,
    maxX,
    minY,
    maxY,
    width: maxX - minX,
    depth: maxY - minY,
  };
}

/**
 * Tests whether a point lies inside a polygon
 */
export function pointInPolygon(point: Vec2, polygon: Vec2[]): boolean {
  let inside = false;
  const n = polygon.length;
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const xi = polygon[i].x;
    const yi = polygon[i].y;
    const xj = polygon[j].x;
    const yj = polygon[j].y;

    const intersect =
      yi > point.y !== yj > point.y &&
      point.x < ((xj - xi) * (point.y - yi)) / (yj - yi + 1e-9) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

export interface OBB {
  center: Vec2;
  width: number; // along local primary axis
  depth: number; // along local secondary axis
  angle: number; // radians of primary axis relative to world X
  axes: [Vec2, Vec2]; // unit vectors
  sides: [
    { a: Vec2; b: Vec2; len: number }, // South side
    { a: Vec2; b: Vec2; len: number }, // East side
    { a: Vec2; b: Vec2; len: number }, // North side
    { a: Vec2; b: Vec2; len: number }, // West side
  ];
}

/**
 * Computes minimum-area Oriented Bounding Box (OBB) for a polygon.
 * Tries every edge direction to find optimal fit for furniture layout.
 */
export function minimumAreaOBB(polygon: Vec2[]): OBB {
  const n = polygon.length;
  if (n < 3) {
    const b = polygonBounds(polygon);
    const center = { x: (b.minX + b.maxX) / 2, y: (b.minY + b.maxY) / 2 };
    const w = Math.max(0.1, b.width);
    const d = Math.max(0.1, b.depth);
    return createOBB(center, w, d, 0);
  }

  let minArea = Infinity;
  let bestAngle = 0;
  let bestCenter: Vec2 = { x: 0, y: 0 };
  let bestW = 0;
  let bestD = 0;

  for (let i = 0; i < n; i++) {
    const p1 = polygon[i];
    const p2 = polygon[(i + 1) % n];
    const edge = { x: p2.x - p1.x, y: p2.y - p1.y };
    const edgeLen = Math.hypot(edge.x, edge.y);
    if (edgeLen < 1e-4) continue;

    const angle = Math.atan2(edge.y, edge.x);
    const cos = Math.cos(-angle);
    const sin = Math.sin(-angle);

    let minU = Infinity;
    let maxU = -Infinity;
    let minV = Infinity;
    let maxV = -Infinity;

    for (const p of polygon) {
      const u = p.x * cos - p.y * sin;
      const v = p.x * sin + p.y * cos;
      if (u < minU) minU = u;
      if (u > maxU) maxU = u;
      if (v < minV) minV = v;
      if (v > maxV) maxV = v;
    }

    const w = maxU - minU;
    const d = maxV - minV;
    const area = w * d;

    if (area < minArea) {
      minArea = area;
      bestAngle = angle;
      bestW = w;
      bestD = d;
      const midU = (minU + maxU) / 2;
      const midV = (minV + maxV) / 2;
      bestCenter = {
        x: midU * Math.cos(angle) - midV * Math.sin(angle),
        y: midU * Math.sin(angle) + midV * Math.cos(angle),
      };
    }
  }

  // Ensure width >= depth for canonical orientation
  if (bestW < bestD) {
    const tmp = bestW;
    bestW = bestD;
    bestD = tmp;
    bestAngle += Math.PI / 2;
  }

  return createOBB(bestCenter, bestW, bestD, bestAngle);
}

function createOBB(center: Vec2, width: number, depth: number, angle: number): OBB {
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  const u: Vec2 = { x: cos, y: sin }; // primary axis unit vector
  const v: Vec2 = { x: -sin, y: cos }; // secondary axis unit vector

  const hw = width / 2;
  const hd = depth / 2;

  // 4 corners
  const c0: Vec2 = { x: center.x - u.x * hw - v.x * hd, y: center.y - u.y * hw - v.y * hd };
  const c1: Vec2 = { x: center.x + u.x * hw - v.x * hd, y: center.y + u.y * hw - v.y * hd };
  const c2: Vec2 = { x: center.x + u.x * hw + v.x * hd, y: center.y + u.y * hw + v.y * hd };
  const c3: Vec2 = { x: center.x - u.x * hw + v.x * hd, y: center.y - u.y * hw + v.y * hd };

  return {
    center,
    width,
    depth,
    angle,
    axes: [u, v],
    sides: [
      { a: c0, b: c1, len: width }, // side 0: bottom/long
      { a: c1, b: c2, len: depth }, // side 1: right/short
      { a: c2, b: c3, len: width }, // side 2: top/long
      { a: c3, b: c0, len: depth }, // side 3: left/short
    ],
  };
}

export function distanceToSegment(p: Vec2, a: Vec2, b: Vec2): number {
  const l2 = (b.x - a.x) ** 2 + (b.y - a.y) ** 2;
  if (l2 === 0) return distance(p, a);
  let t = ((p.x - a.x) * (b.x - a.x) + (p.y - a.y) * (b.y - a.y)) / l2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(p.x - (a.x + t * (b.x - a.x)), p.y - (a.y + t * (b.y - a.y)));
}

