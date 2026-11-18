/**
 * Server-Sent Events read with fetch().
 *
 * Every stream of this API needs the signed-in user's token, and EventSource cannot send
 * an Authorization header. fetch() can, so streams are read from the response body here.
 */
import { API_BASE_URL, ApiError, TOKEN_STORAGE_KEY, ensureFreshSession, refreshSession } from './api';

export interface SseMessage {
  event: string;
  data: string;
}

/** Split an SSE text buffer into complete messages; returns them and the unfinished rest. */
export function parseSse(buffer: string): { messages: SseMessage[]; rest: string } {
  const messages: SseMessage[] = [];
  const blocks = buffer.replace(/\r\n/g, '\n').split('\n\n');
  const rest = blocks.pop() ?? '';
  for (const block of blocks) {
    let event = 'message';
    const data: string[] = [];
    for (const line of block.split('\n')) {
      if (line.startsWith(':')) continue; // keep-alive comment
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
    }
    if (data.length) messages.push({ event, data: data.join('\n') });
  }
  return { messages, rest };
}

/** The Authorization header of the current session; empty when nobody is signed in. */
export function authHeaders(): Headers {
  const headers = new Headers();
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return headers;
}

async function errorDetail(res: Response): Promise<string> {
  try {
    const body: unknown = await res.json();
    if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') return body.detail;
  } catch {
    // not JSON: use the default below
  }
  return `Request failed with status ${res.status}`;
}

/**
 * GET with the session's token. A refused token is refreshed once and the request
 * repeated, like `apiRequest` does. Throws ApiError for any response that is not ok.
 */
export async function authorizedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  await ensureFreshSession();
  const url = path.startsWith('http') ? path : `${API_BASE_URL}${path}`;
  const send = () => {
    const headers = authHeaders();
    new Headers(init.headers).forEach((value, key) => headers.set(key, value));
    return fetch(url, { ...init, headers });
  };
  let res = await send();
  if (res.status === 401 && localStorage.getItem(TOKEN_STORAGE_KEY) && (await refreshSession())) res = await send();
  if (!res.ok) throw new ApiError(res.status, await errorDetail(res));
  return res;
}

/**
 * Open an event stream and hand every message to `onMessage` until the server closes it.
 *
 * Resolves when the stream ends, rejects with ApiError when it cannot be opened (401 when
 * not signed in, 404 when the stream is not this user's) and with the network error when
 * the connection drops. Aborting `signal` stops it.
 */
export async function readEventStream(
  path: string,
  options: { signal?: AbortSignal; onMessage: (message: SseMessage) => void },
): Promise<void> {
  const res = await authorizedFetch(path, { headers: { Accept: 'text/event-stream' }, signal: options.signal });
  if (!res.body) throw new ApiError(res.status, 'The progress stream has no body.');
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSse(buffer);
    buffer = parsed.rest;
    parsed.messages.forEach(options.onMessage);
  }
}
