import { describe, it, expect, vi, beforeEach } from 'vitest';
import { filesApi } from './api';

describe('filesApi and Blueprint Ingestion Module', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('uploads blueprint PDF to /api/v1/parsing/process and returns task_id', async () => {
    const mockResponse = {
      task_id: 'task-test-999',
      project_id: 'proj-test-111',
      status: 'queued',
      stream_url: '/api/v1/parsing/stream/task-test-999',
      message: 'Blueprint upload received.',
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockResponse,
    });

    const dummyFile = new File(['%PDF-1.4 dummy content'], 'floorplan_test.pdf', {
      type: 'application/pdf',
    });

    const res = await filesApi.uploadBlueprint(dummyFile, 'proj-test-111');
    expect(res.task_id).toBe('task-test-999');
    expect(res.project_id).toBe('proj-test-111');
    expect(res.status).toBe('queued');

    const callArgs = (globalThis.fetch as any).mock.calls[0];
    expect(callArgs[0]).toContain('/api/v1/parsing/process');
    expect(callArgs[1].method).toBe('POST');
  });

  it('fetches parsed PlanJSON by plan ID', async () => {
    const mockPlanPayload = {
      id: 'plan-xyz-123',
      name: 'Extracted Plan - floorplan_test.pdf',
      plan_json: {
        version: 1,
        units: 'm',
        levels: [
          {
            walls: [
              { id: 'w1', start: [0, 0], end: [11.12, 0], thickness: 0.23 },
              { id: 'w2', start: [0, 0], end: [0, 16.76], thickness: 0.23 },
            ],
            rooms: [
              { id: 'r1', name: 'VERANDAH', polygon: [[0, 0], [7, 0], [7, 1.3], [0, 1.3]] },
            ],
            openings: [],
          },
        ],
      },
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockPlanPayload,
    });

    const res = await filesApi.getPlanById('plan-xyz-123');
    expect(res.id).toBe('plan-xyz-123');
    expect(res.plan_json.levels?.[0]?.walls?.length).toBe(2);
    expect(res.plan_json.levels?.[0]?.rooms?.[0]?.name).toBe('VERANDAH');
  });

  it('retrieves active project PlanJSON from backend', async () => {
    const mockPlanPayload = {
      id: 'plan-proj-456',
      name: 'Active Project Plan',
      plan_json: {
        version: 1,
        units: 'm',
        levels: [{ walls: [], rooms: [], openings: [] }],
      },
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockPlanPayload,
    });

    const res = await filesApi.getProjectPlan('proj-test-111');
    expect(res.id).toBe('plan-proj-456');
    expect(res.plan_json.version).toBe(1);
  });
});

