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
    expect(screen.getByText(/instant architect demo access/i)).toBeDefined();
  });

  it('renders Route 2: /home (Strictly 2 Primary Choices: Create Project & Analyse Materials)', () => {
    renderWithProviders(<HomePage />);
    expect(screen.getByText(/create new project/i)).toBeDefined();
    expect(screen.getByText(/analyse interior materials/i)).toBeDefined();
  });

  it('renders Route 3: /projects/new (Project Setup Information)', () => {
    renderWithProviders(<CreateProjectPage />);
    expect(screen.getByText(/create project/i)).toBeDefined();
    expect(screen.getByText(/project name \*/i)).toBeDefined();
    expect(screen.getByText(/residential/i)).toBeDefined();
  });

  it('renders Route 4: /projects/options (Strictly 2 Workflow Choices)', () => {
    renderWithProviders(<ProjectOptionsPage />);
    expect(screen.getByText(/how would you like to build your plan\?/i)).toBeDefined();
    expect(screen.getByText(/import existing 2d plan/i)).toBeDefined();
    expect(screen.getByText(/create your own 2d plan/i)).toBeDefined();
  });

  // Routes 5 and 6 (the import page and the in-browser 3D workspace) were replaced by
  // 2D to 3D at /3d: see "2D to 3D routes" below.

  it('renders Route 7: /projects/ai-generator (AI Floor Plan Generator)', () => {
    renderWithProviders(<AiGeneratorPage />);
    expect(screen.getByText(/ai floor plan generator/i)).toBeDefined();
    // a floor plan is always made inside a project: the page asks for one first
    expect(screen.getByText(/choose a project first/i)).toBeDefined();
    expect(screen.getByRole('button', { name: /create a new project/i })).toBeDefined();
  });

  it('keeps the old generator at /projects/ai-generator/legacy until it is retired', () => {
    renderWithProviders(<LegacyAiGeneratorPage />);
    expect(screen.getByText(/conversational cad/i)).toBeDefined();
  });

  it('renders Route 8: /materials/analyse (Material Finder)', () => {
    renderWithProviders(<MaterialFinderPage />);
    expect(screen.getByText(/material finder/i)).toBeDefined();
    expect(screen.getByText(/upload a photo of a room, kitchen or facade/i)).toBeDefined();
    expect(screen.getByRole('textbox', { name: 'Prompt' })).toBeDefined();
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
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    // the server as it answers an account without projects or plans
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = new URL(String(input)).pathname;
        const method = init?.method ?? 'GET';
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
