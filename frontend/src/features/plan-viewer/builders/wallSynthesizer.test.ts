import { describe, it, expect } from 'vitest';
import { ensureCompleteWalls, filterValidRooms } from './wallSynthesizer';
import type { Room, Wall } from '../../../types';

describe('wallSynthesizer', () => {
  it('synthesizes interior partition wall between two adjacent indoor rooms when missing', () => {
    const rooms: Room[] = [
      {
        id: 'bed1',
        name: 'BEDROOM 12X12',
        kind: 'indoor',
        polygon: [
          [0, 0],
          [4, 0],
          [4, 4],
          [0, 4],
        ],
      },
      {
        id: 'bed2',
        name: 'BEDROOM 12X12',
        kind: 'indoor',
        polygon: [
          [4, 0],
          [8, 0],
          [8, 4],
          [4, 4],
        ],
      },
    ];

    const perimeterWalls: Wall[] = [
      { id: 'w_ext_top', start: [0, 0], end: [8, 0], thickness: 0.23, kind: 'exterior', length: 8 },
      { id: 'w_ext_right', start: [8, 0], end: [8, 4], thickness: 0.23, kind: 'exterior', length: 4 },
      { id: 'w_ext_bottom', start: [8, 4], end: [0, 4], thickness: 0.23, kind: 'exterior', length: 8 },
      { id: 'w_ext_left', start: [0, 4], end: [0, 0], thickness: 0.23, kind: 'exterior', length: 4 },
    ];

    const completed = ensureCompleteWalls(perimeterWalls, rooms);
    const interior = completed.filter((w) => w.kind === 'interior');

    expect(interior.length).toBeGreaterThanOrEqual(1);
    const divider = interior.find((w) => Math.abs(w.start[0] - 4) < 0.2 && Math.abs(w.end[0] - 4) < 0.2);
    expect(divider).toBeDefined();
    expect(divider?.thickness).toBe(0.12);
  });

  it('filters out stray rooms that float outside the main building footprint', () => {
    const validWalls: Wall[] = [
      { id: 'w1', start: [0, 0], end: [10, 0], thickness: 0.23, kind: 'exterior', length: 10 },
      { id: 'w2', start: [10, 0], end: [10, 15], thickness: 0.23, kind: 'exterior', length: 15 },
      { id: 'w3', start: [10, 15], end: [0, 15], thickness: 0.23, kind: 'exterior', length: 10 },
      { id: 'w4', start: [0, 15], end: [0, 0], thickness: 0.23, kind: 'exterior', length: 15 },
    ];

    const rooms: Room[] = [
      {
        id: 'living',
        name: 'LIVING ROOM',
        kind: 'indoor',
        polygon: [[1, 1], [6, 1], [6, 6], [1, 6]],
      },
      {
        id: 'stray_backyard_slab',
        name: 'STRAY SLAB',
        kind: 'outdoor',
        polygon: [[20, 20], [25, 20], [25, 25], [20, 25]], // Far outside building
      },
    ];

    const filtered = filterValidRooms(rooms, validWalls);
    expect(filtered.length).toBe(1);
    expect(filtered[0].id).toBe('living');
  });
});

