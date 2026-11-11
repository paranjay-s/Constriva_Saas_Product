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
});

