import { apiRequest } from '../../lib/api';

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

export const filesApi = {
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
};
