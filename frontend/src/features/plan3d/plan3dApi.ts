/**
 * 3D gateway API client (/api/v1/3d). Every JSON response is checked with zod.
 *
 * Flow: upload(file) or sample() -> { job_id } -> job(id), asked again while it is worked on
 * -> the review page in an iframe (embed(id).review_url) -> build(id, quality) -> job(id)
 * until it is done -> the walkthrough in an iframe (embed(id).walkthrough_url).
 *
 * The pages in the iframes are served by the backend, which is another origin than this
 * app. Their URLs carry a signed token instead of the Authorization header (an iframe and
 * a download link cannot send one).
 */
import { z } from 'zod';
import { API_BASE_URL, ApiError, apiRequest } from '../../lib/api';
import {
  type Plan3dEmbed,
  type Plan3dJob,
  type Plan3dQualityId,
  type Plan3dSystem,
  plan3dEmbedSchema,
  plan3dExportSchema,
  plan3dJobCreatedSchema,
  plan3dJobListSchema,
  plan3dJobSchema,
  plan3dSystemSchema,
} from './plan3dSchemas';

export const PLAN3D_BASE = '/api/v1/3d';

/** A message a person can act on, whatever was thrown. */
export function plan3dErrorText(e: unknown): string {
  if (e instanceof ApiError) {
    // a 422 carries a list of issues instead of a sentence
    return typeof e.detail === 'string' && e.detail.trim() ? e.detail : `The request could not be completed (${e.status}).`;
  }
  if (e instanceof z.ZodError) return 'The server sent an answer this page could not read. Please try again.';
  if (e instanceof TypeError) return 'Could not reach the server. Check your connection and try again.';
  if (e instanceof Error && e.message) return e.message;
  return 'Something went wrong.';
}

/** True when the server says the job does not exist, or is not this person's. */
export function isNotFound(e: unknown): boolean {
  return e instanceof ApiError && e.status === 404;
}

/** The absolute URL of an embed path (`/api/v1/3d/embed/<token>/...`), for an iframe or a link. */
export function embedUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

/** The origin the embedded pages are served from, and post their messages from. */
export function embedOrigin(): string {
  return new URL(API_BASE_URL).origin;
}

/** The URL of one file of a job (e.g. the packed Blender file) under its `files_url`. */
export function jobFileUrl(filesUrl: string, file: string): string {
  return embedUrl(`${filesUrl}/${encodeURIComponent(file)}`);
}

/** Start a download by following a link; the server answers with an attachment. */
export function startDownload(url: string): void {
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', '');
  link.hidden = true;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

const jobPath = (jobId: string) => `${PLAN3D_BASE}/jobs/${encodeURIComponent(jobId)}`;

const withProject = (path: string, projectId?: string | null) =>
  projectId ? `${path}?project_id=${encodeURIComponent(projectId)}` : path;

export const plan3dApi = {
  /** Whether the 3D builder can take plans, and which qualities it can build. */
  system: async (signal?: AbortSignal): Promise<Plan3dSystem> =>
    plan3dSystemSchema.parse(await apiRequest(`${PLAN3D_BASE}/system`, { signal })),

  /** Upload a floor-plan PDF; detection starts at once. The answer is the job to follow. */
  upload: async (file: File, projectId?: string | null, signal?: AbortSignal): Promise<{ job_id: string }> => {
    const body = new FormData();
    body.append('file', file);
    if (projectId) body.append('project_id', projectId);
    return plan3dJobCreatedSchema.parse(await apiRequest(`${PLAN3D_BASE}/jobs`, { method: 'POST', body, signal }));
  },

  /** The same with the 3D builder's own sample plan. */
  sample: async (projectId?: string | null, signal?: AbortSignal): Promise<{ job_id: string }> =>
    plan3dJobCreatedSchema.parse(
      await apiRequest(withProject(`${PLAN3D_BASE}/jobs/sample`, projectId), { method: 'POST', signal }),
    ),

  /** The person's jobs, newest first; only one project's when `projectId` is given. */
  list: async (projectId?: string | null, signal?: AbortSignal): Promise<Plan3dJob[]> =>
    plan3dJobListSchema.parse(await apiRequest(withProject(`${PLAN3D_BASE}/jobs`, projectId), { signal })),

  job: async (jobId: string, signal?: AbortSignal): Promise<Plan3dJob> =>
    plan3dJobSchema.parse(await apiRequest(jobPath(jobId), { signal })),

  /** Build the 3D house from the plan as it was last saved. The answer is the job, now queued. */
  build: async (jobId: string, quality: Plan3dQualityId): Promise<Plan3dJob> =>
    plan3dJobSchema.parse(
      await apiRequest(`${jobPath(jobId)}/build`, { method: 'POST', body: JSON.stringify({ quality }) }),
    ),

  /** Pack the Blender file (up to a few minutes the first time). The answer is its file name. */
  exportBlender: async (jobId: string): Promise<{ file: string }> =>
    plan3dExportSchema.parse(await apiRequest(`${jobPath(jobId)}/export`, { method: 'POST' })),

  /** URLs of the job's review page, walkthrough and files, good for `expires_in` seconds. */
  embed: async (jobId: string, signal?: AbortSignal): Promise<Plan3dEmbed> =>
    plan3dEmbedSchema.parse(await apiRequest(`${jobPath(jobId)}/embed`, { method: 'POST', signal })),

  /** The URL of the furniture models page, which needs no job. */
  furnitureEmbed: async (signal?: AbortSignal): Promise<Plan3dEmbed> =>
    plan3dEmbedSchema.parse(await apiRequest(`${PLAN3D_BASE}/embed`, { method: 'POST', signal })),

  /** Delete a job and its files. Refused (409) while it is being built. */
  remove: async (jobId: string): Promise<void> => {
    await apiRequest(jobPath(jobId), { method: 'DELETE' });
  },
};
