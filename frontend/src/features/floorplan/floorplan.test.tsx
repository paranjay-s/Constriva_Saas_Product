import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider } from '../../context/AuthContext';
import { ProjectProvider } from '../../context/ProjectContext';
import { FloorplanPage } from './FloorplanPage';
import { ConfirmationCard } from './components/ConfirmationCard';
import { ProgressSteps } from './components/ProgressSteps';
import { parseSse } from './hooks/useJobEvents';
import { type JobEvent, type ParseResponse, briefFormSchema } from './schemas';

const BRIEF: ParseResponse['brief'] = {
  plot: { width_cm: 1219, depth_cm: 1524, input_unit: 'ft', shape_assumed: false },
  bedrooms: 5,
  bathrooms: null,
  rooms: [{ type: 'master_bedroom', count: 1, attached_bath: true, dress_room: false }],
  road_side: 'east',
  project_name: '',
  owner_name: '',
  notes: '',
  unknowns: [],
  conflicts: [{ field: 'bedrooms', form_value: '4', text_value: '5', resolution: 'description value used' }],
  assumptions: ['Purpose not given: planned as a residential home.'],
};

const PARSED: ParseResponse = { brief: BRIEF, summary: '5 bedrooms (1 with attached bath)', warnings: [], missing: [], ready: true };

function ev(stage: string, progress: number, extra: Partial<JobEvent> = {}): JobEvent {
  return { job_id: 'j', status: 'running', stage, detail: '', progress, options: [], ...extra };
}

describe('parseSse', () => {
  it('splits complete messages and keeps the unfinished rest', () => {
    const { messages, rest } = parseSse('event: progress\ndata: {"a":1}\n\n: keep-alive\n\nevent: end\ndata: {}\n\nevent: prog');
    expect(messages).toEqual([
      { event: 'progress', data: '{"a":1}' },
      { event: 'end', data: '{}' },
    ]);
    expect(rest).toBe('event: prog');
  });

  it('handles CRLF line endings', () => {
    expect(parseSse('event: progress\r\ndata: x\r\n\r\n').messages).toEqual([{ event: 'progress', data: 'x' }]);
  });
});

describe('briefFormSchema', () => {
  const base = { unit: 'ft', extras: [], project_name: '', owner_name: '', prompt: '' };

  it('accepts a plot from the form', () => {
    const r = briefFormSchema.safeParse({ ...base, plot_width: '30', plot_depth: '45', bedrooms: '' });
    expect(r.success).toBe(true);
    expect(r.success && r.data.plot_width).toBe(30);
    expect(r.success && r.data.bedrooms).toBeUndefined();
  });

  it('accepts a description without plot fields', () => {
    expect(briefFormSchema.safeParse({ ...base, prompt: '3 BHK on 30x45 ft' }).success).toBe(true);
  });

  it('rejects only one plot side, or nothing at all', () => {
    expect(briefFormSchema.safeParse({ ...base, plot_width: 30 }).success).toBe(false);
    expect(briefFormSchema.safeParse(base).success).toBe(false);
  });
});

describe('ConfirmationCard', () => {
  it('shows the summary, the conflict and assumptions, and generates', () => {
    const onGenerate = vi.fn();
    render(<ConfirmationCard parsed={PARSED} busy={false} onBack={() => {}} onGenerate={onGenerate} />);
    expect(screen.getByText(/5 bedrooms \(1 with attached bath\)/)).toBeDefined();
    expect(screen.getByText(/the form said 4, the description said 5/)).toBeDefined();
    expect(screen.getByText(/40' × 50'/)).toBeDefined();
    expect(screen.getByText(/planned as a residential home/)).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: /generate plan/i }));
    expect(onGenerate).toHaveBeenCalled();
  });

  it('blocks generating while something is missing', () => {
    render(
      <ConfirmationCard
        parsed={{ ...PARSED, ready: false, missing: ['plot size'] }}
        busy={false}
        onBack={() => {}}
        onGenerate={() => {}}
      />,
    );
    expect(screen.getByText('plot size')).toBeDefined();
    expect((screen.getByRole('button', { name: /generate plan/i }) as HTMLButtonElement).disabled).toBe(true);
  });
});

describe('ProgressSteps', () => {
  it('shows progress and the failure with options', () => {
    const onRetry = vi.fn();
    render(
      <ProgressSteps
        events={[
          ev('queued', 0),
          ev('feasibility', 5),
          ev('failed', 5, { status: 'failed', error: 'The rooms need 120 m2.', options: ['Use 3 bedrooms'] }),
        ]}
        onRetry={onRetry}
      />,
    );
    expect(screen.getByText('The rooms need 120 m2.')).toBeDefined();
    expect(screen.getByText('Use 3 bedrooms')).toBeDefined();
    fireEvent.click(screen.getByText(/change the brief/i));
    expect(onRetry).toHaveBeenCalled();
  });
});

describe('FloorplanPage', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('sends the form and shows the confirmation card', async () => {
    const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => {
      if (url.includes('/floorplans/brief/parse')) {
        return new Response(JSON.stringify(PARSED), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }
      return new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } });
    });
    vi.stubGlobal('fetch', fetchMock);
    render(
      <MemoryRouter>
        <AuthProvider>
          <ProjectProvider>
            <FloorplanPage />
          </ProjectProvider>
        </AuthProvider>
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText(/describe the house/i), { target: { value: '5 bedrooms on 40x50 ft' } });
    fireEvent.click(screen.getByRole('button', { name: /check my brief/i }));
    await waitFor(() => expect(screen.getByText(/is this right\?/i)).toBeDefined());
    const call = fetchMock.mock.calls.find(([u]) => String(u).includes('/brief/parse'));
    expect(call).toBeDefined();
    const body = JSON.parse(String(call?.[1]?.body));
    expect(body.prompt).toBe('5 bedrooms on 40x50 ft');
    expect(body).not.toHaveProperty('plot_width');
  });
});
