/**
 * Floor plan API client (/api/v1/ai/floorplans). Every response is checked with zod.
 */
import { API_BASE_URL, ApiError, TOKEN_STORAGE_KEY, apiRequest } from '../../lib/api';
import {
  type Brief,
  type BriefFormValues,
  type EditResponse,
  type ExportFormat,
  type FloorplanSummary,
  type JobState,
  type ParseResponse,
  type PlanResponse,
  type PlanView,
  VIEW_FORMATS,
  editResponseSchema,
  floorplanSummarySchema,
  jobStateSchema,
  parseResponseSchema,
  planResponseSchema,
} from './schemas';

export const FLOORPLAN_BASE = '/api/v1/ai/floorplans';

export function authHeaders(): Headers {
  const headers = new Headers();
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return headers;
}

/** Drop empty optional values so the backend sees "not given" rather than 0 or "". */
function formBody(v: BriefFormValues): Record<string, unknown> {
  const body: Record<string, unknown> = {
    unit: v.unit,
    extras: v.extras,
    project_name: v.project_name.trim(),
    owner_name: v.owner_name.trim(),
    prompt: v.prompt.trim(),
  };
  for (const key of ['plot_width', 'plot_depth', 'bedrooms', 'bathrooms', 'road_side', 'pool_layout'] as const) {
    if (v[key] !== undefined) body[key] = v[key];
  }
  return body;
}

export const floorplanApi = {
  parseBrief: async (values: BriefFormValues): Promise<ParseResponse> =>
    parseResponseSchema.parse(
      await apiRequest(`${FLOORPLAN_BASE}/brief/parse`, {
        method: 'POST',
        body: JSON.stringify(formBody(values)),
      }),
    ),

  generate: async (brief: Brief, projectId?: string | null): Promise<string> => {
    const res = await apiRequest<{ job_id: string }>(`${FLOORPLAN_BASE}/generate`, {
      method: 'POST',
      body: JSON.stringify({ brief, project_id: projectId ?? null }),
    });
    return res.job_id;
  },

  job: async (jobId: string): Promise<JobState> =>
    jobStateSchema.parse(await apiRequest(`${FLOORPLAN_BASE}/jobs/${encodeURIComponent(jobId)}`)),

  plan: async (planId: string): Promise<PlanResponse> =>
    planResponseSchema.parse(await apiRequest(`${FLOORPLAN_BASE}/${encodeURIComponent(planId)}`)),

  edit: async (planId: string, message: string, version: number): Promise<EditResponse> =>
    editResponseSchema.parse(
      await apiRequest(`${FLOORPLAN_BASE}/${encodeURIComponent(planId)}/edit`, {
        method: 'POST',
        body: JSON.stringify({ message, version, allow_reflow: true }),
      }),
    ),

  /** The user's floor plans (newest first), optionally of one project. */
  /** The chat edit as a job (a full re-solve can take FLOORPLAN_FULL_RESOLVE_S). */
  editJob: async (planId: string, message: string, version: number): Promise<string> => {
    const res = await apiRequest<{ job_id: string }>(`${FLOORPLAN_BASE}/${encodeURIComponent(planId)}/edit-job`, {
      method: 'POST',
      body: JSON.stringify({ message, version }),
    });
    return res.job_id;
  },

  list: async (projectId?: string): Promise<FloorplanSummary[]> => {
    const q = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
    return floorplanSummarySchema.array().parse(await apiRequest(`${FLOORPLAN_BASE}${q}`));
  },

  /** Undo the last change, or go back to a given version. */
  revert: async (planId: string, version?: number): Promise<EditResponse> =>
    editResponseSchema.parse(
      await apiRequest(`${FLOORPLAN_BASE}/${encodeURIComponent(planId)}/revert`, {
        method: 'POST',
        body: JSON.stringify({ version: version ?? null }),
      }),
    ),

  /** The colour presentation plan as SVG text, for the plan view. */
  presentationSvg: async (planId: string): Promise<string> => {
    const url = `${API_BASE_URL}${FLOORPLAN_BASE}/${encodeURIComponent(planId)}/export?format=svg&view=presentation`;
    const res = await fetch(url, { headers: authHeaders() });
    if (!res.ok) throw new ApiError(res.status, `Could not load the presentation plan (${res.status})`);
    return res.text();
  },

  /** Download one export and hand it to the browser as a file. */
  download: async (planId: string, format: ExportFormat, dpi = 200, view: PlanView = 'engineering'): Promise<void> => {
    const asked = view === 'presentation' && VIEW_FORMATS.includes(format) ? '&view=presentation' : '';
    const url = `${API_BASE_URL}${FLOORPLAN_BASE}/${encodeURIComponent(planId)}/export?format=${format}&dpi=${dpi}${asked}`;
    const res = await fetch(url, { headers: authHeaders() });
    if (!res.ok) throw new ApiError(res.status, `Download failed (${res.status})`);
    const disposition = res.headers.get('content-disposition') ?? '';
    const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? `floor-plan.${format}`;
    const blobUrl = URL.createObjectURL(await res.blob());
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
  },
};
