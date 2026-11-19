import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, RouterProvider, createMemoryRouter } from 'react-router-dom';
import { routes } from './app/router';
import { AuthProvider } from './context/AuthContext';
import { ProjectProvider } from './context/ProjectContext';
import { AuthPage } from './features/auth/AuthPage';
import { HomePage } from './features/home/HomePage';
import { CreateProjectPage } from './features/projects/CreateProjectPage';
import { ProjectOptionsPage } from './features/projects/ProjectOptionsPage';
import { AiGeneratorPage } from './features/chat/AiGeneratorPage';
import { LegacyAiGeneratorPage } from './features/chat/LegacyAiGeneratorPage';
import { MaterialFinderPage } from './features/materials';
import { LoanAnalysisPage } from './features/loan/LoanAnalysisPage';
import { TOKEN_STORAGE_KEY } from './lib/api';

// Helper to render within required providers
function renderWithProviders(ui: React.ReactElement, initialRoute = '/') {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <AuthProvider>
        <ProjectProvider>{ui}</ProjectProvider>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe('Constriva Frontend - 9 Core Required Pages', () => {
  it('renders Route 1: /auth (Authentication Page)', () => {
    renderWithProviders(<AuthPage />);
    expect(screen.getByText(/architectural intelligence platform/i)).toBeDefined();
    expect(screen.getByText(/sign in to workspace/i)).toBeDefined();
    // demo access is off unless VITE_ALLOW_DEMO_USER is set (the API refuses requests without a token)
    expect(screen.queryByText(/instant architect demo access/i)).toBeNull();
  });

  it('renders Route 2: /home (Project overview)', () => {
    renderWithProviders(<HomePage />);
    expect(screen.getByRole('heading', { name: 'Project overview' })).toBeDefined();
    expect(screen.getByRole('link', { name: /create new project/i })).toBeDefined();
    expect(screen.getByRole('link', { name: 'Floor plan chat' })).toBeDefined();
    expect(screen.getByRole('link', { name: 'Image analysis' })).toBeDefined();
  });

  it('renders Route 3: /projects/new (Project Setup Information)', () => {
    renderWithProviders(<CreateProjectPage />);
    expect(screen.getByText(/create project/i)).toBeDefined();
    expect(screen.getByText(/project name \*/i)).toBeDefined();
    expect(screen.getByText(/residential/i)).toBeDefined();
  });

  it('renders Route 4: /projects/options (Strictly 2 Workflow Choices)', () => {
    renderWithProviders(<ProjectOptionsPage />);
    expect(screen.getByRole('heading', { name: 'Choose a plan source' })).toBeDefined();
    expect(screen.getByText(/import existing 2d plan/i)).toBeDefined();
    expect(screen.getByText(/create your own 2d plan/i)).toBeDefined();
  });

  // Routes 5 and 6 (the import page and the in-browser 3D workspace) were replaced by
  // 2D to 3D at /3d: see "2D to 3D routes" below.

  it('renders Route 7: /projects/ai-generator (AI Floor Plan Generator)', () => {
    renderWithProviders(<AiGeneratorPage />);
    // chat studio: sidebar with history, composer in the middle, project picker
    expect(screen.getByRole('complementary', { name: 'Sidebar' })).toBeDefined();
    expect(screen.getByRole('textbox', { name: /describe the house/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /choose project/i })).toBeDefined();
  });

  it('keeps the old generator at /projects/ai-generator/legacy until it is retired', () => {
    renderWithProviders(<LegacyAiGeneratorPage />);
    expect(screen.getByText(/conversational cad/i)).toBeDefined();
  });

  it('renders Route 8: /materials/analyse (Material Finder)', () => {
    renderWithProviders(<MaterialFinderPage />);
    expect(screen.getByText(/material finder · the ai names the finishes/i)).toBeDefined();
    expect(screen.getByRole('textbox', { name: /ask about the photo/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /add photos/i })).toBeDefined();
    expect(screen.queryByText('What should I look at?')).toBeNull();
  });

  it('renders Route 9: /projects/loan-analysis (Bank Sanction vs Material BOQ)', () => {
    renderWithProviders(<LoanAnalysisPage />);
    expect(screen.getByText(/construction loan feasibility analysis/i)).toBeDefined();
    expect(screen.getByText(/sanctioned loan facility/i)).toBeDefined();
    expect(screen.getByText(/estimated material boq cost/i)).toBeDefined();
  });
});

/** The real route table, with the app's providers, opened at `path` as a signed-in visitor would. */
function openRoute(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <AuthProvider>
      <ProjectProvider>
        <RouterProvider router={router} />
      </ProjectProvider>
    </AuthProvider>,
  );
  return router;
}

describe('2D to 3D routes', () => {
  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem(TOKEN_STORAGE_KEY, 'test-token'); // a signed-in session (checked with /auth/me)
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    // the server as it answers an account without projects or plans
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = new URL(String(input)).pathname;
        const method = init?.method ?? 'GET';
        if (method === 'GET' && path === '/api/v1/auth/me') {
          return json({ id: '11111111-1111-1111-1111-111111111111', email: 'asha@studio.example', full_name: 'Asha Verma' });
        }
        if (method === 'GET' && path === '/api/v1/3d/system') {
          return json({ reachable: true, ready: true, checks: {}, detail: '', qualities: [] });
        }
        if (method === 'GET' && (path === '/api/v1/3d/jobs' || path === '/api/v1/projects')) return json([]);
        if (method === 'GET' && path === '/api/v1/parsing/upload-limits') return json({ max_pdf_mb: 20, max_pdf_pages: 10 });
        if (method === 'POST' && path === '/api/v1/3d/embed') {
          const base = '/api/v1/3d/embed/signed-token';
          return json({
            base_url: base,
            expires_in: 3600,
            review_url: null,
            walkthrough_url: null,
            furniture_url: `${base}/web/furniture.html?embed`,
            files_url: null,
          });
        }
        return json({ detail: '3D job not found.' }, 404);
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('serves the upload page at /3d, linked from the navigation as "2D to 3D"', async () => {
    const router = openRoute('/3d');
    expect(await screen.findByRole('heading', { name: '2D Plan to 3D' })).toBeDefined();
    expect(router.state.location.pathname).toBe('/3d');
    expect(screen.getByText(/drag and drop your floor plan pdf here/i)).toBeDefined();
    expect(screen.getByRole('button', { name: 'Upload plan' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Try the sample plan' })).toBeDefined();
    expect(await screen.findByText(/no plans yet/i)).toBeDefined();
    const link = screen.getByRole('link', { name: '2D to 3D' });
    expect(link.getAttribute('href')).toBe('/3d');
    expect(screen.queryByRole('link', { name: '3D Workspace' })).toBeNull();
  });

  it.each(['/projects/import', '/projects/3d-workspace'])('keeps the old address %s alive as a redirect to /3d', async (old) => {
    const router = openRoute(old);
    expect(await screen.findByRole('heading', { name: '2D Plan to 3D' })).toBeDefined();
    expect(router.state.location.pathname).toBe('/3d');
    // the old address is replaced, so Back does not bounce through it
    expect(router.state.historyAction).toBe('REPLACE');
  });

  it('serves the furniture models at /3d/furniture (not as a plan called "furniture")', async () => {
    const router = openRoute('/3d/furniture');
    expect(await screen.findByRole('heading', { name: 'Furniture models' })).toBeDefined();
    expect(await screen.findByTitle('Furniture models')).toBeDefined();
    expect(router.state.location.pathname).toBe('/3d/furniture');
  });

  it('shows the page of one plan at /3d/:jobId', async () => {
    const router = openRoute('/3d/a1b2c3d4e5f6');
    // the server above knows no such job: the plan's page says so
    expect(await screen.findByRole('heading', { name: 'This plan was not found' })).toBeDefined();
    expect(router.state.location.pathname).toBe('/3d/a1b2c3d4e5f6');
  });
});

describe('signed out', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.spyOn(console, 'warn').mockImplementation(() => {});
  });
  afterEach(() => vi.restoreAllMocks());

  it.each(['/home', '/projects/ai-generator', '/materials/analyse', '/boq', '/3d', '/3d/abcdef012345', '/projects/new'])(
    'sends a visit to %s to sign in',
    async (path) => {
      const router = openRoute(path);
      await screen.findByText(/sign in to workspace/i);
      expect(router.state.location.pathname).toBe('/auth');
    },
  );
});
