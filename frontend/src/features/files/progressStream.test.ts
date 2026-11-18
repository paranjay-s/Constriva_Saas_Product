/**
 * The 2D-to-3D progress stream and the protected images are read with fetch() and the
 * session's token: the server answers them only for the signed-in owner, and neither
 * EventSource nor an <img> tag can send an Authorization header.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { API_BASE_URL, TOKEN_STORAGE_KEY } from '../../lib/api';
import { parseSse, readEventStream } from '../../lib/sse';
import { filesApi } from './api';

const TASK = '11111111-1111-4111-8111-111111111111';
const STREAM_URL = `${API_BASE_URL}/api/v1/parsing/stream/${TASK}`;

function sse(...events: [name: string, data: unknown][]): Response {
  const text = events.map(([name, data]) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`).join('');
  return new Response(text, { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const event = (status: string, progress: number, step: string, result?: unknown) => ({
  task_id: TASK,
  status,
  progress,
  step,
  result,
});

function follow() {
  const seen = {
    progress: [] as [string, number][],
    complete: [] as unknown[],
    errors: [] as [string, string | undefined][],
  };
  const stop = filesApi.subscribeToProgress(TASK, {
    onProgress: (step, progress) => seen.progress.push([step, progress]),
    onComplete: (data) => seen.complete.push(data),
    onError: (message, code) => seen.errors.push([message, code]),
  });
  return { seen, stop };
}

describe('parsing progress stream', () => {
  let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>;

  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem(TOKEN_STORAGE_KEY, 'test-jwt-token');
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
    vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('sends the session token and never uses EventSource', async () => {
    const eventSource = vi.fn();
    vi.stubGlobal('EventSource', eventSource);
    fetchMock.mockResolvedValue(sse(['complete', event('done', 100, 'Finished', { plan_id: 'p1' })]));
    const { seen } = follow();
    await vi.waitFor(() => expect(seen.complete).toHaveLength(1));

    expect(eventSource).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(STREAM_URL);
    const headers = new Headers(init?.headers);
    expect(headers.get('Authorization')).toBe('Bearer test-jwt-token');
    expect(headers.get('Accept')).toBe('text/event-stream');
  });

  it('reports progress, then the finished job, and stops', async () => {
    fetchMock.mockResolvedValue(
      sse(
        ['progress', event('running', 15, 'Reading the plan')],
        ['progress', event('running', 65, 'Building the model')],
        ['complete', event('done', 100, 'Finished', { plan_id: 'p1', project_id: 'pr1' })],
      ),
    );
    const { seen } = follow();
    await vi.waitFor(() => expect(seen.complete).toHaveLength(1));
    expect(seen.progress).toEqual([
      ['Reading the plan', 15],
      ['Building the model', 65],
    ]);
    expect(seen.complete[0]).toMatchObject({ status: 'done', result: { plan_id: 'p1' } });
    expect(seen.errors).toEqual([]);
    expect(fetchMock).toHaveBeenCalledTimes(1); // a finished job is not followed again
  });

  it("passes on the parser's own error when the job fails", async () => {
    const failure = { status: 'failed', error: { code: 'llm_rate_limited', message: 'Too many requests right now.' } };
    fetchMock.mockResolvedValue(sse(['failed', event('failed', 40, 'Parsing failed', failure)]));
    const { seen } = follow();
    await vi.waitFor(() => expect(seen.errors).toHaveLength(1));
    expect(seen.errors[0]).toEqual(['Too many requests right now.', 'llm_rate_limited']);
    expect(seen.complete).toEqual([]);
  });

  it('opens the stream again after a drop and loses nothing', async () => {
    vi.useFakeTimers();
    fetchMock
      .mockResolvedValueOnce(sse(['progress', event('running', 15, 'Reading the plan')])) // ends early
      .mockRejectedValueOnce(new TypeError('network down'))
      .mockResolvedValueOnce(sse(['complete', event('done', 100, 'Finished', { plan_id: 'p1' })]));
    const { seen } = follow();
    await vi.advanceTimersByTimeAsync(5000);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(seen.progress).toEqual([['Reading the plan', 15]]);
    expect(seen.complete).toHaveLength(1);
    expect(seen.errors).toEqual([]);
  });

  it('gives up after three drops in a row', async () => {
    vi.useFakeTimers();
    fetchMock.mockRejectedValue(new TypeError('network down'));
    const { seen } = follow();
    await vi.advanceTimersByTimeAsync(10000);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(seen.errors).toEqual([['Lost connection while the plan was being processed.', 'connection_lost']]);
  });

  it('treats a server "error" event as a drop, not as the end', async () => {
    vi.useFakeTimers();
    fetchMock
      .mockResolvedValueOnce(sse(['error', { error: 'Lost connection to job updates' }]))
      .mockResolvedValueOnce(sse(['complete', event('done', 100, 'Finished', { plan_id: 'p1' })]));
    const { seen } = follow();
    await vi.advanceTimersByTimeAsync(3000);
    expect(seen.complete).toHaveLength(1);
    expect(seen.errors).toEqual([]);
  });

  it('says so when the job is not this user\'s, without retrying', async () => {
    fetchMock.mockResolvedValue(json(404, { detail: 'Parsing job not found.' }));
    const { seen } = follow();
    await vi.waitFor(() => expect(seen.errors).toHaveLength(1));
    expect(seen.errors[0][1]).toBe('job_not_found');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('asks the person to sign in again when the token is refused', async () => {
    fetchMock.mockResolvedValue(json(401, { detail: 'You are not signed in. Please sign in and try again.' }));
    const { seen } = follow();
    await vi.waitFor(() => expect(seen.errors).toHaveLength(1));
    expect(seen.errors[0]).toEqual(['Your session has expired. Please sign in again.', 'not_signed_in']);
    // no refresh token is stored, so the stream request is the only call
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('stops following when the page lets go', async () => {
    vi.useFakeTimers();
    fetchMock.mockImplementation(
      (_url, init) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
        }),
    );
    const { seen, stop } = follow();
    await vi.advanceTimersByTimeAsync(10);
    stop();
    await vi.advanceTimersByTimeAsync(10000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(seen.errors).toEqual([]);
  });
});

describe('protected images', () => {
  let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>;

  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem(TOKEN_STORAGE_KEY, 'test-jwt-token');
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:preview') }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  const png = () => new Response(new Uint8Array([137, 80, 78, 71]), { status: 200, headers: { 'Content-Type': 'image/png' } });

  it('fetches the job image with the token and returns an object URL', async () => {
    fetchMock.mockResolvedValue(png());
    await expect(filesApi.getJobImage(TASK)).resolves.toBe('blob:preview');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API_BASE_URL}/api/v1/parsing/job/${TASK}/image`);
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer test-jwt-token');
  });

  it('fetches the plan drawing with the token', async () => {
    fetchMock.mockResolvedValue(png());
    const drawing = await filesApi.getPlanDrawing('plan-1');
    expect(drawing?.size).toBe(4);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API_BASE_URL}/api/v1/plans/plan-1/download-png`);
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer test-jwt-token');
  });

  it('returns null for an image that is missing or belongs to someone else', async () => {
    fetchMock.mockImplementation(async () => json(404, { detail: 'Parsing job not found.' }));
    await expect(filesApi.getJobImage(TASK)).resolves.toBeNull();
    await expect(filesApi.getPlanDrawing('plan-1')).resolves.toBeNull();
  });

  it('does not hide other failures', async () => {
    fetchMock.mockImplementation(async () => json(401, { detail: 'You are not signed in.' }));
    await expect(filesApi.getJobImage(TASK)).rejects.toMatchObject({ status: 401 });
  });
});

describe('readEventStream', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('joins messages that arrive split across chunks', async () => {
    const encoder = new TextEncoder();
    const chunks = ['event: progress\ndata: {"a"', ':1}\n\nevent: prog', 'ress\ndata: {"a":2}\n\n'];
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
        controller.close();
      },
    });
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(new Response(body, { status: 200 })));
    const seen: string[] = [];
    await readEventStream('/api/v1/parsing/stream/x', { onMessage: (m) => seen.push(`${m.event}:${m.data}`) });
    expect(seen).toEqual(['progress:{"a":1}', 'progress:{"a":2}']);
  });

  it('parses comments, named events and multi-line data', () => {
    const { messages, rest } = parseSse(': keep-alive\n\nevent: complete\ndata: line1\ndata: line2\n\ndata: tail');
    expect(messages).toEqual([{ event: 'complete', data: 'line1\nline2' }]);
    expect(rest).toBe('data: tail');
  });
});
