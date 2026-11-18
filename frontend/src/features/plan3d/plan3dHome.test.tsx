import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { ProjectProvider } from '../../context/ProjectContext';
import { TOKEN_STORAGE_KEY } from '../../lib/api';
import { Plan3dFurniturePage } from './Plan3dFurniturePage';
import { Plan3dHomePage } from './Plan3dHomePage';
import {
  API,
  BASE,
  EMBED_BASE,
  type FetchMock,
  type MockRoutes,
  RAW_SYSTEM,
  authorizationOf,
  callsTo,
  json,
  mockFetch,
  noContent,
  rawFurnitureEmbed,
  rawJob,
} from './plan3dFixture';

const PROJECT_ID = '0b9d7c1e-6f55-4f0a-9d3b-2f7a5c1e8d40';
const NEW_JOB = 'ffeeddccbbaa';

const JOBS = [
  rawJob({ job_id: 'aaaaaaaaaaaa', name: 'green-villa.pdf', stage: 'done', quality: 'medium', build_seconds: 200 }),
  rawJob({ job_id: 'bbbbbbbbbbbb', name: 'sample_plan.pdf', source: 'sample', stage: 'detected' }),
  rawJob({ job_id: 'cccccccccccc', name: 'office.pdf', stage: 'building', quality: 'low', progress: 40 }),
  rawJob({ job_id: 'dddddddddddd', name: 'scan.pdf', stage: 'failed', floors: [], message: 'This drawing could not be read.' }),
];

/** The API as it answers when all is well; a test replaces the answers it is about. */
function mockApi(routes: MockRoutes = {}): FetchMock {
  return mockFetch({
    'GET /api/v1/projects': () => json([]),
    'GET /api/v1/parsing/upload-limits': () => json({ max_pdf_mb: 8, max_pdf_pages: 4 }),
    [`GET ${BASE}/system`]: () => json(RAW_SYSTEM),
    [`GET ${BASE}/jobs`]: () => json(JOBS),
    [`POST ${BASE}/jobs`]: () => json({ job_id: NEW_JOB }, 201),
    [`POST ${BASE}/jobs/sample`]: () => json({ job_id: NEW_JOB }, 201),
    ...routes,
  });
}

function Where() {
  return <div data-testid="where">{useLocation().pathname}</div>;
}

function renderPage() {
  render(
    <MemoryRouter initialEntries={['/3d']}>
      <ProjectProvider>
        <Routes>
          <Route path="/3d" element={<Plan3dHomePage />} />
          <Route path="*" element={<Where />} />
        </Routes>
      </ProjectProvider>
    </MemoryRouter>,
  );
}

/** A saved project, chosen in the app and present in the account. */
function chooseProject(routes: MockRoutes = {}): FetchMock {
  localStorage.setItem(
    'construtiva_active_project',
    JSON.stringify({ id: PROJECT_ID, name: 'Green Villa', type: 'Residential', createdAt: '', updatedAt: '', status: 'ready' }),
  );
  return mockApi({
    'GET /api/v1/projects': () => json([{ id: PROJECT_ID, name: 'Green Villa', description: '[Residential] A house', status: 'active' }]),
    ...routes,
  });
}

const pdf = (name = 'green-villa.pdf') => new File(['%PDF-1.7'], name, { type: 'application/pdf' });

function pick(file: File) {
  fireEvent.change(screen.getByLabelText('Floor plan PDF'), { target: { files: [file] } });
}

const plans = () => within(screen.getByRole('region', { name: 'Your plans' }));
/** The account's projects and plans have arrived, so a plan can be started. */
const loaded = () => plans().findByText('sample_plan.pdf');
const rowOf = (name: string): HTMLElement => {
  const row = plans().getByText(name).closest('li');
  if (!row) throw new Error(`no row for ${name}`);
  return row;
};

describe('2D to 3D home page', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem(TOKEN_STORAGE_KEY, 'test-jwt-token');
    vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('shows no banner when the 3D builder is ready', async () => {
    const fetchMock = mockApi();
    renderPage();
    expect(screen.getByRole('heading', { name: '2D Plan to 3D' })).toBeDefined();
    await plans().findByText('green-villa.pdf');
    expect(screen.queryByRole('alert')).toBeNull();
    expect(authorizationOf(callsTo(fetchMock, 'GET', `${BASE}/system`)[0])).toBe('Bearer test-jwt-token');
  });

  it('says so when the 3D builder cannot be reached, and checks again on request', async () => {
    let up = false;
    const down = {
      reachable: false,
      ready: false,
      checks: {},
      detail: 'The 3D builder is not running right now. Please try again in a moment.',
      qualities: RAW_SYSTEM.qualities.map((quality) => ({ ...quality, available: false })),
    };
    const fetchMock = mockApi({ [`GET ${BASE}/system`]: () => json(up ? RAW_SYSTEM : down) });
    renderPage();
    const banner = await screen.findByRole('alert');
    expect(banner.textContent).toContain('The 3D builder is not running right now. Please try again in a moment.');

    up = true;
    fireEvent.click(within(banner).getByRole('button', { name: 'Check again' }));
    await waitFor(() => expect(screen.queryByRole('alert')).toBeNull());
    expect(callsTo(fetchMock, 'GET', `${BASE}/system`)).toHaveLength(2);
  });

  it('names what the 3D builder is missing when it is not set up', async () => {
    const checks = {
      blender: { ok: false, version: '' },
      pdf_tools: { ok: false },
      viewer: { ok: true },
      materials: { ok: false, running: true, done: 3, total: 40, failed: [] },
    };
    mockApi({ [`GET ${BASE}/system`]: () => json({ ...RAW_SYSTEM, ready: false, checks }) });
    renderPage();
    expect((await screen.findByRole('alert')).textContent).toContain(
      'The 3D builder is not set up yet. Missing: Blender, PDF tools, materials.',
    );
  });

  it("shows the server's upload limits and refuses a file that is not a PDF, or too large", async () => {
    const fetchMock = mockApi();
    renderPage();
    expect(screen.getByText(/drag and drop your floor plan pdf here/i)).toBeDefined();
    await loaded();
    expect(await screen.findByText('Max Size: 8 MB')).toBeDefined();
    expect(screen.getByText('Up to 4 pages')).toBeDefined();
    const upload = screen.getByRole('button', { name: 'Upload plan' });
    expect(upload.hasAttribute('disabled')).toBe(true);

    pick(new File(['x'], 'plan.png', { type: 'image/png' }));
    expect(screen.getByRole('alert').textContent).toMatch(/as a PDF file/i);
    expect(upload.hasAttribute('disabled')).toBe(true);

    pick(new File([new Uint8Array(9 * 1024 * 1024)], 'huge.pdf', { type: 'application/pdf' }));
    expect(screen.getByRole('alert').textContent).toBe('This PDF is 9.0 MB. The largest file accepted is 8 MB.');
    expect(upload.hasAttribute('disabled')).toBe(true);

    pick(new File([], 'empty.pdf', { type: 'application/pdf' }));
    expect(screen.getByRole('alert').textContent).toMatch(/empty/i);

    pick(pdf('my-house.pdf'));
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByText('my-house.pdf')).toBeDefined();
    expect(upload.hasAttribute('disabled')).toBe(false);

    fireEvent.click(screen.getByRole('button', { name: 'Remove file' }));
    expect(upload.hasAttribute('disabled')).toBe(true);
    // nothing was sent for any of this
    expect(callsTo(fetchMock, 'POST', `${BASE}/jobs`)).toHaveLength(0);
  });

  it('uploads the PDF and goes to the page of the new job', async () => {
    const fetchMock = mockApi();
    renderPage();
    await loaded();
    pick(pdf());
    fireEvent.click(screen.getByRole('button', { name: 'Upload plan' }));
    expect(screen.getByText('Uploading the PDF…').getAttribute('role')).toBe('status');
    expect(screen.getByRole('button', { name: 'Try the sample plan' }).hasAttribute('disabled')).toBe(true);
    expect((await screen.findByTestId('where')).textContent).toBe(`/3d/${NEW_JOB}`);

    const [request] = callsTo(fetchMock, 'POST', `${BASE}/jobs`);
    expect(request.url.href).toBe(`${API}${BASE}/jobs`);
    expect(authorizationOf(request)).toBe('Bearer test-jwt-token');
    const body = request.init.body;
    if (!(body instanceof FormData)) throw new Error('the PDF was not sent as a form');
    const sent = body.get('file');
    expect(sent instanceof File && sent.name).toBe('green-villa.pdf');
    // no project is chosen (the app's placeholder project is not one of the account's)
    expect(body.has('project_id')).toBe(false);
    // the browser sets the multipart content type itself
    expect(new Headers(request.init.headers).has('Content-Type')).toBe(false);
  });

  it('starts the sample plan and goes to its page', async () => {
    const fetchMock = mockApi();
    renderPage();
    await loaded();
    fireEvent.click(screen.getByRole('button', { name: 'Try the sample plan' }));
    expect((await screen.findByTestId('where')).textContent).toBe(`/3d/${NEW_JOB}`);
    const [request] = callsTo(fetchMock, 'POST', `${BASE}/jobs/sample`);
    expect(request.url.search).toBe('');
    expect(authorizationOf(request)).toBe('Bearer test-jwt-token');
    expect(callsTo(fetchMock, 'POST', `${BASE}/jobs`)).toHaveLength(0);
  });

  it('says why an upload was refused, and stays on the page', async () => {
    let attempts = 0;
    const fetchMock = mockApi({
      [`POST ${BASE}/jobs`]: () =>
        ++attempts === 1
          ? json({ detail: 'The 3D builder is not running right now. Please try again in a moment.' }, 503)
          : json({ job_id: NEW_JOB }, 201),
    });
    renderPage();
    await loaded();
    pick(pdf());
    fireEvent.click(screen.getByRole('button', { name: 'Upload plan' }));
    expect((await screen.findByRole('alert')).textContent).toBe(
      'The 3D builder is not running right now. Please try again in a moment.',
    );
    expect(screen.queryByTestId('where')).toBeNull();
    // the file is still there: the person can simply try again
    const upload = screen.getByRole('button', { name: 'Upload plan' });
    expect(upload.hasAttribute('disabled')).toBe(false);
    fireEvent.click(upload);
    expect((await screen.findByTestId('where')).textContent).toBe(`/3d/${NEW_JOB}`);
    expect(callsTo(fetchMock, 'POST', `${BASE}/jobs`)).toHaveLength(2);
  });

  it("passes on the server's own reason for refusing a PDF, and for the sample plan", async () => {
    mockApi({
      [`POST ${BASE}/jobs`]: () => json({ detail: 'This PDF has 12 pages. The most accepted is 4.' }, 413),
      [`POST ${BASE}/jobs/sample`]: () => json({ detail: 'The sample plan is missing from the 3D builder.' }, 502),
    });
    renderPage();
    await loaded();
    pick(pdf());
    fireEvent.click(screen.getByRole('button', { name: 'Upload plan' }));
    expect((await screen.findByRole('alert')).textContent).toBe('This PDF has 12 pages. The most accepted is 4.');
    fireEvent.click(screen.getByRole('button', { name: 'Try the sample plan' }));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toBe('The sample plan is missing from the 3D builder.'));
  });

  it('lists the plans with their stage in plain words, the quality when built, and a link to open each', async () => {
    mockApi();
    renderPage();
    await plans().findByText('green-villa.pdf');
    expect(plans().getAllByRole('listitem')).toHaveLength(4);
    expect(rowOf('green-villa.pdf').textContent).toContain('3D house ready • Medium quality');
    expect(rowOf('sample_plan.pdf').textContent).toContain('Ready to review');
    expect(rowOf('office.pdf').textContent).toContain('Building the 3D house');
    expect(rowOf('office.pdf').textContent).not.toContain('quality'); // not built yet
    expect(rowOf('scan.pdf').textContent).toContain('Drawing could not be read');
    expect(within(rowOf('green-villa.pdf')).getByRole('link', { name: 'Open green-villa.pdf' }).getAttribute('href')).toBe(
      '/3d/aaaaaaaaaaaa',
    );
    expect(plans().getByRole('link', { name: 'Furniture models' }).getAttribute('href')).toBe('/3d/furniture');
  });

  it('says so when there are no plans, and when the list cannot be loaded', async () => {
    let fail = false;
    mockApi({ [`GET ${BASE}/jobs`]: () => (fail ? json({ detail: 'The 3D builder answered with an error (500).' }, 500) : json([])) });
    renderPage();
    expect(await plans().findByText(/no plans yet/i)).toBeDefined();

    fail = true;
    fireEvent.click(plans().getByRole('button', { name: 'Refresh' }));
    const alert = await plans().findByRole('alert');
    expect(alert.textContent).toContain('Your plans could not be loaded. The 3D builder answered with an error (500).');
    fail = false;
    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }));
    expect(await plans().findByText(/no plans yet/i)).toBeDefined();
  });

  it('deletes a plan only after the person confirms', async () => {
    const fetchMock = mockApi({ [`DELETE ${BASE}/jobs/bbbbbbbbbbbb`]: () => noContent() });
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    renderPage();
    await plans().findByText('sample_plan.pdf');

    fireEvent.click(plans().getByRole('button', { name: 'Delete sample_plan.pdf' }));
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(String(confirm.mock.calls[0][0])).toContain('sample_plan.pdf');
    expect(callsTo(fetchMock, 'DELETE', `${BASE}/jobs/bbbbbbbbbbbb`)).toHaveLength(0);
    expect(plans().getByText('sample_plan.pdf')).toBeDefined();

    confirm.mockReturnValue(true);
    fireEvent.click(plans().getByRole('button', { name: 'Delete sample_plan.pdf' }));
    await waitFor(() => expect(plans().queryByText('sample_plan.pdf')).toBeNull());
    expect(plans().getAllByRole('listitem')).toHaveLength(3);
    const [request] = callsTo(fetchMock, 'DELETE', `${BASE}/jobs/bbbbbbbbbbbb`);
    expect(authorizationOf(request)).toBe('Bearer test-jwt-token');
    // the list was not asked for again
    expect(callsTo(fetchMock, 'GET', `${BASE}/jobs`).length).toBeLessThanOrEqual(2);
  });

  it('keeps a plan that cannot be deleted while it is being built', async () => {
    mockApi({ [`DELETE ${BASE}/jobs/cccccccccccc`]: () => json({ detail: 'a build is already running' }, 409) });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderPage();
    await plans().findByText('office.pdf');
    fireEvent.click(plans().getByRole('button', { name: 'Delete office.pdf' }));
    expect((await plans().findByRole('alert')).textContent).toBe('"office.pdf" could not be deleted. a build is already running');
    expect(plans().getByText('office.pdf')).toBeDefined();
    expect(plans().getByRole('button', { name: 'Delete office.pdf' }).hasAttribute('disabled')).toBe(false);
  });

  it("stores new plans in the chosen project and lists that project's plans", async () => {
    const fetchMock = chooseProject();
    renderPage();
    expect(await screen.findByText('In the project Green Villa')).toBeDefined();
    await plans().findByText('green-villa.pdf');
    const listed = callsTo(fetchMock, 'GET', `${BASE}/jobs`);
    expect(listed[listed.length - 1].url.searchParams.get('project_id')).toBe(PROJECT_ID);

    pick(pdf());
    fireEvent.click(screen.getByRole('button', { name: 'Upload plan' }));
    expect((await screen.findByTestId('where')).textContent).toBe(`/3d/${NEW_JOB}`);
    const body = callsTo(fetchMock, 'POST', `${BASE}/jobs`)[0].init.body;
    expect(body instanceof FormData && body.get('project_id')).toBe(PROJECT_ID);
  });

  it('starts the sample plan in the chosen project, and can list the plans of every project', async () => {
    const fetchMock = chooseProject();
    renderPage();
    await screen.findByText('In the project Green Villa');
    await plans().findByText('green-villa.pdf');

    fireEvent.click(plans().getByRole('button', { name: 'Show all plans' }));
    expect(await screen.findByText('From all your projects')).toBeDefined();
    await plans().findByText('green-villa.pdf');
    const listed = callsTo(fetchMock, 'GET', `${BASE}/jobs`);
    expect(listed[listed.length - 1].url.search).toBe('');
    expect(plans().getByRole('button', { name: 'Show this project only' })).toBeDefined();

    fireEvent.click(screen.getByRole('button', { name: 'Try the sample plan' }));
    expect((await screen.findByTestId('where')).textContent).toBe(`/3d/${NEW_JOB}`);
    expect(callsTo(fetchMock, 'POST', `${BASE}/jobs/sample`)[0].url.searchParams.get('project_id')).toBe(PROJECT_ID);
  });

  it('does not start a plan before it is known which project it belongs to', async () => {
    let answerProjects: (answer: Response) => void = () => {};
    const fetchMock = chooseProject({ 'GET /api/v1/projects': () => new Promise<Response>((resolve) => (answerProjects = resolve)) });
    renderPage();
    pick(pdf());
    const upload = screen.getByRole('button', { name: 'Upload plan' });
    const sample = screen.getByRole('button', { name: 'Try the sample plan' });
    await waitFor(() => expect(callsTo(fetchMock, 'GET', '/api/v1/projects')).toHaveLength(1));
    expect(upload.hasAttribute('disabled')).toBe(true);
    expect(sample.hasAttribute('disabled')).toBe(true);
    expect(plans().getByText('Loading your plans…')).toBeDefined();

    answerProjects(json([{ id: PROJECT_ID, name: 'Green Villa', description: '[Residential] A house', status: 'active' }]));
    await waitFor(() => expect(upload.hasAttribute('disabled')).toBe(false));
    expect(sample.hasAttribute('disabled')).toBe(false);
    fireEvent.click(upload);
    expect((await screen.findByTestId('where')).textContent).toBe(`/3d/${NEW_JOB}`);
    const body = callsTo(fetchMock, 'POST', `${BASE}/jobs`)[0].init.body;
    expect(body instanceof FormData && body.get('project_id')).toBe(PROJECT_ID);
  });

  it('sends no project when none of the account is chosen', async () => {
    const fetchMock = mockApi();
    renderPage();
    await plans().findByText('green-villa.pdf');
    expect(screen.queryByText(/in the project/i)).toBeNull();
    expect(plans().queryByRole('button', { name: 'Show all plans' })).toBeNull();
    for (const request of callsTo(fetchMock, 'GET', `${BASE}/jobs`)) expect(request.url.search).toBe('');
  });
});

describe('furniture models page', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem(TOKEN_STORAGE_KEY, 'test-jwt-token');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  const renderFurniture = () =>
    render(
      <MemoryRouter initialEntries={['/3d/furniture']}>
        <Plan3dFurniturePage />
      </MemoryRouter>,
    );

  it('shows the furniture models in an iframe, with a link that needs no job', async () => {
    const fetchMock = mockFetch({ [`POST ${BASE}/embed`]: () => json(rawFurnitureEmbed()) });
    renderFurniture();
    expect(screen.getByRole('heading', { name: 'Furniture models' })).toBeDefined();
    const frame = await screen.findByTitle('Furniture models');
    expect(frame.getAttribute('src')).toBe(`${API}${EMBED_BASE}/web/furniture.html?embed`);
    expect(screen.getByRole('link', { name: 'All plans' }).getAttribute('href')).toBe('/3d');
    const [request] = callsTo(fetchMock, 'POST', `${BASE}/embed`);
    expect(authorizationOf(request)).toBe('Bearer test-jwt-token');
    // that one request is all: no job is involved
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('offers to try again when the link cannot be made', async () => {
    let attempts = 0;
    mockFetch({
      [`POST ${BASE}/embed`]: () => (++attempts === 1 ? json({ detail: 'Try again in a moment.' }, 503) : json(rawFurnitureEmbed())),
    });
    renderFurniture();
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('The furniture models could not be opened. Try again in a moment.');
    expect(screen.queryByTitle('Furniture models')).toBeNull();
    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }));
    expect(await screen.findByTitle('Furniture models')).toBeDefined();
    expect(screen.queryByRole('alert')).toBeNull();
  });
});

describe('build notifications', () => {
  beforeEach(() => {
    localStorage.setItem(TOKEN_STORAGE_KEY, 'test-token');
  });
  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it('lists finished builds with a link to each', async () => {
    mockApi({
      [`GET ${BASE}/notifications`]: () =>
        json({
          email: true,
          items: [{ job_id: 'aaaaaaaaaaaa', outcome: 'done', title: 'Your 3D house is ready', quality: 'high', at: '2026-11-19T02:00:00+00:00' }],
        }),
      [`PUT ${BASE}/notifications/settings`]: () => json({ email: false }),
    });
    renderPage();
    const notices = await screen.findByRole('region', { name: 'Build notifications' });
    fireEvent.click(within(notices).getByRole('link', { name: 'Your 3D house is ready' }));
    expect(screen.getByTestId('where').textContent).toBe('/3d/aaaaaaaaaaaa');
  });

  it('saves the email switch', async () => {
    const fetchMock = mockApi({
      [`GET ${BASE}/notifications`]: () => json({ email: true, items: [] }),
      [`PUT ${BASE}/notifications/settings`]: () => json({ email: false }),
    });
    renderPage();
    const box = await screen.findByRole('checkbox', { name: /email me/i });
    fireEvent.click(box);
    await waitFor(() => expect((box as HTMLInputElement).checked).toBe(false));
    const [put] = callsTo(fetchMock, 'PUT', `${BASE}/notifications/settings`);
    expect(JSON.parse(String(put.init.body))).toEqual({ email: false });
  });
});
