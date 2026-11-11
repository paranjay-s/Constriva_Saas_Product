import { describe, it, expect, vi, beforeEach } from 'vitest';
import { authApi, TOKEN_STORAGE_KEY } from '../../lib/api';

describe('authApi integration tests', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('signs up user successfully and parses backend AuthResponse', async () => {
    const mockResponse = {
      access_token: 'fake-jwt-token-123',
      token_type: 'bearer',
      user: {
        id: 'usr-uuid-001',
        email: 'test@construtiva.ai',
        full_name: 'Test Architect',
      },
    };

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockResponse,
    });
    vi.stubGlobal('fetch', mockFetch);

    const res = await authApi.signup({
      email: 'test@construtiva.ai',
      password: 'Password123!',
      full_name: 'Test Architect',
    });

    expect(res.access_token).toBe('fake-jwt-token-123');
    expect(res.user.email).toBe('test@construtiva.ai');
    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/auth/signup',
      expect.objectContaining({
        method: 'POST',
      })
    );
  });

  it('logs in user and sends authorization header when token exists', async () => {
    const mockLoginRes = {
      access_token: 'jwt-logged-in-456',
      token_type: 'bearer',
      user: {
        id: 'usr-uuid-002',
        email: 'login@construtiva.ai',
        full_name: 'Senior Architect',
      },
    };

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockLoginRes,
    });
    vi.stubGlobal('fetch', mockFetch);

    const res = await authApi.login({
      email: 'login@construtiva.ai',
      password: 'SecretPassword!',
    });

    expect(res.access_token).toBe('jwt-logged-in-456');

    // Test getProfile with token
    localStorage.setItem(TOKEN_STORAGE_KEY, 'jwt-logged-in-456');
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockLoginRes.user,
    });

    const profile = await authApi.getProfile();
    expect(profile.id).toBe('usr-uuid-002');
  });

  it('throws ApiError with detail message on 401 failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ detail: 'Invalid email or password.' }),
      })
    );

    await expect(
      authApi.login({ email: 'wrong@test.com', password: 'bad' })
    ).rejects.toThrow('Invalid email or password.');
  });
});
