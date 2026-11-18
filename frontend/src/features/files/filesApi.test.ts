import { describe, it, expect, vi } from 'vitest';

describe('plan upload limits', () => {
  it('pre-checks a picked file against the limits', async () => {
    const { planFileProblem, DEFAULT_UPLOAD_LIMITS } = await import('./api');
    const mb = 1024 * 1024;
    expect(DEFAULT_UPLOAD_LIMITS).toEqual({ max_pdf_mb: 20, max_pdf_pages: 10 });
    expect(planFileProblem({ name: 'plan.pdf', size: 1024 })).toBeNull();
    expect(planFileProblem({ name: 'PLAN.PDF', size: 20 * mb })).toBeNull();
    expect(planFileProblem({ name: 'plan.png', size: 1024, type: 'image/png' })).toMatch(/as a PDF file/);
    expect(planFileProblem({ name: 'plan.pdf', size: 0 })).toMatch(/empty/i);
    expect(planFileProblem({ name: 'plan.pdf', size: 20 * mb + 1 })).toBe(
      'This PDF is 20.0 MB. The largest file accepted is 20 MB.',
    );
    // the server's own limit is used once it is known
    expect(planFileProblem({ name: 'plan.pdf', size: 6 * mb }, { max_pdf_mb: 5, max_pdf_pages: 3 })).toMatch(
      /largest file accepted is 5 MB/,
    );
    expect(planFileProblem({ name: 'plan.pdf', size: 30 * mb }, { max_pdf_mb: 50, max_pdf_pages: 10 })).toBeNull();
  });

  it('reads the limits from the server and falls back to the defaults', async () => {
    const { filesApi: api, DEFAULT_UPLOAD_LIMITS } = await import('./api');
    const fetchMock = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ max_pdf_mb: 8, max_pdf_pages: 4 }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);
    expect(await api.getUploadLimits()).toEqual({ max_pdf_mb: 8, max_pdf_pages: 4 });
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/v1/parsing/upload-limits');

    fetchMock.mockRejectedValueOnce(new TypeError('offline'));
    expect(await api.getUploadLimits()).toEqual(DEFAULT_UPLOAD_LIMITS);

    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ max_pdf_mb: 0 }), { status: 200, headers: { 'content-type': 'application/json' } }),
    );
    expect(await api.getUploadLimits()).toEqual(DEFAULT_UPLOAD_LIMITS);
    vi.unstubAllGlobals();
  });
});
