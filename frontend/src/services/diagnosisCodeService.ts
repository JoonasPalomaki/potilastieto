import { config } from '../config';

const sanitizeBaseUrl = (baseUrl: string) => baseUrl.replace(/\/$/, '');

const apiBaseUrl = sanitizeBaseUrl(config.apiBaseUrl);

export interface DiagnosisCodeImportIssue {
  line?: number;
  code?: string;
  message: string;
}

export interface DiagnosisCodeImportSummary {
  imported: number;
  updated?: number;
  skipped?: number;
  auditId?: string;
  message?: string;
  issues?: DiagnosisCodeImportIssue[];
}

export interface DiagnosisCodeSearchResult {
  code: string;
  description?: string;
  status?: string;
}

export interface DiagnosisCodeSearchParams {
  query?: string;
  limit?: number;
  signal?: AbortSignal;
}

export interface DiagnosisCodeImportParams {
  file: File;
  authorization: string;
  signal?: AbortSignal;
}

export class DiagnosisCodeError extends Error {
  status: number;
  details?: unknown;
  issues?: DiagnosisCodeImportIssue[];

  constructor(message: string, status: number, details?: unknown, issues?: DiagnosisCodeImportIssue[]) {
    super(message);
    this.name = 'DiagnosisCodeError';
    this.status = status;
    this.details = details;
    this.issues = issues;
  }
}

const safeJson = async (response: Response): Promise<unknown> => {
  try {
    return await response.json();
  } catch (error) {
    return null;
  }
};

const coerceNumber = (value: unknown): number | undefined => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  return undefined;
};

const normalizeIssues = (payload: unknown): DiagnosisCodeImportIssue[] => {
  if (!Array.isArray(payload)) {
    return [];
  }

  return payload
    .map((entry) => {
      if (!entry || typeof entry !== 'object') {
        return null;
      }
      const issue = entry as {
        line?: unknown;
        code?: unknown;
        message?: unknown;
        detail?: unknown;
      };
      const message =
        typeof issue.message === 'string'
          ? issue.message
          : typeof issue.detail === 'string'
            ? issue.detail
            : null;
      if (!message) {
        return null;
      }
      return {
        line: typeof issue.line === 'number' ? issue.line : undefined,
        code: typeof issue.code === 'string' ? issue.code : undefined,
        message,
      } satisfies DiagnosisCodeImportIssue;
    })
    .filter((issue): issue is DiagnosisCodeImportIssue => Boolean(issue));
};

const normalizeSummary = (payload: unknown): DiagnosisCodeImportSummary => {
  if (!payload || typeof payload !== 'object') {
    return {
      imported: 0,
      message: 'Palvelin ei palauttanut yhteenvetoa tuonnista.',
    };
  }
  const summary = payload as {
    imported?: unknown;
    created?: unknown;
    updated?: unknown;
    skipped?: unknown;
    duplicates?: unknown;
    audit_id?: unknown;
    message?: unknown;
    errors?: unknown;
    issues?: unknown;
  };

  return {
    imported: coerceNumber(summary.imported ?? summary.created) ?? 0,
    updated: coerceNumber(summary.updated),
    skipped: coerceNumber(summary.skipped ?? summary.duplicates),
    auditId: typeof summary.audit_id === 'string' ? summary.audit_id : undefined,
    message: typeof summary.message === 'string' ? summary.message : undefined,
    issues: normalizeIssues(summary.errors ?? summary.issues),
  };
};

const importCodes = async ({ file, authorization, signal }: DiagnosisCodeImportParams): Promise<DiagnosisCodeImportSummary> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${apiBaseUrl}/v1/diagnosis-codes/import`, {
    method: 'POST',
    headers: {
      Authorization: authorization,
    },
    body: formData,
    signal,
  });

  const payload = await safeJson(response);

  if (!response.ok) {
    const message =
      typeof (payload as { message?: unknown; detail?: unknown } | null)?.message === 'string'
        ? ((payload as { message?: unknown }).message as string)
        : typeof (payload as { detail?: unknown } | null)?.detail === 'string'
          ? ((payload as { detail?: unknown }).detail as string)
          : 'Diagnoosikoodien tuonti epäonnistui.';
    const issues = normalizeIssues((payload as { errors?: unknown; issues?: unknown } | null)?.errors ?? (payload as { errors?: unknown; issues?: unknown } | null)?.issues);
    throw new DiagnosisCodeError(message, response.status, payload, issues);
  }

  return normalizeSummary(payload);
};

const searchCodes = async ({
  authorization,
  query,
  limit,
  signal,
}: DiagnosisCodeSearchParams & { authorization: string }): Promise<DiagnosisCodeSearchResult[]> => {
  const params = new URLSearchParams();
  if (query) {
    params.set('q', query);
  }
  if (typeof limit === 'number') {
    params.set('limit', String(limit));
  }

  const queryString = params.toString();
  const url = queryString
    ? `${apiBaseUrl}/v1/diagnosis-codes/search?${queryString}`
    : `${apiBaseUrl}/v1/diagnosis-codes/search`;

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
      Authorization: authorization,
    },
    signal,
  });

  const payload = await safeJson(response);

  if (!response.ok) {
    const message =
      typeof (payload as { message?: unknown } | null)?.message === 'string'
        ? ((payload as { message?: unknown }).message as string)
        : 'Diagnoosikoodien haku epäonnistui.';
    throw new DiagnosisCodeError(message, response.status, payload);
  }

  if (!Array.isArray(payload)) {
    return [];
  }

  return payload
    .map((entry) => {
      if (!entry || typeof entry !== 'object') {
        return null;
      }
      const codeEntry = entry as { code?: unknown; description?: unknown; status?: unknown };
      if (typeof codeEntry.code !== 'string') {
        return null;
      }
      return {
        code: codeEntry.code,
        description: typeof codeEntry.description === 'string' ? codeEntry.description : undefined,
        status: typeof codeEntry.status === 'string' ? codeEntry.status : undefined,
      } satisfies DiagnosisCodeSearchResult;
    })
    .filter((entry): entry is DiagnosisCodeSearchResult => Boolean(entry));
};

export interface DiagnosisCodeService {
  importCodes: (params: DiagnosisCodeImportParams) => Promise<DiagnosisCodeImportSummary>;
  searchCodes?: (params: DiagnosisCodeSearchParams & { authorization: string }) => Promise<DiagnosisCodeSearchResult[]>;
}

export const diagnosisCodeService: DiagnosisCodeService = {
  importCodes,
  searchCodes,
};
