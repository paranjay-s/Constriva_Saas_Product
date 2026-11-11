import { apiRequest, API_BASE_URL, TOKEN_STORAGE_KEY } from '../../lib/api';
import type { MaterialQuantityItem } from '../../types';

export interface SheetItem {
  id: string;
  sheet_id?: string;
  name: string;
  category: string;
  unit: string;
  quantity: number;
  waste_factor: number;
  unit_price: number;
  total_quantity: number;
  amount: number;
  surface_tag?: string | null;
  area?: number | null;
  area_unit?: string | null;
  secondary_quantity?: number | null;
  secondary_unit?: string | null;
  is_custom?: boolean;
}

export interface SheetResponse {
  id: string;
  project_id: string;
  plan_id?: string | null;
  name: string;
  status: string;
  stale: boolean;
  currency: string;
  subtotal: number;
  contingency_rate: number;
  contingency: number;
  total_cost: number;
  items: SheetItem[];
}

export interface SheetItemUpdate {
  name?: string;
  category?: string;
  unit?: string;
  quantity?: number;
  waste_factor?: number;
  unit_price?: number;
  surface_tag?: string;
}

export interface SheetItemCreate {
  name: string;
  category: string;
  unit: string;
  quantity: number;
  waste_factor?: number;
  unit_price?: number;
  surface_tag?: string;
}

/**
 * Maps a backend SheetItem into the frontend MaterialQuantityItem format
 */
export function mapSheetItemToMaterial(item: SheetItem): MaterialQuantityItem {
  let surfaceTag = item.surface_tag || 'concrete';
  const lowerName = (item.name || '').toLowerCase();
  
  // Normalize tag for 3D highlighting
  if (lowerName.includes('brick') || lowerName.includes('masonry')) {
    surfaceTag = 'brick'; // highlights masonry walls
  } else if (lowerName.includes('tile') || lowerName.includes('marble')) {
    surfaceTag = 'tiles'; // highlights indoor room floors
  } else if (lowerName.includes('steel') || lowerName.includes('rebar')) {
    surfaceTag = 'steel'; // highlights structural walls & reinforcement
  } else if (lowerName.includes('plaster')) {
    surfaceTag = 'plaster'; // highlights wall plaster
  } else if (lowerName.includes('cement')) {
    surfaceTag = 'cement'; // highlights mortar in walls
  } else if (lowerName.includes('sand')) {
    surfaceTag = 'sand'; // highlights mortar
  } else if (lowerName.includes('ballast')) {
    surfaceTag = 'ballast'; // highlights foundation
  }

  const areaStr = item.area
    ? `${item.area.toFixed(1)} m²`
    : item.secondary_quantity
    ? `${item.secondary_quantity} ${item.secondary_unit || ''}`.trim()
    : `${item.total_quantity} ${item.unit}`;

  return {
    id: item.id,
    materialName: item.name,
    category: item.category,
    rate: item.unit_price,
    unit: item.unit,
    quantity: `${item.total_quantity.toLocaleString('en-IN', { maximumFractionDigits: 1 })} ${item.unit}`,
    totalArea: areaStr,
    estimatedAmount: item.amount || Math.round(item.total_quantity * item.unit_price),
    surfaceTag: surfaceTag as any,
  };
}

export const sheetsApi = {
  /**
   * Fetch project cost sheet (auto-creates if missing)
   */
  getSheet: async (projectId: string): Promise<SheetResponse> => {
    return apiRequest<SheetResponse>(`/api/v1/sheets/${projectId}`, {
      method: 'GET',
    });
  },

  /**
   * Recalculate cost sheet from active PlanJSON in DB
   */
  recalculateFromPlan: async (projectId: string): Promise<SheetResponse> => {
    return apiRequest<SheetResponse>(`/api/v1/sheets/${projectId}/recalculate-from-plan`, {
      method: 'POST',
    });
  },

  /**
   * Inline edit a line item
   */
  updateItem: async (projectId: string, itemId: string, payload: SheetItemUpdate): Promise<SheetItem> => {
    return apiRequest<SheetItem>(`/api/v1/sheets/${projectId}/items/${itemId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Add a custom line item
   */
  addItem: async (projectId: string, payload: SheetItemCreate): Promise<SheetItem> => {
    return apiRequest<SheetItem>(`/api/v1/sheets/${projectId}/items`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Delete a line item
   */
  deleteItem: async (projectId: string, itemId: string): Promise<void> => {
    await apiRequest<void>(`/api/v1/sheets/${projectId}/items/${itemId}`, {
      method: 'DELETE',
    });
  },

  /**
   * Download CSV export directly via authenticated fetch
   */
  downloadCsv: async (projectId: string, projectName: string = 'project'): Promise<void> => {
    const token = localStorage.getItem(TOKEN_STORAGE_KEY);
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE_URL}/api/v1/sheets/${projectId}/export/csv`, {
      headers,
    });
    if (!res.ok) throw new Error('Failed to download CSV export');

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${projectName}_BOQ_Estimate.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  },

  /**
   * Download PDF architectural report directly via authenticated fetch
   */
  downloadPdf: async (projectId: string, projectName: string = 'project'): Promise<void> => {
    const token = localStorage.getItem(TOKEN_STORAGE_KEY);
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE_URL}/api/v1/sheets/${projectId}/export/pdf`, {
      headers,
    });
    if (!res.ok) throw new Error('Failed to download PDF export');

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${projectName}_BOQ_Report.pdf`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  },
};

