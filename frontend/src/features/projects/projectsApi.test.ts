import { describe, it, expect, vi, beforeEach } from 'vitest';
import { projectsApi, mapBackendProject, type BackendProject } from './api';
import { TOKEN_STORAGE_KEY } from '../../lib/api';

describe('projectsApi Service & Mapping', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem(TOKEN_STORAGE_KEY, 'test-jwt-token');
    vi.restoreAllMocks();
  });

  it('maps backend snake_case response with [Commercial] tag to frontend Project', () => {
    const raw: BackendProject = {
      id: 'proj_123',
      user_id: 'user_456',
      name: 'Skyline Business Tower',
      description: '[Commercial] High-rise office building with glass facade',
      status: 'active',
      created_at: '2026-11-10T12:00:00Z',
      updated_at: '2026-11-10T12:00:00Z',
    };

    const mapped = mapBackendProject(raw);
    expect(mapped.id).toBe('proj_123');
    expect(mapped.name).toBe('Skyline Business Tower');
    expect(mapped.type).toBe('Commercial');
    expect(mapped.description).toBe('High-rise office building with glass facade');
    expect(mapped.status).toBe('ready');
  });

  it('calls POST /api/v1/projects on create with auth header', async () => {
    const mockCreatedBackend: BackendProject = {
      id: 'proj_new_999',
      user_id: 'user_456',
      name: 'Pavilion Villa',
      description: '[Residential] 3BHK luxury residence',
      status: 'active',
      created_at: '2026-11-11T10:00:00Z',
      updated_at: '2026-11-11T10:00:00Z',
    };

    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockCreatedBackend,
    });

    vi.stubGlobal('fetch', fetchSpy);

    const project = await projectsApi.create('Pavilion Villa', 'Residential', '3BHK luxury residence');

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/projects',
      expect.objectContaining({
        method: 'POST',
        headers: expect.any(Headers),
      })
    );

    const sentHeaders = fetchSpy.mock.calls[0][1].headers as Headers;
    expect(sentHeaders.get('Authorization')).toBe('Bearer test-jwt-token');
    expect(project.id).toBe('proj_new_999');
    expect(project.name).toBe('Pavilion Villa');
    expect(project.type).toBe('Residential');
  });

  it('calls GET /api/v1/projects to list all projects', async () => {
    const mockList: BackendProject[] = [
      {
        id: 'proj_1',
        name: 'Project 1',
        description: '[Residential] Desc 1',
        status: 'active',
        created_at: '2026-11-11T09:00:00Z',
      },
      {
        id: 'proj_2',
        name: 'Project 2',
        description: '[Interior] Studio Renovation',
        status: 'active',
        created_at: '2026-11-11T08:00:00Z',
      },
    ];

    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockList,
    });

    vi.stubGlobal('fetch', fetchSpy);

    const list = await projectsApi.list();
    expect(list).toHaveLength(2);
    expect(list[0].id).toBe('proj_1');
    expect(list[1].type).toBe('Interior');
  });

  it('calls DELETE /api/v1/projects/{id}', async () => {
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ deleted: true, project_id: 'proj_123' }),
    });

    vi.stubGlobal('fetch', fetchSpy);

    const result = await projectsApi.delete('proj_123');
    expect(result.deleted).toBe(true);
    expect(result.project_id).toBe('proj_123');
  });
});
