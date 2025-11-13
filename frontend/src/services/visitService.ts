import { config } from '../config';

const sanitizeBaseUrl = (baseUrl: string) => baseUrl.replace(/\/$/, '');

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

export interface RequestOptions {
  authorization: string;
  signal?: AbortSignal;
}

export interface VisitBasicsPanel {
  visit_type?: string | null;
  location?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  attending_provider_id?: number | null;
  updated_at?: string | null;
}

export interface VisitReasonPanel {
  reason?: string | null;
  updated_at?: string | null;
}

export interface VisitNarrativePanel {
  content?: string | null;
  author_id?: number | null;
  updated_at?: string | null;
}

export interface VisitDiagnosisEntry {
  code: string;
  description?: string | null;
  is_primary?: boolean;
}

export interface VisitDiagnosesPanel {
  diagnoses: VisitDiagnosisEntry[];
  author_id?: number | null;
  updated_at?: string | null;
}

export interface VisitOrderItemRead {
  id: number;
  order_type: string;
  status?: string | null;
  details: Record<string, unknown>;
  placed_at?: string | null;
  ordered_by_id?: number | null;
  created_at: string;
  updated_at: string;
}

export interface VisitOrdersPanel {
  orders: VisitOrderItemRead[];
}

export interface InitialVisit {
  id: number;
  patient_id: number | null;
  appointment_id?: number | null;
  basics: VisitBasicsPanel;
  reason: VisitReasonPanel;
  anamnesis: VisitNarrativePanel;
  status: VisitNarrativePanel;
  diagnoses: VisitDiagnosesPanel;
  orders: VisitOrdersPanel;
  summary: VisitNarrativePanel;
  created_at: string;
  updated_at: string;
}

export interface AppointmentDetail {
  id: number;
  patient_id: number | null;
  provider_id: number;
  service_type?: string | null;
  location?: string | null;
  start_time: string;
  end_time: string;
  notes?: string | null;
  status: string;
}

export interface PatientDetail {
  id: number;
  identifier?: string | null;
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  sex?: string | null;
  contact_info?: Record<string, unknown> | null;
}

export interface VisitBasicsUpdate {
  visit_type?: string | null;
  location?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  attending_provider_id?: number | null;
}

export interface VisitReasonUpdate {
  reason: string;
}

export interface VisitNarrativeUpdate {
  content: string;
}

export interface VisitDiagnosesUpdate {
  diagnoses: VisitDiagnosisEntry[];
}

export interface VisitOrdersUpdateItem {
  order_type: string;
  status?: string | null;
  details?: Record<string, unknown>;
  placed_at?: string | null;
  ordered_by_id?: number | null;
}

export interface VisitOrdersUpdate {
  orders: VisitOrdersUpdateItem[];
}

export interface InitialVisitCreateRequest {
  appointment_id?: number | null;
  patient_id?: number | null;
  basics?: VisitBasicsUpdate;
  reason?: VisitReasonUpdate;
  anamnesis?: VisitNarrativeUpdate;
  status?: VisitNarrativeUpdate;
  diagnoses?: VisitDiagnosesUpdate;
  orders?: VisitOrdersUpdate;
  summary?: VisitNarrativeUpdate;
}

export interface PatientCreateRequest {
  identifier: string;
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  sex?: string | null;
  contact_info?: Record<string, unknown> | null;
}

const defaultHeaders = (authorization: string): HeadersInit => ({
  Accept: 'application/json',
  Authorization: authorization,
});

const parseBody = async (response: Response) => {
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    return response.json();
  }
  return null;
};

const createVisitService = (baseUrl: string) => {
  const apiBaseUrl = sanitizeBaseUrl(baseUrl);

  const request = async <T>(path: string, init: RequestInit, options: RequestOptions): Promise<T> => {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers: {
        ...defaultHeaders(options.authorization),
        ...(init.headers ?? {}),
      },
      signal: options.signal,
    });

    if (!response.ok) {
      const errorBody = await parseBody(response);
      throw new ApiError(
        `API request to ${path} failed with status ${response.status}`,
        response.status,
        errorBody,
      );
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const body = await parseBody(response);
    return body as T;
  };

  const getInitialVisit = (visitId: number, options: RequestOptions) =>
    request<InitialVisit>(`/v1/visits/${visitId}`, { method: 'GET' }, options);

  const createInitialVisit = (payload: InitialVisitCreateRequest, options: RequestOptions) =>
    request<InitialVisit>(
      `/v1/visits`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
      options,
    );

  const getAppointment = (appointmentId: number, options: RequestOptions) =>
    request<AppointmentDetail>(`/v1/appointments/${appointmentId}`, { method: 'GET' }, options);

  const getPatient = (patientId: number, options: RequestOptions) =>
    request<PatientDetail>(`/v1/patients/${patientId}`, { method: 'GET' }, options);

  const createPatient = (payload: PatientCreateRequest, options: RequestOptions) =>
    request<PatientDetail>(
      `/v1/patients`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
      options,
    );

  return {
    getInitialVisit,
    createInitialVisit,
    getAppointment,
    getPatient,
    createPatient,
  };
};

export const visitService = createVisitService(config.apiBaseUrl);

export type VisitService = ReturnType<typeof createVisitService>;
