import { API_BASE_URL, apiRequest } from '../../lib/api';
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
   * Subscribes to real-time Server-Sent Events (SSE) tracking geometric extraction progress.
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
    const sseUrl = `${API_BASE_URL}/api/v1/parsing/stream/${taskId}`;
    const eventSource = new EventSource(sseUrl);
    let streamErrors = 0;

    eventSource.addEventListener('progress', (e) => {
      streamErrors = 0;
      try {
        const payload: ParsingProgressEvent = JSON.parse(e.data);
        callbacks.onProgress(payload.step, payload.progress);
      } catch (err) {
        console.warn('Error parsing SSE progress payload:', err);
      }
    });

    eventSource.addEventListener('complete', (e) => {
      try {
        const payload: ParsingProgressEvent = JSON.parse(e.data);
        callbacks.onComplete(payload);
      } catch (err) {
        console.warn('Error parsing SSE complete payload:', err);
      }
      eventSource.close();
    });

    eventSource.addEventListener('failed', (e) => {
      try {
        const payload: ParsingProgressEvent = JSON.parse(e.data);
        const error = payload.result?.error;
        callbacks.onError(error?.message || payload.step || 'The plan could not be processed.', error?.code);
      } catch {
        callbacks.onError('The plan could not be processed.');
      }
      eventSource.close();
    });

    eventSource.onerror = (err) => {
      console.warn('SSE connection error:', err);
      // The browser reconnects by itself and the server then sends the job's current state,
      // so a short drop loses nothing. Give up only when it keeps failing.
      streamErrors += 1;
      if (streamErrors >= MAX_STREAM_ERRORS || eventSource.readyState === EventSource.CLOSED) {
        callbacks.onError('Lost connection while the plan was being processed.', 'connection_lost');
        eventSource.close();
      }
    };

    return () => {
      eventSource.close();
    };
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
