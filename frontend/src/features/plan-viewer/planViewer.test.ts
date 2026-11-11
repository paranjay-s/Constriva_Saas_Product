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

  it('builds full 3D architectural model from DEFAULT_ARCHITECTURAL_PLAN with non-zero geometry', async () => {
    const { DEFAULT_ARCHITECTURAL_PLAN } = await import('../../lib/defaultPlan');
    const { normalizePlan } = await import('../../viewer3d/adapter/normalizePlan');
    const { buildFloorsWithPbr } = await import('./builders/buildFloors');
    const { buildWallsWithOpenings } = await import('./builders/buildWallsWithOpenings');
    const { furnishRoomsWithPbr } = await import('./furniture/roomFurnisher');
    const { getPbrMaterialCatalog } = await import('./materials/materials');

    const plan = normalizePlan(DEFAULT_ARCHITECTURAL_PLAN);
    expect(plan.walls.length).toBeGreaterThan(0);
    expect(plan.rooms.length).toBeGreaterThan(0);

    const mats = getPbrMaterialCatalog();
    const roomsData = plan.rooms.map((r) => ({
      id: r.id,
      name: r.label || r.id,
      type: r.type,
      polygon: r.polygon,
    }));

    const floors = buildFloorsWithPbr(roomsData, mats);
    expect(floors.group.children.length).toBeGreaterThan(0);
    expect(floors.roomMeshes.size).toBeGreaterThan(0);

    const walls = buildWallsWithOpenings(plan.walls, plan.openings, mats);
    expect(walls.group.children.length).toBeGreaterThan(0);
    expect(walls.walls.length).toBeGreaterThan(0);

    const furn = furnishRoomsWithPbr(roomsData, mats);
    expect(furn.group.children.length).toBeGreaterThan(0);
  });

  it('provides luxurious architectural finish descriptions and icons upon room entrance', async () => {
    const { getRoomFinishDescription, getRoomIcon } = await import('./PlanViewer');

    const bedFinish = getRoomFinishDescription('Master Bedroom Suite');
    expect(bedFinish.flooring).toContain('Herringbone Oak');
    expect(bedFinish.wallFinish).toContain('Skirting');
    expect(getRoomIcon('Master Bedroom')).toBe('🛏️');

    const livingFinish = getRoomFinishDescription('Living & Dining Hall');
    expect(livingFinish.flooring).toContain('Carrara Marble');
    expect(livingFinish.wallFinish).toContain('Crown Moulding');
    expect(getRoomIcon('Living Room')).toBe('🛋️');

    const bathFinish = getRoomFinishDescription('Attached Toilet & Bath');
    expect(bathFinish.flooring).toContain('Ceramic Tile');
    expect(getRoomIcon('Toilet')).toBe('🚿');

    const deckFinish = getRoomFinishDescription('Outdoor Teak Verandah & Deck');
    expect(deckFinish.flooring).toContain('Teak Wood');
    expect(getRoomIcon('Patio Deck')).toBe('🌿');
  });

  it('guarantees dividing partition walls between adjacent rooms separated by a standard 0.23m wall gap', async () => {
    const { normalizePlan } = await import('../../viewer3d/adapter/normalizePlan');

    // Two adjacent rooms separated by 0.23m (9 inch) gap where CAD plan omitted the dividing wall
    const rawPlanWithMissingDivider = {
      units: 'm',
      levels: [
        {
          rooms: [
            {
              id: 'room_a',
              name: 'BEDROOM 1',
              polygon: [
                [0, 0],
                [4, 0],
                [4, 4],
                [0, 4],
              ],
            },
            {
              id: 'room_b',
              name: 'BEDROOM 2',
              polygon: [
                [4.23, 0], // Separated by 0.23m wall gap
                [8.23, 0],
                [8.23, 4],
                [4.23, 4],
              ],
            },
          ],
          walls: [
            // Only outer perimeter walls, interior divider is missing!
            { id: 'w_ext_top', a: [0, 0], b: [8.23, 0], kind: 'exterior' },
            { id: 'w_ext_right', a: [8.23, 0], b: [8.23, 4], kind: 'exterior' },
            { id: 'w_ext_bottom', a: [8.23, 4], b: [0, 4], kind: 'exterior' },
            { id: 'w_ext_left', a: [0, 4], b: [0, 0], kind: 'exterior' },
          ],
        },
      ],
    };

    const normalized = normalizePlan(rawPlanWithMissingDivider);
    const interiorDividers = normalized.walls.filter(
      (w) => w.kind === 'interior' || w.id.includes('synth_partition')
    );

    expect(interiorDividers.length).toBeGreaterThanOrEqual(1);
    const divider = interiorDividers.find(
      (w) => Math.abs(w.a.x - w.b.x) < 0.1 && Math.abs(w.b.y - w.a.y) >= 3.5
    );
    expect(divider).toBeDefined();
  });
});

