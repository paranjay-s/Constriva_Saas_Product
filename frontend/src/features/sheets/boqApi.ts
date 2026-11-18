/**
 * BOQ raw-material API client (/api/v1/sheets/boq). Every JSON response is checked with zod.
 *
 * Flow: start(file) -> { job_id } -> follow the job with useJobEvents({ base: BOQ_BASE })
 * -> result(jobId) -> download('pdf' | 'xlsx', result).
 */
import { z } from 'zod';
import { API_BASE_URL, ApiError, TOKEN_STORAGE_KEY, apiRequest, ensureFreshSession } from '../../lib/api';
import { exportFileName, fileNameFromDisposition } from './boqLogic';
import { type BoqExportFormat, type BoqResult, boqJobCreatedSchema, boqResultSchema } from './boqSchemas';

export const BOQ_BASE = '/api/v1/sheets/boq';

export const EXPORT_LABELS: Record<BoqExportFormat, string> = { pdf: 'PDF', xlsx: 'Excel' };

const errorBodySchema = z.looseObject({ detail: z.string() });

/** A message a person can act on, whatever was thrown. */
export function boqErrorText(e: unknown): string {
  if (e instanceof ApiError) return e.detail;
  if (e instanceof z.ZodError) return 'The server sent a result this page could not read. Please try again.';
  if (e instanceof TypeError) return 'Could not reach the server. Check your connection and try again.';
  if (e instanceof Error && e.message) return e.message;
  return 'Something went wrong.';
}

/** The export request: the four parts of the result exactly as the server sent them, nothing else. */
export function boqExportBody(result: BoqResult): Pick<BoqResult, 'items' | 'warnings' | 'geometry_summary' | 'project_metadata'> {
  const { items, warnings, geometry_summary, project_metadata } = result;
  return { items, warnings, geometry_summary, project_metadata };
}

async function exportError(res: Response, format: BoqExportFormat): Promise<ApiError> {
  let detail = `The ${EXPORT_LABELS[format]} file could not be created (${res.status}).`;
  try {
    const body = errorBodySchema.safeParse(await res.json());
    if (body.success && body.data.detail) detail = body.data.detail;
  } catch {
    // not JSON: keep the default message
  }
  return new ApiError(res.status, detail);
}

function saveBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', fileName);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export const boqApi = {
  /** Upload the floor-plan PDF; the answer is the job to follow. */
  start: async (file: File, signal?: AbortSignal): Promise<{ job_id: string }> => {
    const body = new FormData();
    body.append('file', file);
    return boqJobCreatedSchema.parse(await apiRequest(BOQ_BASE, { method: 'POST', body, signal }));
  },

  /** The finished bill; only available once the job is done. */
  result: async (jobId: string): Promise<BoqResult> =>
    boqResultSchema.parse(await apiRequest(`${BOQ_BASE}/jobs/${encodeURIComponent(jobId)}/result`)),

  /**
   * Download the whole bill as a PDF or Excel file. The file name comes from the server;
   * without one it is BOQ_<source file base name>.pdf / .xlsx.
   */
  download: async (format: BoqExportFormat, result: BoqResult, sourceName?: string | null): Promise<void> => {
    await ensureFreshSession();
    const token = localStorage.getItem(TOKEN_STORAGE_KEY);
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(`${API_BASE_URL}${BOQ_BASE}/export/${format}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(boqExportBody(result)),
    });
    if (!res.ok) throw await exportError(res, format);
    const fileName =
      fileNameFromDisposition(res.headers.get('content-disposition')) ??
      exportFileName(format, result.project_metadata.source_file_name || sourceName);
    saveBlob(await res.blob(), fileName);
  },
};
