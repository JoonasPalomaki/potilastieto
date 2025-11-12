import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { config } from '../config';
import { useAuth } from '../contexts/AuthContext';

const sanitizeBaseUrl = (baseUrl: string) => baseUrl.replace(/\/$/, '');

interface PatientListItem {
  identifier: string;
  name?: string | null;
  status?: string | null;
}

interface PaginationMeta {
  total?: number;
  page?: number;
  size?: number;
  pages?: number;
}

interface PatientsResponse {
  items?: PatientListItem[];
  data?: PatientListItem[];
  patients?: PatientListItem[];
  meta?: PaginationMeta & {
    current_page?: number;
    per_page?: number;
    total_pages?: number;
  };
  pagination?: PaginationMeta & {
    current_page?: number;
    per_page?: number;
    total_pages?: number;
  };
  total?: number;
  page?: number;
  size?: number;
}

const normalizePatients = (payload: PatientsResponse): PatientListItem[] => {
  if (Array.isArray(payload.items)) {
    return payload.items;
  }
  if (Array.isArray(payload.data)) {
    return payload.data;
  }
  if (Array.isArray(payload.patients)) {
    return payload.patients;
  }
  return [];
};

const normalizeMeta = (payload: PatientsResponse): PaginationMeta | null => {
  const source = payload.meta ?? payload.pagination ?? null;

  if (source) {
    return {
      total: source.total,
      page: source.page ?? source.current_page,
      size: source.size ?? source.per_page,
      pages: source.pages ?? source.total_pages,
    };
  }

  if (payload.total || payload.page || payload.size) {
    return {
      total: payload.total,
      page: payload.page,
      size: payload.size,
    };
  }

  return null;
};

const PatientsPage = () => {
  const { session, logout } = useAuth();
  const navigate = useNavigate();
  const [patients, setPatients] = useState<PatientListItem[]>([]);
  const [pagination, setPagination] = useState<PaginationMeta | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const apiBaseUrl = useMemo(() => sanitizeBaseUrl(config.apiBaseUrl), []);

  useEffect(() => {
    if (!session) {
      return;
    }

    const controller = new AbortController();

    const fetchPatients = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(`${apiBaseUrl}/v1/patients`, {
          method: 'GET',
          headers: {
            Accept: 'application/json',
            Authorization: `${session.tokenType} ${session.accessToken}`,
          },
          signal: controller.signal,
        });

        if (response.status === 401) {
          logout();
          navigate('/login', { replace: true, state: { from: { pathname: '/patients' } } });
          return;
        }

        if (!response.ok) {
          throw new Error(`Patient list failed with status ${response.status}`);
        }

        const payload = (await response.json()) as PatientsResponse;
        setPatients(normalizePatients(payload));
        setPagination(normalizeMeta(payload));
      } catch (fetchError) {
        if (controller.signal.aborted) {
          return;
        }
        console.error('Potilastietojen haku epäonnistui', fetchError);
        setError('Potilastietojen hakeminen epäonnistui. Yritä uudelleen myöhemmin.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchPatients();

    return () => {
      controller.abort();
    };
  }, [apiBaseUrl, logout, navigate, session]);

  return (
    <section className="space-y-6">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-sky-400">Potilaat</p>
          <h2 className="text-2xl font-bold">Potilasluettelo</h2>
          <p className="mt-1 text-sm text-slate-400">
            Tarkastele järjestelmään rekisteröityjen potilaiden perustietoja.
          </p>
        </div>
        {pagination && (
          <div className="rounded-md border border-slate-800 bg-slate-900 px-4 py-2 text-sm text-slate-300">
            <p>
              Sivu {pagination.page ?? 1}{' '}
              {pagination.pages ? ` / ${pagination.pages}` : null}
            </p>
            {typeof pagination.total === 'number' && (
              <p className="text-xs text-slate-400">Yhteensä {pagination.total} potilasta</p>
            )}
          </div>
        )}
      </header>

      {isLoading && (
        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">
          Ladataan potilaslistaa...
        </div>
      )}

      {error && !isLoading && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-900/20 p-6 text-sm text-rose-200">{error}</div>
      )}

      {!isLoading && !error && patients.length === 0 && (
        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">
          Potilaslistaus on tyhjä.
        </div>
      )}

      {!isLoading && !error && patients.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-slate-800 shadow-sm">
          <table className="min-w-full divide-y divide-slate-800">
            <thead className="bg-slate-900/70">
              <tr>
                <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Tunniste
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Nimi
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Tila
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 bg-slate-900/40">
              {patients.map((patient) => (
                <tr key={patient.identifier} className="hover:bg-slate-900/80">
                  <td className="px-4 py-3 text-sm font-medium text-slate-100">{patient.identifier}</td>
                  <td className="px-4 py-3 text-sm text-slate-200">{patient.name ?? '—'}</td>
                  <td className="px-4 py-3 text-sm text-slate-200">{patient.status ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
};

export default PatientsPage;
