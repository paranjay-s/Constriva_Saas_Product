import { ApiError, apiRequest } from '../../lib/api';
import { type SseMessage, authorizedFetch, readEventStream } from '../../lib/sse';
import type { PlanJSON } from '../../types';

export interface ProcessBlueprintResponse {
  task_id: string;
  project_id: string;
  status: string;
  stream_url: string;
  message: string;
}

export interface ParsingProgressEvent {
  task_id: string;
  status: 'running' | 'queued' | 'done' | 'failed';
  progress: number;
  step: string;
  result?: {
    plan_id?: string;
    project_id?: string;
    pdf_file_id?: string;
    preview_image_url?: string;
    plan_summary?: {
      walls_count: number;
      openings_count: number;
      rooms_count: number;
      columns_count: number;
    };
    /** Present when the job failed: the plan parser's typed error. */
    status?: string;
    error?: { code?: string; message?: string; details?: string[] };
  };
}

/** The limits the server holds every plan PDF to (PLAN_PARSER_MAX_PDF_MB / _PAGES). */
export interface UploadLimits {
  max_pdf_mb: number;
  max_pdf_pages: number;
}

/** Used until the server's own limits arrive, and if they cannot be fetched. */
export const DEFAULT_UPLOAD_LIMITS: UploadLimits = { max_pdf_mb: 20, max_pdf_pages: 10 };

/**
 * Why a picked file cannot be uploaded as a plan, or null when it can. This only saves a
 * pointless upload: the server makes the same checks, plus the page count, and decides.
 */
export function planFileProblem(
  file: { name: string; size: number; type?: string },
  limits: UploadLimits = DEFAULT_UPLOAD_LIMITS,
): string | null {
  const isPdf = file.name.toLowerCase().endsWith('.pdf');
  if (!isPdf) return 'Please upload the floor plan as a PDF file.';
  if (file.size === 0) return 'This PDF is empty. Please choose another file.';
  if (file.size > limits.max_pdf_mb * 1024 * 1024) {
    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    return `This PDF is ${sizeMb} MB. The largest file accepted is ${limits.max_pdf_mb} MB.`;
  }
  return null;
}

/** How many times the progress stream may drop before the page gives up on it. */
const MAX_STREAM_ERRORS = 3;
/** Wait before reconnecting, longer after each drop in a row. */
const RECONNECT_MS = 1000;

const pause = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener('abort', () => {
      clearTimeout(timer);
      resolve();
    });
  });

export const filesApi = {
  /**
   * Upload an architectural PDF blueprint to initiate background conversion into 3D PlanJSON.
   */
  uploadBlueprint: async (file: File, projectId?: string): Promise<ProcessBlueprintResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    if (projectId) {
      formData.append('project_id', projectId);
    }

    return apiRequest<ProcessBlueprintResponse>('/api/v1/parsing/process', {
      method: 'POST',
      body: formData,
    });
  },

  /**
   * The size and page limits for a plan PDF. Falls back to the defaults when the server
   * cannot be asked, so the upload screens always have something to show.
   */
  getUploadLimits: async (): Promise<UploadLimits> => {
    try {
      const limits = await apiRequest<Partial<UploadLimits>>('/api/v1/parsing/upload-limits', { method: 'GET' });
      const mb = Number(limits?.max_pdf_mb);
      const pages = Number(limits?.max_pdf_pages);
      if (mb > 0 && pages >= 1) return { max_pdf_mb: mb, max_pdf_pages: pages };
    } catch {
      // keep the defaults
    }
    return DEFAULT_UPLOAD_LIMITS;
  },

  /**
   * Follows a parsing job's progress over Server-Sent Events.
   *
   * The stream belongs to the user who started the job, so it is read with fetch() and
   * the session's token (EventSource cannot send one). If the connection drops it is
   * opened again; the server then sends the job's current state, so nothing is lost.
   * It gives up after MAX_STREAM_ERRORS drops in a row. Returns a function that stops it.
   */
  subscribeToProgress: (
    taskId: string,
    callbacks: {
      onProgress: (step: string, progress: number) => void;
      onComplete: (data: ParsingProgressEvent) => void;
      /** `code` is the parser's error code when the job itself failed (e.g. `llm_unavailable`). */
      onError: (errorMsg: string, code?: string) => void;
    }
  ): (() => void) => {
    const controller = new AbortController();
    const { signal } = controller;
    let finished = false;
    let drops = 0;

    const payloadOf = (message: SseMessage): ParsingProgressEvent | null => {
      try {
        return JSON.parse(message.data) as ParsingProgressEvent;
      } catch (err) {
        console.warn(`Error parsing SSE ${message.event} payload:`, err);
        return null;
      }
    };

    const onMessage = (message: SseMessage) => {
      if (finished || signal.aborted) return;
      if (message.event === 'progress') {
        drops = 0;
        const payload = payloadOf(message);
        if (payload) callbacks.onProgress(payload.step, payload.progress);
      } else if (message.event === 'complete') {
        finished = true;
        const payload = payloadOf(message);
        if (payload) callbacks.onComplete(payload);
        else callbacks.onError('The plan could not be processed.');
      } else if (message.event === 'failed') {
        finished = true;
        const payload = payloadOf(message);
        const error = payload?.result?.error;
        callbacks.onError(error?.message || payload?.step || 'The plan could not be processed.', error?.code);
      }
      // an `error` event means the server lost the job's updates and is closing the
      // stream: it counts as a drop below, and the stream is opened again
    };

    const follow = async () => {
      while (!finished && !signal.aborted) {
        try {
          await readEventStream(`/api/v1/parsing/stream/${encodeURIComponent(taskId)}`, { signal, onMessage });
        } catch (err) {
          if (signal.aborted || finished) return;
          if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
            finished = true;
            callbacks.onError('Your session has expired. Please sign in again.', 'not_signed_in');
            return;
          }
          if (err instanceof ApiError && err.status === 404) {
            finished = true;
            callbacks.onError('This import could not be found. Please upload the plan again.', 'job_not_found');
            return;
          }
          console.warn('SSE connection error:', err);
        }
        if (finished || signal.aborted) return;
        drops += 1;
        if (drops >= MAX_STREAM_ERRORS) {
          finished = true;
          callbacks.onError('Lost connection while the plan was being processed.', 'connection_lost');
          return;
        }
        await pause(RECONNECT_MS * drops, signal);
      }
    };

    void follow();
    return () => controller.abort();
  },

  /**
   * The page image of a parsing job, as an object URL for an <img>. It is fetched with
   * the session's token because the endpoint answers only the job's owner. Null when the
   * job has no image (yet). The caller revokes the URL when it is done with it.
   */
  getJobImage: async (taskId: string): Promise<string | null> => {
    try {
      const res = await authorizedFetch(`/api/v1/parsing/job/${encodeURIComponent(taskId)}/image`);
      return URL.createObjectURL(await res.blob());
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) return null;
      throw err;
    }
  },

  /**
   * The downloadable PNG drawing of a plan, fetched with the session's token (the endpoint
   * answers only the owner of the plan's project). Null when the plan has no drawing.
   */
  getPlanDrawing: async (planId: string): Promise<Blob | null> => {
    try {
      const res = await authorizedFetch(`/api/v1/plans/${encodeURIComponent(planId)}/download-png`);
      return await res.blob();
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) return null;
      throw err;
    }
  },

  /**
   * Retrieve the active PlanJSON for a given project.
   */
  getProjectPlan: async (projectId: string): Promise<{ plan_json: PlanJSON; id: string; name: string }> => {
    return apiRequest<{ plan_json: PlanJSON; id: string; name: string }>(
      `/api/v1/plans/project/${projectId}`,
      { method: 'GET' }
    );
  },

  /**
   * Retrieve a specific plan by its Plan ID.
   */
  getPlanById: async (planId: string): Promise<{ plan_json: PlanJSON; id: string; name: string }> => {
    return apiRequest<{ plan_json: PlanJSON; id: string; name: string }>(
      `/api/v1/plans/${planId}`,
      { method: 'GET' }
    );
  },
};
