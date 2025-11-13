import { ApiError } from '../services/visitService';

type FastApiErrorDetail = {
  loc?: unknown;
  msg?: unknown;
  message?: unknown;
  detail?: unknown;
};

const extractMessageFromDetail = (detail: FastApiErrorDetail): string | null => {
  if (typeof detail.msg === 'string') {
    return detail.msg;
  }
  if (typeof detail.message === 'string') {
    return detail.message;
  }
  if (typeof detail.detail === 'string') {
    return detail.detail;
  }
  return null;
};

const formatFastApiErrorDetail = (detail: FastApiErrorDetail): string | null => {
  const message = extractMessageFromDetail(detail);
  if (!message) {
    return null;
  }

  if (Array.isArray(detail.loc)) {
    const location = detail.loc
      .filter((part) => part !== 'body')
      .map((part) => (typeof part === 'string' ? part : String(part)))
      .join('.');
    if (location) {
      return `${location}: ${message}`;
    }
  }

  return message;
};

export const resolveApiErrorMessage = (error: ApiError): string => {
  const body = error.body as { detail?: unknown } | null;
  if (body && typeof body.detail === 'string') {
    return body.detail;
  }

  if (body && Array.isArray(body.detail)) {
    const messages = body.detail
      .map((detail) => (typeof detail === 'object' && detail ? formatFastApiErrorDetail(detail) : null))
      .filter((detailMessage): detailMessage is string => Boolean(detailMessage));
    if (messages.length > 0) {
      return messages.join(' ');
    }
  }

  if (body && body.detail && typeof body.detail === 'object' && 'message' in body.detail) {
    const detail = body.detail as { message?: unknown };
    if (typeof detail.message === 'string') {
      return detail.message;
    }
  }

  return 'Toiminto epäonnistui. Yritä uudelleen myöhemmin.';
};
