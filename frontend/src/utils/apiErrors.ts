import { ApiError } from '../services/visitService';

export const resolveApiErrorMessage = (error: ApiError): string => {
  const body = error.body as { detail?: unknown } | null;
  if (body && typeof body.detail === 'string') {
    return body.detail;
  }
  if (body && body.detail && typeof body.detail === 'object' && 'message' in body.detail) {
    const detail = body.detail as { message?: unknown };
    if (typeof detail.message === 'string') {
      return detail.message;
    }
  }
  return 'Toiminto epäonnistui. Yritä uudelleen myöhemmin.';
};
