const DEFAULT_API_BASE_URL = 'http://localhost:8000/api';

export const config = {
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? DEFAULT_API_BASE_URL,
} as const;

export type AppConfig = typeof config;
