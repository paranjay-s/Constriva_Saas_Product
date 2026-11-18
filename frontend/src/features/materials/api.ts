/**
 * Material Finder API client (/api/v1/ai/material-analysis). Every response is checked with zod.
 */
import { API_BASE_URL, ApiError, TOKEN_STORAGE_KEY, apiRequest, ensureFreshSession } from '../../lib/api';
import {
  type ChatReply,
  type ManualSpace,
  type Overrides,
  type Session,
  type SessionSummary,
  analysisCreatedSchema,
  chatReplySchema,
  sessionSchema,
  sessionSummarySchema,
} from './schemas';

export const MATERIAL_BASE = '/api/v1/ai/material-analysis';

export interface StartAnalysis {
  images: File[];
  focusAreas: string[];
  focus: string;
  space?: ManualSpace | null;
  projectId?: string | null;
  room?: string;
}

export const materialApi = {
  start: async (input: StartAnalysis): Promise<{ report_id: string; job_id: string }> => {
    const body = new FormData();
    input.images.forEach((f) => body.append('images', f));
    body.append('focus_areas', input.focusAreas.join(','));
    body.append('focus', input.focus.trim());
    if (input.space) body.append('space', JSON.stringify(input.space));
    if (input.projectId) body.append('project_id', input.projectId);
    if (input.room?.trim()) body.append('room', input.room.trim());
    return analysisCreatedSchema.parse(await apiRequest(MATERIAL_BASE, { method: 'POST', body }));
  },

  get: async (id: string): Promise<Session> =>
    sessionSchema.parse(await apiRequest(`${MATERIAL_BASE}/${encodeURIComponent(id)}`)),

  recalculate: async (id: string, space: ManualSpace | null, overrides: Overrides): Promise<Session> =>
    sessionSchema.parse(
      await apiRequest(`${MATERIAL_BASE}/${encodeURIComponent(id)}/recalculate`, {
        method: 'POST',
        body: JSON.stringify({ space, overrides }),
      }),
    ),

  chat: async (id: string, message: string, file?: File | null): Promise<ChatReply> => {
    const body = new FormData();
    body.append('message', message);
    if (file) body.append('file', file);
    return chatReplySchema.parse(
      await apiRequest(`${MATERIAL_BASE}/${encodeURIComponent(id)}/chat`, { method: 'POST', body }),
    );
  },

  /** History: the user's earlier analyses, newest first. */
  list: async (): Promise<SessionSummary[]> => sessionSummarySchema.array().parse(await apiRequest(MATERIAL_BASE)),

  remove: async (id: string): Promise<void> => {
    await apiRequest(`${MATERIAL_BASE}/${encodeURIComponent(id)}`, { method: 'DELETE' });
  },

  /** The analysed photo kept by the server, as an object URL (null if none was kept). */
  image: async (id: string): Promise<string | null> => {
    await ensureFreshSession();
    const token = localStorage.getItem(TOKEN_STORAGE_KEY);
    const res = await fetch(`${API_BASE_URL}${MATERIAL_BASE}/${encodeURIComponent(id)}/image`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (res.status === 404) return null;
    if (!res.ok) throw new ApiError(res.status, `Photo could not be loaded (${res.status})`);
    return URL.createObjectURL(await res.blob());
  },
};
