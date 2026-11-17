import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MaterialChat } from './components/MaterialChat';
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

  it('answers a question with one click on an option', () => {
    const onSend = vi.fn();
    render(
      <MaterialChat
        messages={[{ role: 'assistant', text: 'What is the layout of the kitchen platform?', status: 'needs_input', options: [] }]}
        pendingOptions={['One wall', 'L-shape']}
        usingLabel="Kitchen, 10 × 8 ft, from project Green Villa"
        busy={false}
        onSend={onSend}
      />,
    );
    expect(screen.getByText(/using: kitchen, 10 × 8 ft/i)).toBeDefined();
    fireEvent.click(screen.getByText('L-shape'));
    expect(onSend).toHaveBeenCalledWith('L-shape', null);
  });

  it('renders short replies with bold numbers and a typing indicator', () => {
    render(
      <MaterialChat
        messages={[{ role: 'assistant', text: '**35.2 sq ft** of marble for the Kitchen platform (L-shape).', status: 'ok', options: [] }]}
        pendingOptions={[]}
        busy
        thinking="Reading the floor plan"
        onSend={() => {}}
      />,
    );
    expect(screen.getByText('35.2 sq ft').tagName).toBe('STRONG');
    expect(screen.getByRole('status').textContent).toMatch(/reading the floor plan/i);
  });

  it('shows step-by-step answers as paragraphs and bullet lists', () => {
    const text = [
      'Sizes come from TV wall (the size you gave).',
      '',
      '**Fluted veneer, TV wall: 92.4 sq ft**',
      '- TV wall: 12 × 10 = 120',
      '- Wastage 10%: 84 × 1.1 = 92.4',
    ].join('\n');
    render(<MaterialChat messages={[{ role: 'assistant', text, status: 'ok', options: [] }]} pendingOptions={[]} busy={false} onSend={() => {}} />);
    const items = screen.getAllByRole('listitem');
    expect(items.map((li) => li.textContent)).toEqual(['TV wall: 12 × 10 = 120', 'Wastage 10%: 84 × 1.1 = 92.4']);
    expect(screen.getByText('Fluted veneer, TV wall: 92.4 sq ft').tagName).toBe('STRONG');
  });

  it('has no money text anywhere in the feature', () => {
    const files = import.meta.glob(['./**/*.ts', './**/*.tsx', '!./**/*.test.tsx'], { query: '?raw', import: 'default', eager: true }) as Record<string, string>;
    expect(Object.keys(files).length).toBeGreaterThan(8);
    for (const [name, text] of Object.entries(files)) {
      expect(text, name).not.toMatch(/₹|\bprice|\bcost\b|\bbudget|\brate\b|INR\b|CPWD/i);
    }
  });
});
