import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { AsciiOcean } from './ocean/AsciiOcean';
import { LAYOUTS } from './ocean/forms';
import { Rail } from './Rail';
import { AiMessage, QuickReplies, Typing } from './Thread';
import { type ChatSummary, dayGroup } from './useChatHistory';

describe('conversation', () => {
  it('shows step-by-step answers as paragraphs, bullets and bold numbers', () => {
    const text = [
      'Sizes come from TV wall (the size you gave).',
      '',
      '**Fluted veneer, TV wall: 92.4 sq ft**',
      '- TV wall: 12 × 10 = 120',
      '- Wastage 10%: 84 × 1.1 = 92.4',
    ].join('\n');
    render(<AiMessage text={text} />);
    const items = screen.getAllByRole('listitem');
    expect(items.map((li) => li.textContent)).toEqual(['TV wall: 12 × 10 = 120', 'Wastage 10%: 84 × 1.1 = 92.4']);
    expect(screen.getByText('Fluted veneer, TV wall: 92.4 sq ft').tagName).toBe('STRONG');
  });

  it('answers with one click on a quick reply', () => {
    const onPick = vi.fn();
    render(<QuickReplies options={['One wall', 'L-shape']} onPick={onPick} />);
    fireEvent.click(screen.getByText('L-shape'));
    expect(onPick).toHaveBeenCalledWith('L-shape');
  });

  it('shows what the assistant is doing while it works', () => {
    render(<Typing label="Reading the floor plan" />);
    expect(screen.getByRole('status').textContent).toMatch(/reading the floor plan/i);
  });

  it('shows the plasma orb while working, with a CSS stand-in without WebGL 2', async () => {
    const { container } = render(<Typing label="Drawing the plan" />);
    await waitFor(() => expect(container.querySelector('.st-orb[data-fallback]')).not.toBeNull());
  });
});

describe('history', () => {
  const now = new Date('2026-11-18T12:00:00');
  it('groups chats by day', () => {
    expect(dayGroup('2026-11-18T08:00:00', now)).toBe('Today');
    expect(dayGroup('2026-11-17T22:00:00', now)).toBe('Yesterday');
    expect(dayGroup('2026-11-14T10:00:00', now)).toBe('Previous 7 days');
    expect(dayGroup('2026-10-25T10:00:00', now)).toBe('Previous 30 days');
    expect(dayGroup('not a date', now)).toBe('Earlier');
  });

  const ITEMS: ChatSummary[] = [
    { id: 'p1', kind: 'plan', title: '3 BHK, 30x40 ft', subtitle: '2D floor plan · v2', createdAt: new Date().toISOString(), href: '/projects/ai-generator?plan=p1' },
    { id: 'a1', kind: 'analysis', title: 'Living room', subtitle: 'analyze this', createdAt: new Date().toISOString(), href: '/materials/analyse?analysis=a1' },
  ];

  function renderRail(onDelete = vi.fn()) {
    render(
      <MemoryRouter>
        <Rail
          agent="plan"
          currentId="p1"
          history={ITEMS}
          historyLoading={false}
          historyError={null}
          onRetryHistory={() => {}}
          onDelete={onDelete}
          expanded
          onToggleExpanded={() => {}}
          motionOn
          onToggleMotion={() => {}}
          userName="Asha Rao"
          onNavigate={() => {}}
        />
      </MemoryRouter>,
    );
    return onDelete;
  }

  it('lists floor plans and image analyses together, and filters them', () => {
    renderRail();
    expect(screen.getByText('Today')).toBeDefined();
    expect(screen.getByText('3 BHK, 30x40 ft').closest('button')?.getAttribute('aria-current')).toBe('page');
    expect(screen.getByText('Living room')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Images' }));
    expect(screen.queryByText('3 BHK, 30x40 ft')).toBeNull();
    expect(screen.getByText('Living room')).toBeDefined();
  });

  it('deletes an image analysis after confirming', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const onDelete = renderRail();
    fireEvent.click(screen.getByRole('button', { name: /delete living room/i }));
    expect(onDelete).toHaveBeenCalledWith(ITEMS[1]);
  });
});

describe('ASCII background', () => {
  it('does nothing (and never throws) where canvas is not available', () => {
    const host = document.createElement('div');
    const canvas = document.createElement('canvas');
    const o = new AsciiOcean(host, canvas);
    expect(o.supported).toBe(false);
    expect(() => {
      o.resize();
      o.setTheme('brass');
      o.typing();
      o.setWorking(true);
      o.pulse();
      o.setFacing('east');
      o.setPlaying(false);
      o.destroy();
    }).not.toThrow();
  });

  it('draws architectural forms, never jellyfish', () => {
    expect(LAYOUTS.blueprint).toHaveLength(5);
    expect(LAYOUTS.brass).toHaveLength(5);
    // every form draws through the pen, so drafting (line by line) works for all of them
    const calls: string[] = [];
    const g = new Proxy({} as CanvasRenderingContext2D, {
      get: (_t, k) => (typeof k === 'string' && /^(set|line|arc|move|begin|close|stroke|fill|save|restore)/.test(k) ? () => calls.push(k) : undefined),
      set: () => true,
    });
    for (const p of [...LAYOUTS.blueprint, ...LAYOUTS.brass]) {
      let steps = 0;
      p.form.draw({ g, col: () => 'rgb(0,0,0)', step: () => (steps++, true) }, 80, { t: 1, k: 1, facing: 0, seed: 0.2 });
      expect(steps).toBeGreaterThan(4);
    }
    expect(calls.length).toBeGreaterThan(100);
  });
});
