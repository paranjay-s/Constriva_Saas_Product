import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ResultView } from './components/ResultView';
import { sessionSchema } from './schemas';

const SESSION = sessionSchema.parse({
  id: 's1',
  focus: 'wall, TV wall',
  materials: [
    { id: 'm1', name: 'fluted walnut veneer panel', display_name: 'Fluted walnut veneer panel', category: 'wood_panel', surface: 'wall', coverage_ratio: 0.7, confidence: 'high' },
    { id: 'm2', name: 'Statuario marble', display_name: 'Statuario marble', category: 'stone', surface: 'wall', coverage_ratio: 0.3, confidence: 'medium', look_alikes: ['marble-look porcelain slab'] },
  ],
  report: {
    version: 1,
    target: { source: 'manual', label: 'TV wall, 12 × 10 ft', wall: { width_ft: 12, height_ft: 10, label: 'TV wall' } },
    lines: [
      {
        material_id: 'm1', material: 'Fluted walnut veneer panel', application: 'TV wall', surface_sqft: 120, coverage_ratio: 0.7,
        net_qty: 84, wastage_pct: 10, total_qty: 92.4, unit: 'sq ft', buy_qty: 3, buy_unit: 'sheets (8 × 4 ft)',
        breakdown: [{ label: 'TV wall', formula: '12 × 10', value: 120 }],
      },
      { material_id: 'm2', material: 'Statuario marble', application: 'TV wall', surface_sqft: 120, coverage_ratio: 0.3, net_qty: 36, wastage_pct: 10, total_qty: 39.6, unit: 'sq ft' },
    ],
    supporting: [
      { material_id: 'm1', material: 'Fluted walnut veneer panel', item: 'Backing plywood (8 x 4 ft)', qty: 3, unit: 'sheets', basis: '84 sq ft ÷ 32' },
    ],
    note: 'Quantities are planning estimates. Verify by site measurement before ordering.',
  },
  messages: [],
});

describe('Material Finder', () => {
  it('shows materials, quantities with buy units, look-alikes and the estimate note', () => {
    render(<ResultView materials={SESSION.materials} report={SESSION.report} />);
    expect(screen.getAllByText('Fluted walnut veneer panel').length).toBeGreaterThan(0);
    expect(screen.getByText('92.4 sq ft')).toBeDefined();
    expect(screen.getByText('3 sheets (8 × 4 ft)')).toBeDefined();
    expect(screen.getByText('39.6 sq ft')).toBeDefined();
    expect(screen.getByText(/could also be: marble-look porcelain slab/i)).toBeDefined();
    expect(screen.getByRole('note').textContent).toMatch(/verify by site measurement/i);
    expect(screen.getByText('Also needed')).toBeDefined();
    expect(screen.getByText('Backing plywood (8 x 4 ft)')).toBeDefined();
  });

  it('has no money text anywhere in the feature', () => {
    const files = import.meta.glob(['./**/*.ts', './**/*.tsx', '!./**/*.test.tsx'], { query: '?raw', import: 'default', eager: true }) as Record<string, string>;
    expect(Object.keys(files).length).toBeGreaterThan(5);
    for (const [name, text] of Object.entries(files)) {
      expect(text, name).not.toMatch(/₹|\bprice|\bcost\b|\bbudget|\brate\b|INR\b|CPWD/i);
    }
  });
});
