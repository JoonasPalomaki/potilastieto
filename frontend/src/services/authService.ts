import { config } from '../config';

const STORAGE_KEY = 'potilastieto.auth';

const sanitizeBaseUrl = (baseUrl: string) => baseUrl.replace(/\/$/, '');

export class AuthError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'AuthError';
    this.status = status;
  }
}

export interface AuthSession {
  accessToken: string;
  refreshToken?: string;
  tokenType: string;
  expiresAt: number;
  username?: string;
  role?: string;
}

interface LoginResponse {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
  expires_in?: number;
  expires_at?: string;
  role?: string | null;
  user?: { username?: string; role?: string | null } | null;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

const parseExpiry = (payload: LoginResponse): number => {
  if (payload.expires_at) {
    const parsed = Date.parse(payload.expires_at);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }

  if (typeof payload.expires_in === 'number') {
    return Date.now() + payload.expires_in * 1000;
  }

  throw new Error('Token expiry missing from authentication response.');
};

const isExpired = (expiresAt: number) => Date.now() >= expiresAt - 5000; // Refresh 5 seconds before actual expiry.

const persistSession = (session: AuthSession) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
};

const loadSession = (): AuthSession | null => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw) as AuthSession;
    if (!parsed.accessToken || !parsed.tokenType || typeof parsed.expiresAt !== 'number') {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }

    if (isExpired(parsed.expiresAt)) {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }

    return parsed;
  } catch (error) {
    console.error('Failed to read authentication session from storage', error);
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
};

const clearSession = () => localStorage.removeItem(STORAGE_KEY);

const apiBaseUrl = sanitizeBaseUrl(config.apiBaseUrl);

export const authService = {
  getSession: (): AuthSession | null => loadSession(),

  isExpired,

  async login(credentials: LoginCredentials): Promise<AuthSession> {
    const response = await fetch(`${apiBaseUrl}/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(credentials),
    });

    if (response.status === 401) {
      throw new AuthError('Unauthorized', 401);
    }

    if (!response.ok) {
      throw new Error(`Login failed with status ${response.status}`);
    }

    const payload = (await response.json()) as LoginResponse;

    if (!payload.access_token) {
      throw new Error('Login response missing access token.');
    }

    const resolvedRole = payload.role ?? payload.user?.role ?? null;

    const session: AuthSession = {
      accessToken: payload.access_token,
      refreshToken: payload.refresh_token,
      tokenType: payload.token_type ?? 'Bearer',
      expiresAt: parseExpiry(payload),
      username: payload.user?.username ?? credentials.username,
      role: resolvedRole ?? undefined,
    };

    persistSession(session);

    return session;
  },

  logout(): void {
    clearSession();
  },

  saveSession(session: AuthSession): void {
    persistSession(session);
  },
};
