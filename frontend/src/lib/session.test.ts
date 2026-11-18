/**
 * Session renewal: the "errors one hour after signing in" incident must not happen again.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  ApiError,
  EXPIRES_STORAGE_KEY,
  REFRESH_STORAGE_KEY,
  SESSION_EXPIRED_EVENT,
  SESSION_NOTICE_KEY,
  TOKEN_STORAGE_KEY,
  apiRequest,
  saveSession,
} from './api';

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const now = () => Math.floor(Date.now() / 1000);

describe('session renewal', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it('stores the refresh token and expiry at sign-in', () => {
    saveSession({ access_token: 'a1', refresh_token: 'r1', expires_at: 123 });
    expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBe('a1');
    expect(localStorage.getItem(REFRESH_STORAGE_KEY)).toBe('r1');
    expect(localStorage.getItem(EXPIRES_STORAGE_KEY)).toBe('123');
  });

  it('refreshes before the token expires, then sends the new token', async () => {
    saveSession({ access_token: 'old', refresh_token: 'r1', expires_at: now() + 30 });
    fetchMock
      .mockResolvedValueOnce(json(200, { access_token: 'new', refresh_token: 'r2', expires_at: now() + 3600 }))
      .mockResolvedValueOnce(json(200, [{ id: 'p1' }]));
    await apiRequest('/api/v1/projects');
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v1/auth/refresh');
    const sent = fetchMock.mock.calls[1][1].headers as Headers;
    expect(sent.get('Authorization')).toBe('Bearer new');
    expect(localStorage.getItem(REFRESH_STORAGE_KEY)).toBe('r2');
  });

  it('does not refresh a token that is still fresh', async () => {
    saveSession({ access_token: 'ok', refresh_token: 'r1', expires_at: now() + 3000 });
    fetchMock.mockResolvedValueOnce(json(200, []));
    await apiRequest('/api/v1/projects');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('on a 401 it refreshes once and repeats the request', async () => {
    saveSession({ access_token: 'stale', refresh_token: 'r1', expires_at: now() + 3000 });
    fetchMock
      .mockResolvedValueOnce(json(401, { detail: 'Your session has expired. Please sign in again.' }))
      .mockResolvedValueOnce(json(200, { access_token: 'new', refresh_token: 'r2', expires_at: now() + 3600 }))
      .mockResolvedValueOnce(json(201, { id: 'p1' }));
    const res = await apiRequest<{ id: string }>('/api/v1/projects', { method: 'POST', body: '{}' });
    expect(res.id).toBe('p1');
    expect((fetchMock.mock.calls[2][1].headers as Headers).get('Authorization')).toBe('Bearer new');
  });

  it('when renewal fails it signs out cleanly with a clear notice', async () => {
    saveSession({ access_token: 'stale', refresh_token: 'dead', expires_at: now() + 3000 });
    const expired = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    fetchMock.mockResolvedValueOnce(json(401, { detail: 'expired' })).mockResolvedValueOnce(json(401, { detail: 'no' }));
    await expect(apiRequest('/api/v1/projects')).rejects.toBeInstanceOf(ApiError);
    expect(expired).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull();
    expect(sessionStorage.getItem(SESSION_NOTICE_KEY)).toMatch(/session has expired/);
    window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
  });
});
