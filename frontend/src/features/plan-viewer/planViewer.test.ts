import { describe, it, expect } from 'vitest';
import {
  categorizeRoom,
  getRoomFloorMaterialParams,
  REALISTIC_THEME,
  CLAY_THEME,
} from './materials/materials';

describe('3D Architectural Viewer - Material & Categorization Engine', () => {
  it('correctly categorizes bedrooms and assigns light oak flooring', () => {
    const category = categorizeRoom('Master Bedroom Suite');
    expect(category).toBe('bedroom');
    const mat = getRoomFloorMaterialParams(category, REALISTIC_THEME);
    expect(mat.color).toBe('#C89D66'); // Warm honey oak
  });

  it('correctly categorizes living/drawing areas and assigns warm honey oak flooring', () => {
    const category = categorizeRoom('Grand Living & Drawing Room');
    expect(category).toBe('living');
    const mat = getRoomFloorMaterialParams(category, REALISTIC_THEME);
    expect(mat.color).toBe('#C89D66'); // Warm honey oak
  });

  it('correctly categorizes kitchens and assigns ceramic tile flooring', () => {
    const category = categorizeRoom('Kitchen & Pantry');
    expect(category).toBe('kitchen');
    const mat = getRoomFloorMaterialParams(category, REALISTIC_THEME);
    expect(mat.color).toBe('#E7E4DF'); // Light stone
  });

  it('correctly categorizes bathrooms and assigns light grey/white tile', () => {
    const category = categorizeRoom('Ensuite Bathroom & WC');
    expect(category).toBe('bathroom');
    const mat = getRoomFloorMaterialParams(category, REALISTIC_THEME);
    expect(mat.color).toBe('#EAE7E2'); // Porcelain stone tile
  });

  it('correctly categorizes balconies and assigns outdoor stone pavers', () => {
    const category = categorizeRoom('Balcony & Sun Terrace');
    expect(category).toBe('balcony');
    const mat = getRoomFloorMaterialParams(category, REALISTIC_THEME);
    expect(mat.color).toBe('#C5BFB5'); // Outdoor pavers
  });

  it('supports architectural clay mode with matte monochromatic properties', () => {
    expect(CLAY_THEME.isClay).toBe(true);
    expect(CLAY_THEME.wallPlaster.color).toBe('#EDE9E1');
    expect(CLAY_THEME.bedroomFloor.color).toBe('#DFD8CC');
  });

  it('defines realistic architectural finishes for walls, doors and windows', () => {
    expect(REALISTIC_THEME.wallPlaster.color).toBe('#FFFFFF');
    expect(REALISTIC_THEME.doorWood.color).toBe('#A87342');
    expect(REALISTIC_THEME.windowGlass.transparent).toBe(true);
    expect(REALISTIC_THEME.windowGlass.opacity).toBeLessThan(0.5);
  });
});

