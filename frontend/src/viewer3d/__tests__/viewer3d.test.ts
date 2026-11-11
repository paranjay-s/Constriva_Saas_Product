// viewer3d/__tests__/viewer3d.test.ts
import { describe, it, expect } from 'vitest';
import { parseFtIn, parseSingleFtIn, formatMetersToFtIn } from '../utils/units';
import { polygonArea, polygonCentroid, minimumAreaOBB, pointInPolygon } from '../utils/geometry';
import { normalizePlan } from '../adapter/normalizePlan';
import { boxesOverlap, canPlaceBox } from '../furniture/layout';
import samplePlan from '../fixtures/plan-sample.json';

describe('Vanilla Three.js Dollhouse 3D Engine - Core Utilities', () => {
  describe('Units & Dimension Parser', () => {
    it('parses imperial feet and inches correctly', () => {
      const dim = parseFtIn('10\'2"X12\'');
      expect(dim).not.toBeNull();
      // 10'2" = 122 inches = 3.0988 m
      expect(dim!.w).toBeCloseTo(3.0988, 3);
      // 12' = 144 inches = 3.6576 m
      expect(dim!.d).toBeCloseTo(3.6576, 3);
    });

    it('parses metric dimensions with "m" suffix', () => {
      const dim = parseFtIn('3.5m x 4.2m');
      expect(dim).not.toBeNull();
      expect(dim!.w).toBeCloseTo(3.5, 2);
      expect(dim!.d).toBeCloseTo(4.2, 2);
    });

    it('converts single ft-in string to meters', () => {
      expect(parseSingleFtIn('10\'')).toBeCloseTo(3.048, 3);
      expect(parseSingleFtIn('6"')).toBeCloseTo(0.1524, 3);
      expect(parseSingleFtIn('10\'6"')).toBeCloseTo(3.2004, 3);
    });

    it('formats meters back to imperial ft-in notation', () => {
      const text = formatMetersToFtIn(3.0988, 3.6576);
      expect(text).toContain('10\'');
      expect(text).toContain('12\'');
    });
  });

  describe('Geometric Computation & OBB', () => {
    it('calculates polygon area using shoelace formula', () => {
      const quad = [
        { x: 0, y: 0 },
        { x: 4, y: 0 },
        { x: 4, y: 3 },
        { x: 0, y: 3 },
      ];
      expect(polygonArea(quad)).toBeCloseTo(12.0, 5);
    });

    it('calculates centroid correctly', () => {
      const quad = [
        { x: 0, y: 0 },
        { x: 4, y: 0 },
        { x: 4, y: 6 },
        { x: 0, y: 6 },
      ];
      const c = polygonCentroid(quad);
      expect(c.x).toBeCloseTo(2.0, 5);
      expect(c.y).toBeCloseTo(3.0, 5);
    });

    it('determines point containment in polygon', () => {
      const quad = [
        { x: 0, y: 0 },
        { x: 5, y: 0 },
        { x: 5, y: 5 },
        { x: 0, y: 5 },
      ];
      expect(pointInPolygon({ x: 2.5, y: 2.5 }, quad)).toBe(true);
      expect(pointInPolygon({ x: 6, y: 2.5 }, quad)).toBe(false);
      expect(pointInPolygon({ x: -1, y: 2.5 }, quad)).toBe(false);
    });

    it('computes minimum-area oriented bounding box (OBB)', () => {
      const rect = [
        { x: 1, y: 1 },
        { x: 5, y: 1 },
        { x: 5, y: 4 },
        { x: 1, y: 4 },
      ];
      const obb = minimumAreaOBB(rect);
      expect(obb.width).toBeCloseTo(4.0, 2);
      expect(obb.depth).toBeCloseTo(3.0, 2);
      expect(obb.center.x).toBeCloseTo(3.0, 2);
      expect(obb.center.y).toBeCloseTo(2.5, 2);
    });
  });

  describe('Furniture Layout & Collision Detection', () => {
    it('detects overlapping oriented boxes', () => {
      const box1 = { center: { x: 0, y: 0 }, width: 2, depth: 2, angle: 0 };
      const box2 = { center: { x: 1, y: 0 }, width: 2, depth: 2, angle: 0 };
      expect(boxesOverlap(box1, box2)).toBe(true);

      const box3 = { center: { x: 5, y: 5 }, width: 1, depth: 1, angle: 0 };
      expect(boxesOverlap(box1, box3)).toBe(false);
    });

    it('prevents placing items outside room polygon', () => {
      const roomPoly = [
        { x: 0, y: 0 },
        { x: 4, y: 0 },
        { x: 4, y: 4 },
        { x: 0, y: 4 },
      ];
      // Item completely inside
      const insideBox = { center: { x: 2, y: 2 }, width: 1.5, depth: 1.5, angle: 0 };
      expect(canPlaceBox(insideBox, roomPoly, [], [])).toBe(true);

      // Item sticking out
      const outsideBox = { center: { x: 3.8, y: 2 }, width: 1.5, depth: 1.5, angle: 0 };
      expect(canPlaceBox(outsideBox, roomPoly, [], [])).toBe(false);
    });
  });

  describe('Plan Normalizer & Adapter', () => {
    it('normalizes sample PlanJSON to internal Plan representation in meters', () => {
      const plan = normalizePlan(samplePlan);
      expect(plan.meta.sourceUnit).toBe('m');
      expect(plan.walls.length).toBeGreaterThan(0);
      expect(plan.rooms.length).toBeGreaterThan(0);

      // Verify footprint is re-centered around origin
      const allXs = plan.walls.flatMap((w) => [w.a.x, w.b.x]);
      const minX = Math.min(...allXs);
      const maxX = Math.max(...allXs);
      expect((minX + maxX) / 2).toBeCloseTo(0, 1);

      // Verify exterior walls are detected
      const exteriorWalls = plan.walls.filter((w) => w.kind === 'exterior');
      expect(exteriorWalls.length).toBeGreaterThan(0);

      // Verify room types are mapped
      const bedroom = plan.rooms.find((r) => r.type === 'bedroom');
      expect(bedroom).toBeDefined();
    });

    it('synthesizes missing interior partition wall between two adjacent rooms', () => {
      // 2 adjacent rooms sharing edge from (3.5, 0) to (3.5, 4.0), but walls has NO wall between them
      const mockRawPlan = {
        units: 'm',
        levels: [
          {
            walls: [
              // Outer walls only, missing middle dividing wall!
              { id: 'w_bottom', start: [0, 0], end: [7, 0], kind: 'exterior' },
              { id: 'w_top', start: [0, 4], end: [7, 4], kind: 'exterior' },
              { id: 'w_left', start: [0, 0], end: [0, 4], kind: 'exterior' },
              { id: 'w_right', start: [7, 0], end: [7, 4], kind: 'exterior' },
            ],
            rooms: [
              {
                id: 'bedroom_1',
                name: 'BEDROOM 1',
                polygon: [[0, 0], [3.5, 0], [3.5, 4], [0, 4]],
              },
              {
                id: 'bedroom_2',
                name: 'BEDROOM 2',
                polygon: [[3.5, 0], [7, 0], [7, 4], [3.5, 4]],
              },
            ],
          },
        ],
      };

      const normalized = normalizePlan(mockRawPlan);
      // Synthesizer must detect the shared boundary and generate an interior partition wall
      const partition = normalized.walls.find(
        (w) => w.kind === 'interior' && w.id.includes('synth_partition')
      );
      expect(partition).toBeDefined();
      expect(partition!.thickness).toBeCloseTo(0.12, 2);
    });
  });
});
