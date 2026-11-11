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
    plan_id: string;
    project_id: string;
    pdf_file_id?: string;
    preview_image_url?: string;
    plan_summary?: {
      walls_count: number;
      openings_count: number;
      rooms_count: number;
      columns_count: number;
    };
  };
}

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
   * Subscribes to real-time Server-Sent Events (SSE) tracking geometric extraction progress.
   */
  subscribeToProgress: (
    taskId: string,
    callbacks: {
      onProgress: (step: string, progress: number) => void;
      onComplete: (data: ParsingProgressEvent) => void;
      onError: (errorMsg: string) => void;
    }
  ): (() => void) => {
    const sseUrl = `${API_BASE_URL}/api/v1/parsing/stream/${taskId}`;
    const eventSource = new EventSource(sseUrl);

    eventSource.addEventListener('progress', (e) => {
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
        const payload = JSON.parse(e.data);
        callbacks.onError(payload.step || payload.result?.error || 'Blueprint parsing failed.');
      } catch {
        callbacks.onError('Blueprint parsing failed.');
      }
      eventSource.close();
    });

    eventSource.onerror = (err) => {
      console.warn('SSE connection error:', err);
      // Give a brief window for retry or report error
      callbacks.onError('Lost connection to plan processing stream.');
      eventSource.close();
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
