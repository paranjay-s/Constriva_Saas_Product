import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider } from '../../context/AuthContext';
import { ProjectProvider } from '../../context/ProjectContext';
import { FloorplanPage } from './FloorplanPage';
import { floorplanApi } from './api';
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

  it('shows how spoken words were read, to confirm', () => {
    const parsed = {
      ...PARSED,
      brief: { ...PARSED.brief, interpretation: ['I read “four year” as “foyer”.'] },
    };
    render(<ConfirmationCard parsed={parsed} busy={false} onBack={() => {}} onGenerate={() => {}} />);
    expect(screen.getByText('I read your words as')).toBeDefined();
    expect(screen.getByText(/“four year” as “foyer”/)).toBeDefined();
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

const PROJECT = {
  id: '11111111-1111-4111-8111-111111111111',
  name: 'Sharma Residence',
  description: '[Residential] villa',
  status: 'active',
  created_at: '2026-11-01T00:00:00Z',
};

function renderPage(projects: unknown[]) {
  const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => {
    const json = (body: unknown, status = 200) =>
      new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
    if (url.includes('/floorplans/brief/parse')) return json(PARSED);
    if (url.includes('/floorplans/generate')) return json({ job_id: 'job-1' }, 202);
    if (url.endsWith('/api/v1/projects')) return json(projects);
    return json([]);
  });
  vi.stubGlobal('fetch', fetchMock);
  localStorage.clear();
  render(
    <MemoryRouter>
      <AuthProvider>
        <ProjectProvider>
          <FloorplanPage />
        </ProjectProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
  return fetchMock;
}

describe('FloorplanPage (chat)', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('starts with the greeting, the composer and the project picker in the middle', async () => {
    renderPage([]);
    expect(screen.getByLabelText(/describe the house/i)).toBeDefined();
    expect(screen.getByRole('button', { name: /choose project/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /3 BHK on 30×40 ft/i })).toBeDefined();
  });

  it('reads the brief from a typed prompt and shows the confirmation card in the chat', async () => {
    const fetchMock = renderPage([PROJECT]);
    fireEvent.change(screen.getByLabelText(/describe the house/i), { target: { value: '5 bedrooms on 40x50 ft' } });
    fireEvent.click(screen.getByRole('button', { name: /^send$/i }));
    await waitFor(() => expect(screen.getByText(/is this right\?/i)).toBeDefined());
    expect(screen.getByText('5 bedrooms on 40x50 ft')).toBeDefined(); // the user's message
    const call = fetchMock.mock.calls.find(([u]) => String(u).includes('/brief/parse'));
    const body = JSON.parse(String(call?.[1]?.body));
    expect(body.prompt).toBe('5 bedrooms on 40x50 ft');
    expect(body).not.toHaveProperty('plot_width');
  });

  it('asks for a project before generating, then generates inside it', async () => {
    const fetchMock = renderPage([PROJECT]);
    fireEvent.change(screen.getByLabelText(/describe the house/i), { target: { value: '5 bedrooms on 40x50 ft' } });
    fireEvent.click(screen.getByRole('button', { name: /^send$/i }));
    await waitFor(() => expect(screen.getByText(/is this right\?/i)).toBeDefined());
    fireEvent.click(screen.getByRole('button', { name: /generate plan/i }));
    expect(await screen.findByText(/choose the project to save this plan in/i)).toBeDefined();
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes('/generate'))).toBe(false);

    fireEvent.click(await screen.findByRole('menuitemradio', { name: /sharma residence/i }));
    fireEvent.click(screen.getByRole('button', { name: /generate plan/i }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u).includes('/generate'))).toBe(true));
    const gen = fetchMock.mock.calls.find(([u]) => String(u).includes('/generate'));
    expect(JSON.parse(String(gen?.[1]?.body)).project_id).toBe(PROJECT.id);
    expect(await screen.findByText(/drawing the plan/i)).toBeDefined();
  });

  it('sends the villa and owner names for the title block', async () => {
    const fetchMock = renderPage([PROJECT]);
    fireEvent.change(screen.getByLabelText(/describe the house/i), { target: { value: '5 bedrooms on 40x50 ft' } });
    fireEvent.click(screen.getByRole('button', { name: /^send$/i }));
    await waitFor(() => expect(screen.getByText(/is this right\?/i)).toBeDefined());
    fireEvent.click(screen.getByRole('button', { name: /generate plan/i }));
    fireEvent.click(await screen.findByRole('menuitemradio', { name: /sharma residence/i }));
    // the villa name defaults to the chosen project's name
    expect((screen.getByLabelText(/villa \/ project name/i) as HTMLInputElement).value).toMatch(/sharma residence/i);
    fireEvent.change(screen.getByLabelText(/villa \/ project name/i), { target: { value: 'Granite Villa' } });
    fireEvent.change(screen.getByLabelText(/owner name/i), { target: { value: 'Mr. A. Sharma' } });
    fireEvent.click(screen.getByRole('button', { name: /generate plan/i }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u).includes('/generate'))).toBe(true));
    const gen = fetchMock.mock.calls.find(([u]) => String(u).includes('/generate'));
    const body = JSON.parse(String(gen?.[1]?.body));
    const brief = body.brief ?? body;
    expect(brief.project_name).toBe('Granite Villa');
    expect(brief.owner_name).toBe('Mr. A. Sharma');
  });
});

describe('plan views', () => {
  it('PDF, PNG and SVG follow the presentation view; DXF, DWG and IFC stay engineering', async () => {
    const urls: string[] = [];
    const fetchMock = vi.fn(async (url: string) => {
      urls.push(url);
      return new Response('x', { status: 200, headers: { 'content-disposition': 'attachment; filename="p.pdf"' } });
    });
    vi.stubGlobal('fetch', fetchMock);
    const create = vi.fn(() => 'blob:x');
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: create, revokeObjectURL: vi.fn() }));
    await floorplanApi.download('p1', 'pdf', 200, 'presentation');
    await floorplanApi.download('p1', 'dxf', 200, 'presentation');
    await floorplanApi.download('p1', 'pdf', 200, 'engineering');
    expect(urls[0]).toContain('format=pdf');
    expect(urls[0]).toContain('view=presentation');
    expect(urls[1]).not.toContain('view=');
    expect(urls[2]).not.toContain('view=');
    vi.unstubAllGlobals();
  });
});
