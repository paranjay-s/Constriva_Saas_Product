/**
 * The dashboard pages show what the backend returns, and send what the person typed.
 * fetch is replaced by a small router that answers with payloads shaped like the real API.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider } from '../../context/AuthContext';
import { ProjectProvider } from '../../context/ProjectContext';
import { TOKEN_STORAGE_KEY } from '../../lib/api';
import { AuthPage } from '../auth/AuthPage';
import { HomePage } from '../home/HomePage';
import { CreateProjectPage } from '../projects/CreateProjectPage';
import { ProjectOptionsPage } from '../projects/ProjectOptionsPage';
import { DashHeader, initialsOf, moduleFor } from './DashHeader';
import { Skyline, skylineSummary } from './Skyline';
import { dayLabel } from './format';

// ------------------------------------------------------------------ fake backend

interface Reply {
  status?: number;
  body: unknown;
}
type Route = Reply | ((body: unknown) => Reply);
interface Call {
  method: string;
  path: string;
  body: unknown;
  auth: string | null;
}

function mockApi(routes: Record<string, Route>): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = new URL(String(input));
      const method = (init.method || 'GET').toUpperCase();
      const body = typeof init.body === 'string' ? JSON.parse(init.body) : undefined;
      calls.push({ method, path: url.pathname, body, auth: new Headers(init.headers).get('Authorization') });
      const route = routes[`${method} ${url.pathname}`];
      const reply: Reply = !route
        ? { status: 404, body: { detail: `no mock for ${method} ${url.pathname}` } }
        : typeof route === 'function'
          ? route(body)
          : route;
      return new Response(JSON.stringify(reply.body), {
        status: reply.status ?? 200,
        headers: { 'content-type': 'application/json' },
      });
    }),
  );
  return calls;
}

const ME = { id: 'u1', email: 'asha@studio.example', full_name: 'Asha Verma' };
const NOW = new Date().toISOString();

const PROJECTS = [
  { id: 'p1', name: 'Courtyard House', description: '[Residential] 3-bedroom home with an open courtyard.', status: 'active', created_at: NOW },
  { id: 'p2', name: 'Lakeview Office', description: '[Commercial] Two floors by the lake.', status: 'active', created_at: '2026-11-09T10:00:00Z' },
  { id: 'p3', name: 'Studio Refit', description: '[Interior]', status: 'draft', created_at: '2026-11-02T10:00:00Z' },
];
const PLANS = [
  { id: 'f1', project_id: 'p1', name: '3 BHK on 30 x 40 ft', version: 3, created_at: '2026-11-17T09:00:00Z' },
  { id: 'f2', project_id: 'p1', name: 'Courtyard option B', version: 1, created_at: '2026-11-12T09:00:00Z' },
  { id: 'f3', project_id: 'p2', name: 'Open office', version: 2, created_at: '2026-11-10T09:00:00Z' },
];
const ANALYSES = [
  { id: 'a1', title: 'Living room', scene: 'living room', created_at: '2026-11-18T08:00:00Z', materials: 3 },
  { id: 'a2', title: '', scene: 'kitchen', created_at: '2026-11-01T08:00:00Z', materials: 1 },
];
const DATA_ROUTES: Record<string, Route> = {
  'GET /api/v1/auth/me': { body: ME },
  'GET /api/v1/projects': { body: PROJECTS },
  'GET /api/v1/ai/floorplans': { body: PLANS },
  'GET /api/v1/ai/material-analysis': { body: ANALYSES },
};

function signedIn() {
  localStorage.setItem(TOKEN_STORAGE_KEY, 'test-token');
}

function activeProject(p: { id: string; name: string } | null) {
  if (!p) return localStorage.setItem('construtiva_active_project', 'null');
  localStorage.setItem(
    'construtiva_active_project',
    JSON.stringify({ ...p, type: 'Residential', createdAt: NOW, updatedAt: NOW, status: 'ready' }),
  );
}

function renderApp(ui: ReactElement, path = '/home', extra?: ReactElement) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <ProjectProvider>
          <Routes>
            <Route path={path.split('?')[0]} element={ui} />
            {extra}
            <Route path="*" element={<p data-testid="elsewhere" />} />
          </Routes>
        </ProjectProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
  sessionStorage.clear();
});

// ------------------------------------------------------------------------ overview

describe('project overview', () => {
  it('shows the projects, floor plans and image analyses the backend returns', async () => {
    signedIn();
    const calls = mockApi(DATA_ROUTES);
    renderApp(<HomePage />);

    await waitFor(() => expect(screen.getByTestId('count-projects').textContent).toBe('3'));
    await waitFor(() => expect(screen.getByTestId('count-plans').textContent).toBe('3 floor plans'));
    await waitFor(() => expect(screen.getByTestId('count-analyses').textContent).toBe('2 image analyses'));

    // every project by name, with its type and status from the backend
    const list = screen.getByText('Your projects').closest('.cv-card') as HTMLElement;
    for (const p of PROJECTS) expect(within(list).getByText(p.name)).toBeDefined();
    expect(within(list).getByText(/Commercial · ready · 1 plan/)).toBeDefined();
    expect(within(list).getByText(/Interior · draft · no plans yet/)).toBeDefined();

    // the newest project is open and lists its own plans with their versions
    const open = within(list).getByRole('article', { name: 'Courtyard House' });
    expect(within(open).getByText('3-bedroom home with an open courtyard.')).toBeDefined();
    expect(within(open).getByText('2D FLOOR PLANS (2)')).toBeDefined();
    expect(within(open).getByText('3 BHK on 30 x 40 ft')).toBeDefined();
    expect(within(open).getByText('v3 · Open')).toBeDefined();
    expect(within(open).queryByText('Open office')).toBeNull();

    // the signed-in name comes from /auth/me
    expect(screen.getByText(/Asha Verma/)).toBeDefined();

    // every data request carried the session token
    for (const path of ['/api/v1/projects', '/api/v1/ai/floorplans', '/api/v1/ai/material-analysis']) {
      const call = calls.find((c) => c.path === path);
      expect(call?.auth, path).toBe('Bearer test-token');
    }
  });

  it('puts 2D to 3D and BOQ beside the studios, and lists each project\'s 3D houses', async () => {
    signedIn();
    const job = (id: string, name: string, project: string | null, stage: string) => ({
      job_id: id, name, project_id: project, source: 'upload', stage, progress: 100, message: '', floors: [],
      scale_source: null, eta_left: null, queue_position: null, quality: null, build_seconds: null, created_at: NOW,
    });
    const calls = mockApi({
      ...DATA_ROUTES,
      'GET /api/v1/3d/jobs': { body: [job('aaaaaaaaaaa1', 'Villa ground floor', 'p1', 'done'), job('aaaaaaaaaaa2', 'Loose upload', null, 'detected')] },
    });
    renderApp(<HomePage />, '/home', <Route path="/3d/:jobId" element={<p data-testid="house-page" />} />);

    expect(screen.getByRole('link', { name: '2D to 3D' }).getAttribute('href')).toBe('/3d');
    expect(screen.getByRole('link', { name: 'BOQ raw materials' }).getAttribute('href')).toBe('/boq');
    await waitFor(() => expect(screen.getByTestId('count-houses').textContent).toBe('2 3D houses'));

    const open = screen.getByRole('article', { name: 'Courtyard House' });
    expect(within(open).getByText('3D HOUSES (1)')).toBeDefined();
    expect(calls.find((c) => c.path === '/api/v1/3d/jobs')?.auth).toBe('Bearer test-token');
    fireEvent.click(within(open).getByRole('button', { name: /Villa ground floor/ }));
    expect(await screen.findByTestId('house-page')).toBeDefined();
  });

  it('draws one building per project, one storey per plan and one frame per analysis', async () => {
    signedIn();
    mockApi(DATA_ROUTES);
    const { container } = renderApp(<HomePage />);
    await waitFor(() => expect(screen.getByTestId('count-plans').textContent).toBe('3 floor plans'));
    await waitFor(() => expect(container.querySelectorAll('[data-testid="skyline-frame"]').length).toBe(2));
    const floors = [...container.querySelectorAll('[data-testid="skyline-building"]')].map((g) => g.getAttribute('data-floors'));
    expect(floors).toEqual(['2', '1', '0']);
  });

  it('lists the newest chats first, floor plans and image analyses together', async () => {
    signedIn();
    mockApi(DATA_ROUTES);
    const { container } = renderApp(<HomePage />);
    await waitFor(() => expect(container.querySelectorAll('.cv-chat').length).toBe(3));
    const rows = [...container.querySelectorAll('.cv-chat')].map((r) => r.textContent);
    expect(rows[0]).toMatch(/IMAGE.*Living room.*3 materials/);
    expect(rows[1]).toMatch(/PLAN.*3 BHK on 30 x 40 ft.*v3/);
    expect(rows[2]).toMatch(/PLAN.*Courtyard option B.*v1/);
  });

  it('opens another project when its row is clicked', async () => {
    signedIn();
    mockApi(DATA_ROUTES);
    renderApp(<HomePage />);
    fireEvent.click(await screen.findByRole('button', { name: /Lakeview Office/ }));
    const open = screen.getByRole('article', { name: 'Lakeview Office' });
    expect(within(open).getByText('Open office')).toBeDefined();
    expect(within(open).getByText('Two floors by the lake.')).toBeDefined();
  });

  it('says so when there are no projects, and shows zeros instead of sample data', async () => {
    signedIn();
    mockApi({ ...DATA_ROUTES, 'GET /api/v1/projects': { body: [] }, 'GET /api/v1/ai/floorplans': { body: [] }, 'GET /api/v1/ai/material-analysis': { body: [] } });
    renderApp(<HomePage />);
    expect(await screen.findByText('No projects yet.')).toBeDefined();
    await waitFor(() => expect(screen.getByTestId('count-plans').textContent).toBe('0 floor plans'));
    expect(screen.getByTestId('count-projects').textContent).toBe('0');
    expect(screen.getByTestId('count-analyses').textContent).toBe('0 image analyses');
    expect(screen.getByText(/No chats yet/)).toBeDefined();
  });

  it('shows the backend error instead of an empty list when projects cannot be loaded', async () => {
    signedIn();
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    mockApi({ ...DATA_ROUTES, 'GET /api/v1/projects': { status: 500, body: { detail: 'Database is unavailable' } } });
    renderApp(<HomePage />);
    expect(await screen.findByText('Database is unavailable')).toBeDefined();
    expect(screen.queryByText('No projects yet.')).toBeNull();
  });

  it('deletes a project through the API after confirmation', async () => {
    signedIn();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const calls = mockApi({ ...DATA_ROUTES, 'DELETE /api/v1/projects/p1': { body: { deleted: true, project_id: 'p1' } } });
    renderApp(<HomePage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete project Courtyard House' }));
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE' && c.path === '/api/v1/projects/p1')).toBe(true));
    await waitFor(() => expect(screen.getByTestId('count-projects').textContent).toBe('2'));
    expect(screen.queryByRole('article', { name: 'Courtyard House' })).toBeNull();
  });
});

describe('skyline', () => {
  it('caps buildings, storeys and frames and says how many are left out', () => {
    const projects = Array.from({ length: 6 }, (_, i) => ({ id: `p${i}`, name: `Project ${i}`, plans: i === 0 ? 7 : 0 }));
    const { container } = render(<Skyline projects={projects} analyses={9} />);
    const buildings = container.querySelectorAll('[data-testid="skyline-building"]');
    expect(buildings.length).toBe(4);
    expect(buildings[0].getAttribute('data-floors')).toBe('4');
    expect(container.querySelectorAll('[data-testid="skyline-frame"]').length).toBe(4);
    const text = container.textContent ?? '';
    expect(text).toContain('+3'); // 7 plans, 4 storeys drawn
    expect(text).toContain('+2 more'); // 6 projects, 4 buildings drawn
    expect(text).toContain('+5'); // 9 analyses, 4 frames drawn
  });

  it('describes the picture in words for screen readers', () => {
    expect(skylineSummary([{ id: 'a', name: 'Villa', plans: 2 }, { id: 'b', name: 'Shop', plans: 0 }], 1)).toBe(
      'Your studio as a skyline: Villa has 2 plans, Shop has no plan yet; 1 image analysis',
    );
  });
});

// ---------------------------------------------------------------- project creation

describe('project creation', () => {
  it('saves the project through the API with the chosen type, then goes to step 2', async () => {
    signedIn();
    const calls = mockApi({
      ...DATA_ROUTES,
      'POST /api/v1/projects': (body) => ({ status: 201, body: { id: 'new1', ...(body as object), created_at: NOW } }),
      'GET /api/v1/plans/project/new1': { status: 404, body: { detail: 'No plan' } },
    });
    renderApp(<CreateProjectPage />, '/projects/new', <Route path="/projects/options" element={<ProjectOptionsPage />} />);

    // step 2 is visible but locked until the project exists
    expect((screen.getByRole('button', { name: 'Import PDF drawing' }) as HTMLButtonElement).disabled).toBe(true);

    fireEvent.change(screen.getByLabelText(/project name/i), { target: { value: '  Hillside Villa ' } });
    fireEvent.click(screen.getByRole('button', { name: /Commercial/ }));
    fireEvent.change(screen.getByLabelText(/project description/i), { target: { value: 'Shops on the ground floor.' } });
    fireEvent.click(screen.getByRole('button', { name: /continue to options/i }));

    await waitFor(() => expect(screen.getByTestId('options-project').textContent).toBe('Hillside Villa'));
    const post = calls.find((c) => c.method === 'POST' && c.path === '/api/v1/projects');
    expect(post?.body).toEqual({ name: 'Hillside Villa', description: '[Commercial] Shops on the ground floor.', status: 'active' });
    expect(post?.auth).toBe('Bearer test-token');
    expect((screen.getByRole('button', { name: 'Import PDF drawing' }) as HTMLButtonElement).disabled).toBe(false);
    expect(screen.getByText('Commercial')).toBeDefined();
  });

  it('asks for a name before calling the backend', async () => {
    signedIn();
    const calls = mockApi(DATA_ROUTES);
    renderApp(<CreateProjectPage />, '/projects/new');
    fireEvent.click(screen.getByRole('button', { name: /continue to options/i }));
    expect((await screen.findByRole('alert')).textContent).toBe('Project name is required');
    expect(calls.some((c) => c.method === 'POST')).toBe(false);
  });

  it('shows the reason when the backend refuses the project', async () => {
    signedIn();
    mockApi({ ...DATA_ROUTES, 'POST /api/v1/projects': { status: 422, body: { detail: 'Project limit reached' } } });
    renderApp(<CreateProjectPage />, '/projects/new');
    fireEvent.change(screen.getByLabelText(/project name/i), { target: { value: 'One more' } });
    fireEvent.click(screen.getByRole('button', { name: /continue to options/i }));
    expect((await screen.findByRole('alert')).textContent).toBe('Project limit reached');
  });

  it('keeps step 2 locked when no project is selected', () => {
    signedIn();
    activeProject(null);
    mockApi(DATA_ROUTES);
    renderApp(<ProjectOptionsPage />, '/projects/options');
    expect(screen.getByText('No project is selected.')).toBeDefined();
    expect((screen.getByRole('button', { name: 'Launch AI plan generator' }) as HTMLButtonElement).disabled).toBe(true);
  });
});

// -------------------------------------------------------------------- 3D workspace

describe('sign in', () => {
  const session = { access_token: 'aaa.bbb.ccc', token_type: 'bearer', refresh_token: 'r1', expires_at: 4102444800, user: ME };

  function fill(email: string, password: string) {
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: email } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: password } });
  }

  it('signs in through the API, keeps the session and opens the overview', async () => {
    const calls = mockApi({ ...DATA_ROUTES, 'POST /api/v1/auth/login': { body: session } });
    renderApp(<AuthPage />, '/auth', <Route path="/home" element={<p>overview page</p>} />);
    fill('asha@studio.example', 'secret-pass');
    fireEvent.click(screen.getByRole('button', { name: /sign in to workspace/i }));
    expect(await screen.findByText('overview page')).toBeDefined();
    expect(calls.find((c) => c.path === '/api/v1/auth/login')?.body).toEqual({ email: 'asha@studio.example', password: 'secret-pass' });
    expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBe('aaa.bbb.ccc');
  });

  it('shows the reason the backend gives for a refused sign-in', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    mockApi({ ...DATA_ROUTES, 'POST /api/v1/auth/login': { status: 401, body: { detail: 'Authentication failed: Invalid login credentials' } } });
    renderApp(<AuthPage />, '/auth');
    fill('asha@studio.example', 'wrong-pass');
    fireEvent.click(screen.getByRole('button', { name: /sign in to workspace/i }));
    expect((await screen.findByRole('alert')).textContent).toBe('Authentication failed: Invalid login credentials');
    expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull();
  });

  it('creates an account through the API with the name, email and password typed', async () => {
    const calls = mockApi({ ...DATA_ROUTES, 'POST /api/v1/auth/signup': { status: 201, body: session } });
    renderApp(<AuthPage />, '/auth', <Route path="/home" element={<p>overview page</p>} />);
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));
    fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Asha Verma' } });
    fill('asha@studio.example', 'secret-pass');
    fireEvent.click(screen.getByRole('button', { name: /create studio account/i }));
    expect(await screen.findByText('overview page')).toBeDefined();
    expect(calls.find((c) => c.path === '/api/v1/auth/signup')?.body).toEqual({ full_name: 'Asha Verma', email: 'asha@studio.example', password: 'secret-pass' });
  });

  it('checks the form before calling the backend', () => {
    const calls = mockApi(DATA_ROUTES);
    renderApp(<AuthPage />, '/auth');
    fill('not-an-email', '123');
    fireEvent.click(screen.getByRole('button', { name: /sign in to workspace/i }));
    expect(screen.getByText('Please enter a valid email address')).toBeDefined();
    expect(screen.getByText('Password must be at least 6 characters')).toBeDefined();
    expect(calls.some((c) => c.method === 'POST')).toBe(false);
  });

  it('shows why the last session ended', () => {
    sessionStorage.setItem('construtiva_session_notice', 'Your session has expired. Please sign in again.');
    mockApi(DATA_ROUTES);
    renderApp(<AuthPage />, '/auth');
    expect(screen.getByRole('status').textContent).toBe('Your session has expired. Please sign in again.');
  });
});

// -------------------------------------------------------------------------- header

describe('dashboard header', () => {
  it('shows the account from /auth/me and signs out', async () => {
    signedIn();
    mockApi(DATA_ROUTES);
    renderApp(<DashHeader />, '/home');
    await waitFor(() => expect(screen.getByRole('button', { name: 'Account' }).textContent).toBe('AV'));
    fireEvent.click(screen.getByRole('button', { name: 'Account' }));
    expect(screen.getByText('Asha Verma')).toBeDefined();
    expect(screen.getByText('asha@studio.example')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull();
    expect(await screen.findByTestId('elsewhere')).toBeDefined();
  });

  it('marks the current section and names the module', () => {
    signedIn();
    mockApi(DATA_ROUTES);
    renderApp(<DashHeader />, '/projects/options');
    expect(screen.getByRole('link', { name: 'New project' }).getAttribute('aria-current')).toBe('page');
    expect(screen.getByRole('link', { name: 'Overview' }).getAttribute('aria-current')).toBeNull();
    expect(moduleFor('/3d/abcdef012345')).toBe('2D to 3D');
    expect(moduleFor('/boq')).toBe('BOQ raw materials');
    expect(moduleFor('/home')).toBe('Overview');
  });

  it('makes initials from the name, or from the email when there is no name', () => {
    expect(initialsOf('Demo Architect')).toBe('DA');
    expect(initialsOf('Asha')).toBe('AS');
    expect(initialsOf('', 'kiran@studio.example')).toBe('KI');
  });
});

describe('dayLabel', () => {
  const now = new Date(2026, 10, 18, 15, 0);
  it('uses today, yesterday, then a short date', () => {
    expect(dayLabel(new Date(2026, 10, 18, 1, 0).toISOString(), now)).toBe('today');
    expect(dayLabel(new Date(2026, 10, 17, 23, 0).toISOString(), now)).toBe('yesterday');
    expect(dayLabel(new Date(2026, 10, 9, 12, 0).toISOString(), now)).toBe('9 nov');
    expect(dayLabel(new Date(2025, 11, 31, 12, 0).toISOString(), now)).toBe('31 dec 2025');
    expect(dayLabel('', now)).toBe('');
    expect(dayLabel('not a date', now)).toBe('');
  });
});
