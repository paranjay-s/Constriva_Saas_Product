import { describe, it, expect } from 'vitest';
import {
  categorizeRoom,
  getRoomFloorMaterialParams,
  REALISTIC_THEME,
  CLAY_THEME,
} from './materials/materials';
import { isIndoorTileTarget } from './PlanViewer';
import type { Room } from '../../types';

describe('3D Architectural Viewer - Material & Categorization Engine', () => {
  it('correctly categorizes bedrooms and assigns light oak flooring', () => {
    const category = categorizeRoom('Master Bedroom Suite');
    expect(category).toBe('bedroom');
    const mat = getRoomFloorMaterialParams(category, REALISTIC_THEME);
    expect(mat.color).toBe('#C4955B'); // Warm natural honey oak
  });

  it('correctly categorizes living/drawing areas and assigns warm honey oak flooring', () => {
    const category = categorizeRoom('Grand Living & Drawing Room');
    expect(category).toBe('living');
    const mat = getRoomFloorMaterialParams(category, REALISTIC_THEME);
    expect(mat.color).toBe('#D4A367'); // Warm luminous amber oak
  });

  it('correctly categorizes kitchens and assigns ceramic tile flooring', () => {
    const category = categorizeRoom('Kitchen & Pantry');
    expect(category).toBe('kitchen');
    const mat = getRoomFloorMaterialParams(category, REALISTIC_THEME);
    expect(mat.color).toBe('#DCD6CB'); // Modern polished travertine
  });

  it('correctly categorizes bathrooms and assigns light grey/white tile', () => {
    const category = categorizeRoom('Ensuite Bathroom & WC');
    expect(category).toBe('bathroom');
    const mat = getRoomFloorMaterialParams(category, REALISTIC_THEME);
    expect(mat.color).toBe('#E5EDF4'); // Elegant cool Carrara marble porcelain
  });

  it('correctly categorizes balconies and assigns outdoor stone pavers', () => {
    const category = categorizeRoom('Balcony & Sun Terrace');
    expect(category).toBe('balcony');
    const mat = getRoomFloorMaterialParams(category, REALISTIC_THEME);
    expect(mat.color).toBe('#BA834E'); // Warm natural outdoor teak decking
  });

  it('supports architectural clay mode with matte monochromatic properties', () => {
    expect(CLAY_THEME.isClay).toBe(true);
    expect(CLAY_THEME.wallPlaster.color).toBe('#EDE9E1');
    expect(CLAY_THEME.bedroomFloor.color).toBe('#DFD8CC');
  });

  it('defines realistic architectural finishes for walls, doors and windows', () => {
    expect(REALISTIC_THEME.wallPlaster.color).toBe('#E8E3D8');
    expect(REALISTIC_THEME.doorWood.color).toBe('#A87342');
    expect(REALISTIC_THEME.windowGlass.transparent).toBe(true);
    expect(REALISTIC_THEME.windowGlass.opacity).toBeLessThan(0.5);
  });

  it('isIndoorTileTarget strictly includes indoor rooms and excludes all outdoor/semi-open spaces', () => {
    const dummyPoly: [number, number][] = [[0, 0], [4, 0], [4, 4], [0, 4]];

    // Indoor rooms MUST be targetable
    const indoorLiving: Room = { id: 'liv_1', name: 'LIVING ROOM 11X20', kind: 'indoor', polygon: dummyPoly };
    const indoorBed: Room = { id: 'bed_1', name: 'BEDROOM 14X12', kind: 'indoor', polygon: dummyPoly };
    const indoorKit: Room = { id: 'kit_1', name: 'KIT. 11X11', kind: 'indoor', polygon: dummyPoly };
    const indoorBath: Room = { id: 'bath_1', name: 'TOILET 6X8', kind: 'indoor', polygon: dummyPoly };
    const indoorPuja: Room = { id: 'puja_1', name: 'PUJA', kind: 'indoor', polygon: dummyPoly };

    expect(isIndoorTileTarget(indoorLiving, 'living')).toBe(true);
    expect(isIndoorTileTarget(indoorBed, 'bedroom')).toBe(true);
    expect(isIndoorTileTarget(indoorKit, 'kitchen')).toBe(true);
    expect(isIndoorTileTarget(indoorBath, 'bathroom')).toBe(true);
    expect(isIndoorTileTarget(indoorPuja, 'general')).toBe(true);

    // Outdoor & semi-open spaces MUST NEVER be targetable for interior floor tiles
    const lawn: Room = { id: 'lawn_1', name: 'LAWN 10X8', kind: 'outdoor', polygon: dummyPoly };
    const parking: Room = { id: 'park_1', name: 'PARKING 14X16', kind: 'semi_open', polygon: dummyPoly };
    const staircase: Room = { id: 'stair_1', name: 'STAIRCASE', kind: 'semi_open', polygon: dummyPoly };
    const verandah: Room = { id: 'ver_1', name: 'VERANDAH', kind: 'semi_open', polygon: dummyPoly };
    const balcony: Room = { id: 'balc_1', name: 'BALCONY', kind: 'semi_open', polygon: dummyPoly };
    const terrace: Room = { id: 'terr_1', name: 'SUN TERRACE', kind: 'semi_open', polygon: dummyPoly };
    const washOutdoor: Room = { id: 'wash_1', name: 'WASH 11X4', kind: 'semi_open', polygon: dummyPoly };
    const openShaft: Room = { id: 'shaft_1', name: 'OPEN SHAFT', kind: 'void', polygon: dummyPoly };

    expect(isIndoorTileTarget(lawn, 'lawn')).toBe(false);
    expect(isIndoorTileTarget(parking, 'parking')).toBe(false);
    expect(isIndoorTileTarget(staircase, 'corridor')).toBe(false);
    expect(isIndoorTileTarget(verandah, 'balcony')).toBe(false);
    expect(isIndoorTileTarget(balcony, 'balcony')).toBe(false);
    expect(isIndoorTileTarget(terrace, 'balcony')).toBe(false);
    expect(isIndoorTileTarget(washOutdoor, 'utility')).toBe(false);
    expect(isIndoorTileTarget(openShaft, 'void')).toBe(false);
  });
});

