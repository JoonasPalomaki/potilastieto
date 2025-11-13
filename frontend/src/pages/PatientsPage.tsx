import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { config } from '../config';
import { useAuth } from '../contexts/AuthContext';

const sanitizeBaseUrl = (baseUrl: string) => baseUrl.replace(/\/$/, '');

interface PatientListItem {
  id?: number;
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
  const [searchParams] = useSearchParams();
  const [patients, setPatients] = useState<PatientListItem[]>([]);
  const [pagination, setPagination] = useState<PaginationMeta | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const apiBaseUrl = useMemo(() => sanitizeBaseUrl(config.apiBaseUrl), []);

  const selectionMode = searchParams.get('select') === 'first-visit';
  const selectionReturnToParam = searchParams.get('returnTo');
  const selectionWantsCreation = selectionMode && searchParams.get('create') === '1';

  const selectionReturnTo = useMemo(() => {
    if (!selectionMode || !selectionReturnToParam) {
      return '/first-visit';
    }
    try {
      const decoded = decodeURIComponent(selectionReturnToParam);
      return decoded || '/first-visit';
    } catch (error) {
      console.warn('Virhe palautusosoitteen purkamisessa', error);
      return '/first-visit';
    }
  }, [selectionMode, selectionReturnToParam]);

  const buildReturnUrl = useCallback(
    (patientId: number) => {
      const basePath = selectionReturnTo || '/first-visit';
      const [pathname, query = ''] = basePath.split('?');
      const params = new URLSearchParams(query);
      params.set('patientId', String(patientId));
      const queryString = params.toString();
      return `${pathname}${queryString ? `?${queryString}` : ''}`;
    },
    [selectionReturnTo],
  );

  const handlePatientSelect = useCallback(
    (patientId?: number | null) => {
      if (!selectionMode || !patientId) {
        return;
      }
      navigate(buildReturnUrl(patientId));
    },
    [buildReturnUrl, navigate, selectionMode],
  );

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

      {selectionMode && (
        <div className="rounded-lg border border-sky-500/40 bg-sky-900/20 p-4 text-sm text-slate-100">
          <p className="font-medium text-slate-100">Valitse ensikäyntiä varten potilas listalta.</p>
          <p className="mt-1 text-slate-200">
            Valintapainike palauttaa sinut takaisin ensikäyntiin ja liittää potilaan lomakkeelle.
          </p>
          {selectionWantsCreation && (
            <p className="mt-2 text-slate-200">
              Voit lisätä uuden potilaan potilaslistan omista työkaluista ja palata tämän sivun kautta ensikäynnille.
            </p>
          )}
        </div>
      )}

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
                {selectionMode && (
                  <th
                    scope="col"
                    className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-400"
                  >
                    Toiminnot
                  </th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 bg-slate-900/40">
              {patients.map((patient) => (
                <tr key={patient.identifier} className="hover:bg-slate-900/80">
                  <td className="px-4 py-3 text-sm font-medium text-slate-100">{patient.identifier}</td>
                  <td className="px-4 py-3 text-sm text-slate-200">{patient.name ?? '—'}</td>
                  <td className="px-4 py-3 text-sm text-slate-200">{patient.status ?? '—'}</td>
                  {selectionMode && (
                    <td className="px-4 py-3 text-right text-sm text-slate-200">
                      <button
                        type="button"
                        onClick={() => handlePatientSelect(patient.id)}
                        disabled={!patient.id}
                        className="rounded-md border border-slate-600 px-3 py-1.5 font-medium text-slate-100 transition hover:border-sky-400 hover:text-white focus:outline-none focus:ring-2 focus:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Valitse
                      </button>
                    </td>
                  )}
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
