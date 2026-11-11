import { describe, it, expect, vi, beforeEach } from 'vitest';
import { sheetsApi, mapSheetItemToMaterial, type SheetResponse, type SheetItem } from './api';
import { TOKEN_STORAGE_KEY } from '../../lib/api';

describe('sheetsApi Service & Material Mapping', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem(TOKEN_STORAGE_KEY, 'test-jwt-token');
    vi.restoreAllMocks();
  });

  it('maps backend SheetItem to frontend MaterialQuantityItem accurately', () => {
    const item: SheetItem = {
      id: 'item_brick_1',
      name: 'Brick',
      category: 'Masonry',
      unit: 'pcs',
      quantity: 6120,
      waste_factor: 0.05,
      total_quantity: 6426,
      unit_price: 75,
      amount: 481950,
      surface_tag: 'masonry_walls',
      area: 699.39,
      area_unit: 'm2',
      secondary_quantity: 699.39,
      secondary_unit: 'm2 wall area',
    };

    const mapped = mapSheetItemToMaterial(item);
    expect(mapped.id).toBe('item_brick_1');
    expect(mapped.materialName).toBe('Brick');
    expect(mapped.category).toBe('Masonry');
    expect(mapped.rate).toBe(75);
    expect(mapped.unit).toBe('pcs');
    expect(mapped.estimatedAmount).toBe(481950);
    expect(mapped.surfaceTag).toBe('brick'); // Brick maps to brick tag for 3D masonry wall highlight
    expect(mapped.totalArea).toBe('699.4 m²');
    expect(mapped.quantity).toContain('6,426 pcs');

    const steelItem: SheetItem = {
      id: 'item_steel_1',
      name: 'Steel/rebar rod',
      category: 'Structural Steel',
      unit: 'kg',
      quantity: 2800,
      waste_factor: 0.03,
      total_quantity: 2884,
      unit_price: 68,
      amount: 196112,
      surface_tag: 'structural_reinforcement',
    };
    const mappedSteel = mapSheetItemToMaterial(steelItem);
    expect(mappedSteel.surfaceTag).toBe('steel'); // Steel maps to steel tag for structural wall/column highlight
  });

  it('calls GET /api/v1/sheets/{project_id} with authorization header', async () => {
    const mockSheet: SheetResponse = {
      id: 'sheet_uuid_1',
      project_id: 'proj_uuid_1',
      name: 'Pavilion Serena BOQ',
      status: 'ready',
      stale: false,
      currency: 'INR',
      subtotal: 1000000,
      contingency_rate: 0.05,
      contingency: 50000,
      total_cost: 1050000,
      items: [
        {
          id: 'item_1',
          name: 'Tiles (floor and wall)',
          category: 'Flooring',
          unit: 'sq.m',
          quantity: 120,
          waste_factor: 0.05,
          total_quantity: 126,
          unit_price: 620,
          amount: 78120,
          surface_tag: 'floor_and_wall_tiles',
        },
      ],
    };

    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockSheet,
    });

    vi.stubGlobal('fetch', fetchSpy);

    const sheet = await sheetsApi.getSheet('proj_uuid_1');

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/sheets/proj_uuid_1',
      expect.objectContaining({
        method: 'GET',
        headers: expect.any(Headers),
      })
    );

    const sentHeaders = fetchSpy.mock.calls[0][1].headers as Headers;
    expect(sentHeaders.get('Authorization')).toBe('Bearer test-jwt-token');
    expect(sheet.id).toBe('sheet_uuid_1');
    expect(sheet.total_cost).toBe(1050000);
    expect(sheet.items).toHaveLength(1);
  });

  it('calls POST /api/v1/sheets/{project_id}/recalculate-from-plan', async () => {
    const mockRecalcResponse: SheetResponse = {
      id: 'sheet_uuid_1',
      project_id: 'proj_uuid_1',
      name: 'Recalculated BOQ',
      status: 'ready',
      stale: false,
      currency: 'INR',
      subtotal: 1200000,
      contingency_rate: 0.05,
      contingency: 60000,
      total_cost: 1260000,
      items: [],
    };

    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockRecalcResponse,
    });

    vi.stubGlobal('fetch', fetchSpy);

    const result = await sheetsApi.recalculateFromPlan('proj_uuid_1');

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/sheets/proj_uuid_1/recalculate-from-plan',
      expect.objectContaining({
        method: 'POST',
      })
    );
    expect(result.total_cost).toBe(1260000);
  });

  it('calls PUT /api/v1/sheets/{project_id}/items/{item_id} on inline edit', async () => {
    const updatedItem: SheetItem = {
      id: 'item_1',
      name: 'Brick',
      category: 'Masonry',
      unit: 'pcs',
      quantity: 9000,
      waste_factor: 0.05,
      total_quantity: 9450,
      unit_price: 10,
      amount: 94500,
    };

    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => updatedItem,
    });

    vi.stubGlobal('fetch', fetchSpy);

    const res = await sheetsApi.updateItem('proj_uuid_1', 'item_1', {
      unit_price: 10,
      quantity: 9000,
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/sheets/proj_uuid_1/items/item_1',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ unit_price: 10, quantity: 9000 }),
      })
    );
    expect(res.amount).toBe(94500);
  });
});

