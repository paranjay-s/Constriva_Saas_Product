/**
 * Test data in the shape of the 3D gateway's answers (/api/v1/3d), and a fetch stand-in
 * that answers by method and path. Used by the tests only.
 */
import { vi } from 'vitest';

export const API = 'http://localhost:8000';
export const BASE = '/api/v1/3d';
export const JOB_ID = 'a1b2c3d4e5f6';
export const TOKEN = 'eyJqb2IiOiJhMWIyYzNkNGU1ZjYifQ.c2lnbmVk';
export const EMBED_BASE = `${BASE}/embed/${TOKEN}`;

export const HIGH_REASON =
  'The cinema video tour is not built by the 3D service yet: PlanTo3D renders it with a command-line tool that needs a camera route written by hand.';

export const RAW_QUALITIES = [
  {
    id: 'low',
    label: 'Low',
    description: 'Draft: the fastest build, to check the plan and walk through it.',
    available: true,
    reason: '',
  },
  { id: 'medium', label: 'Medium', description: 'High-quality light and textures for the walkthrough.', available: true, reason: '' },
  { id: 'high', label: 'High', description: 'Cinema video tour of the house.', available: false, reason: HIGH_REASON },
];

export const RAW_SYSTEM = {
  reachable: true,
  ready: true,
  checks: {
    blender: { ok: true, version: '4.2' },
    pdf_tools: { ok: true },
    viewer: { ok: true },
    materials: { ok: true, running: false, done: 0, total: 0, failed: [] },
  },
  detail: '',
  qualities: RAW_QUALITIES,
};

export function rawJob(overrides: Record<string, unknown> = {}) {
  return {
    job_id: JOB_ID,
    name: 'green-villa.pdf',
    project_id: null,
    source: 'upload',
    stage: 'detected',
    progress: 100,
    message: 'Plan detected - please review',
    floors: ['Ground floor', 'First floor'],
    scale_source: 'dimension_label',
    eta_left: null,
    queue_position: null,
    quality: null,
    build_seconds: null,
    created_at: '2026-11-18T10:00:00+00:00',
    ...overrides,
  };
}

/** The answer of POST /jobs/{id}/embed. */
export function rawEmbed(jobId: string = JOB_ID, base: string = EMBED_BASE) {
  return {
    base_url: base,
    expires_in: 3600,
    review_url: `${base}/web/edit.html?job=${jobId}&embed`,
    walkthrough_url: `${base}/web/view.html?job=${jobId}&embed`,
    furniture_url: `${base}/web/furniture.html?embed`,
    files_url: `${base}/jobs/${jobId}`,
  };
}

/** The answer of POST /embed: the furniture models page alone. */
export function rawFurnitureEmbed(base: string = EMBED_BASE) {
  return {
    base_url: base,
    expires_in: 3600,
    review_url: null,
    walkthrough_url: null,
    furniture_url: `${base}/web/furniture.html?embed`,
    files_url: null,
  };
}

export const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

export const noContent = () => new Response(null, { status: 204 });

export interface MockRequest {
  url: URL;
  init: RequestInit;
}

export type MockRoutes = Record<string, (request: MockRequest) => Response | Promise<Response>>;

/** Answer fetch() from `routes`, keyed "METHOD /path" (without the query); anything else is a 404. */
export function mockFetch(routes: MockRoutes) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input));
    const handler = routes[`${(init.method ?? 'GET').toUpperCase()} ${url.pathname}`];
    return handler ? handler({ url, init }) : json({ detail: 'Not found' }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

export type FetchMock = ReturnType<typeof mockFetch>;

/** Every request made to "METHOD /path", oldest first. */
export function callsTo(fetchMock: FetchMock, method: string, path: string): MockRequest[] {
  return fetchMock.mock.calls
    .map(([input, init]) => ({ url: new URL(String(input)), init: init ?? {} }))
    .filter(({ url, init }) => url.pathname === path && (init.method ?? 'GET').toUpperCase() === method);
}

export const authorizationOf = (request: MockRequest) => new Headers(request.init.headers).get('Authorization');
