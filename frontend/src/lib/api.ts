/**
 * Construtiva Frontend Centralized API Client
 * Connects React frontend (port 5173) to FastAPI backend (port 8000)
 */

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const TOKEN_STORAGE_KEY = 'construtiva_auth_token';

/**
 * Custom API Error class containing backend error detail
 */
export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

// ------------------------------------------------------------------ session
//
// Supabase access tokens live 1 hour. The refresh token is stored with them and used to
// get a new access token shortly before expiry (and once more if the server still answers
// 401). If that fails, the session is cleared and SESSION_EXPIRED_EVENT tells the app to go
// to sign-in with a clear message, instead of every page failing with database errors.

export const REFRESH_STORAGE_KEY = 'construtiva_refresh_token';
export const EXPIRES_STORAGE_KEY = 'construtiva_token_expires_at';
export const SESSION_NOTICE_KEY = 'construtiva_session_notice';
export const SESSION_EXPIRED_EVENT = 'construtiva:session-expired';
const REFRESH_BEFORE_S = 120;

interface SessionTokens {
  access_token: string;
  refresh_token?: string | null;
  expires_at?: number | null;
}

/** Seconds since epoch when the access token expires (from the response or the JWT itself). */
function expiryOf(s: SessionTokens): number | null {
  if (s.expires_at) return s.expires_at;
  try {
    const payload = JSON.parse(atob(s.access_token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    return typeof payload.exp === 'number' ? payload.exp : null;
  } catch {
    return null;
  }
}

export function saveSession(s: SessionTokens): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, s.access_token);
  if (s.refresh_token) localStorage.setItem(REFRESH_STORAGE_KEY, s.refresh_token);
  const exp = expiryOf(s);
  if (exp) localStorage.setItem(EXPIRES_STORAGE_KEY, String(exp));
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(REFRESH_STORAGE_KEY);
  localStorage.removeItem(EXPIRES_STORAGE_KEY);
}

function endSession(message: string): void {
  clearSession();
  try {
    sessionStorage.setItem(SESSION_NOTICE_KEY, message);
  } catch {
    // storage blocked: the sign-in page simply shows no notice
  }
  window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT, { detail: message }));
}

let refreshing: Promise<boolean> | null = null;

/** Exchange the refresh token for a new session (one request at a time). */
export function refreshSession(): Promise<boolean> {
  const refreshToken = localStorage.getItem(REFRESH_STORAGE_KEY);
  if (!refreshToken) return Promise.resolve(false);
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!res.ok) return false;
        saveSession((await res.json()) as SessionTokens);
        return true;
      } catch {
        return false; // offline: keep the current session, the request decides
      } finally {
        refreshing = null;
      }
    })();
  }
  return refreshing;
}

/** Refresh shortly before the access token expires, so requests never carry an expired one. */
export async function ensureFreshSession(): Promise<void> {
  const exp = Number(localStorage.getItem(EXPIRES_STORAGE_KEY) || 0);
  if (!exp || !localStorage.getItem(REFRESH_STORAGE_KEY)) return;
  if (exp - Date.now() / 1000 < REFRESH_BEFORE_S) await refreshSession();
}

const isAuthEndpoint = (endpoint: string) => endpoint.includes('/api/v1/auth/');

/**
 * Standard HTTP fetch wrapper with authorization header injection
 */
export async function apiRequest<T = any>(
  endpoint: string,
  options: RequestInit = {},
  retried = false,
): Promise<T> {
  if (!isAuthEndpoint(endpoint)) await ensureFreshSession();
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401 && token && !isAuthEndpoint(endpoint) && !retried) {
    // the token was refused: try one refresh, then repeat the request once
    if (await refreshSession()) {
      const retryHeaders = new Headers(options.headers || {});
      return apiRequest<T>(endpoint, { ...options, headers: retryHeaders }, true);
    }
    endSession('Your session has expired. Please sign in again.');
    throw new ApiError(401, 'Your session has expired. Please sign in again.');
  }

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    try {
      const errorJson = await response.json();
      errorDetail = errorJson.detail || errorDetail;
    } catch {
      // If not JSON, use default error message
    }
    throw new ApiError(response.status, errorDetail);
  }

  // Handle empty responses (204 No Content)
  if (response.status === 204) {
    return {} as T;
  }

  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return (await response.json()) as T;
  }

  return (await response.text()) as unknown as T;
}

/**
 * Authentication API Service
 */
export interface AuthUser {
  id: string;
  email: string;
  full_name?: string;
  phone?: string | null;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
  refresh_token?: string | null;
  expires_at?: number | null;
}

export const authApi = {
  signup: async (payload: { email: string; password: string; full_name: string; phone?: string }): Promise<AuthResponse> => {
    return apiRequest<AuthResponse>('/api/v1/auth/signup', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  login: async (payload: { email: string; password: string }): Promise<AuthResponse> => {
    return apiRequest<AuthResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  getProfile: async (): Promise<AuthUser> => {
    return apiRequest<AuthUser>('/api/v1/auth/me', {
      method: 'GET',
    });
  },
};
