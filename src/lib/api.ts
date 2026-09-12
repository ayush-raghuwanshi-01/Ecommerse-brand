/** Typed API client with refresh-token rotation + retry-once on 401. */

import type { User } from './types';

export const API = '/api/v1';

const ACCESS_KEY = 'bh_access';
const REFRESH_KEY = 'bh_refresh';

export class ApiError extends Error {
  code: string;
  status: number;
  details: Record<string, unknown>;
  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY);
  },
  set(access: string, refresh: string) {
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

async function raw(path: string, init: RequestInit = {}, auth = true): Promise<Response> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((init.headers as Record<string, string>) || {}),
  };
  if (auth && tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
  return fetch(`${API}${path}`, { ...init, headers });
}

async function tryRefresh(): Promise<boolean> {
  if (!tokens.refresh) return false;
  try {
    const res = await fetch(`${API}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: tokens.refresh }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    tokens.set(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

export async function request<T>(path: string, init: RequestInit = {}, auth = true): Promise<T> {
  let res = await raw(path, init, auth);
  if (res.status === 401 && auth && tokens.refresh) {
    if (await tryRefresh()) {
      res = await raw(path, init, auth);
    }
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error || {};
    throw new ApiError(res.status, err.code || 'ERROR', err.message || res.statusText, err.details || {});
  }
  return body as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown, headers?: Record<string, string>) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body), headers }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};

export async function login(email: string, password: string): Promise<User> {
  const data = await request<{ access_token: string; refresh_token: string }>(
    '/auth/login',
    { method: 'POST', body: JSON.stringify({ email, password }) },
    false,
  );
  tokens.set(data.access_token, data.refresh_token);
  return request<User>('/auth/me');
}

export async function register(payload: {
  email: string;
  password: string;
  full_name: string;
  phone?: string;
}): Promise<User> {
  const data = await request<{ access_token: string; refresh_token: string }>(
    '/auth/register',
    { method: 'POST', body: JSON.stringify(payload) },
    false,
  );
  tokens.set(data.access_token, data.refresh_token);
  return request<User>('/auth/me');
}

export async function logout() {
  try {
    if (tokens.refresh) await api.post('/auth/logout', { refresh_token: tokens.refresh });
  } catch {
    /* best effort */
  }
  tokens.clear();
}
