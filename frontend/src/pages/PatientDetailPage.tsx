import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { useAuth } from '../contexts/AuthContext';
import {
  ApiError,
  PatientDetail,
  PatientVisitSummary,
  VisitService,
  visitService,
} from '../services/visitService';

interface PatientDetailPageProps {
  service?: VisitService;
}

const formatDate = (value?: string | null): string => {
  if (!value) {
    return '—';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return '—';
  }
  return new Intl.DateTimeFormat('fi-FI').format(parsed);
};

const formatDateTime = (value?: string | null): string => {
  if (!value) {
    return '—';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return '—';
  }
  return new Intl.DateTimeFormat('fi-FI', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(parsed);
};

const getVisitTimeLabel = (visit: PatientVisitSummary): string => {
  return formatDateTime(visit.started_at ?? visit.created_at);
};

const PatientDetailPage = ({ service = visitService }: PatientDetailPageProps) => {
  const { patientId } = useParams();
  const navigate = useNavigate();
  const { session, logout } = useAuth();
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedVisitIds, setExpandedVisitIds] = useState<Set<number>>(new Set());

  const numericPatientId = useMemo(() => {
    if (!patientId) {
      return null;
    }
    const parsed = Number(patientId);
    return Number.isNaN(parsed) ? null : parsed;
  }, [patientId]);

  const authorization = useMemo(() => {
    if (!session) {
      return null;
    }
    return `${session.tokenType} ${session.accessToken}`;
  }, [session]);

  useEffect(() => {
    setExpandedVisitIds(new Set());
  }, [patient?.id]);

  useEffect(() => {
    if (!authorization) {
      setIsLoading(false);
      setError('Istunto on vanhentunut. Kirjaudu sisään uudelleen.');
      return;
    }

    if (!numericPatientId) {
      setIsLoading(false);
      setError('Potilaan tunnistetta ei löytynyt.');
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setError(null);

    service
      .getPatient(numericPatientId, { authorization, signal: controller.signal })
      .then((data) => {
        setPatient(data);
      })
      .catch((fetchError) => {
        if (controller.signal.aborted) {
          return;
        }
        if (fetchError instanceof ApiError && fetchError.status === 401) {
          logout();
          navigate('/login', { replace: true, state: { from: { pathname: `/patients/${numericPatientId}` } } });
          return;
        }
        console.error('Potilastietojen haku epäonnistui', fetchError);
        setError('Potilastietojen lataaminen epäonnistui. Yritä uudelleen myöhemmin.');
      })
      .finally(() => {
        setIsLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [authorization, numericPatientId, service, logout, navigate]);

  const visits = patient?.visits ?? [];
  const firstVisits = visits.slice(0, 3);
  const extraVisits = visits.slice(3);

  const toggleVisit = useCallback((visitId: number) => {
    setExpandedVisitIds((prev) => {
      const next = new Set(prev);
      if (next.has(visitId)) {
        next.delete(visitId);
      } else {
        next.add(visitId);
      }
      return next;
    });
  }, []);

  const renderVisitCard = (visit: PatientVisitSummary, index: number) => (
    <div key={visit.id} className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-400">
        <span className="font-semibold text-slate-200">Käynti #{index + 1}</span>
        <span>{getVisitTimeLabel(visit)}</span>
      </div>
      <p className="mt-2 text-base font-semibold text-slate-100">{visit.reason ?? 'Ei kirjattua käyntisyytä'}</p>
      <dl className="mt-3 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-slate-400">Tyyppi</dt>
          <dd className="text-slate-100">{visit.visit_type ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-slate-400">Sijainti</dt>
          <dd className="text-slate-100">{visit.location ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-slate-400">Käynnin tila</dt>
          <dd className="text-slate-100">{visit.status}</dd>
        </div>
        <div>
          <dt className="text-slate-400">Päättyi</dt>
          <dd className="text-slate-100">{formatDateTime(visit.ended_at)}</dd>
        </div>
      </dl>
    </div>
  );

  return (
    <section className="space-y-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-sky-400">Potilas</p>
          <h1 className="text-3xl font-bold text-slate-50">
            {patient ? `${patient.first_name} ${patient.last_name}` : 'Potilaan tiedot'}
          </h1>
          <p className="mt-1 text-sm text-slate-400">Yksityiskohtainen näkymä potilaan perustietoihin ja käyntihistoriaan.</p>
        </div>
        {patient && (
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 px-4 py-2 text-right text-sm text-slate-300">
            <p className="font-semibold text-slate-100">Käyntejä yhteensä</p>
            <p>{patient.visit_count ?? visits.length}</p>
          </div>
        )}
      </header>

      {isLoading && (
        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">
          Ladataan potilastietoja...
        </div>
      )}

      {error && !isLoading && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-900/20 p-6 text-sm text-rose-200">{error}</div>
      )}

      {!isLoading && !error && patient && (
        <div className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-lg border border-slate-800 bg-slate-900/60 shadow-sm">
              <div className="border-b border-slate-800 px-4 py-3">
                <h2 className="text-lg font-semibold text-slate-100">Perustiedot</h2>
              </div>
              <dl className="grid grid-cols-1 gap-4 px-6 py-5 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-slate-400">Henkilötunnus</dt>
                  <dd className="text-slate-100">{patient.identifier ?? '—'}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Syntymäaika</dt>
                  <dd className="text-slate-100">{formatDate(patient.date_of_birth)}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Sukupuoli</dt>
                  <dd className="text-slate-100">{patient.sex ?? '—'}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Kieli</dt>
                  <dd className="text-slate-100">{patient.language ?? '—'}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Tila</dt>
                  <dd className="text-slate-100">{patient.status ?? 'aktiivinen'}</dd>
                </div>
              </dl>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/60 shadow-sm">
              <div className="border-b border-slate-800 px-4 py-3">
                <h2 className="text-lg font-semibold text-slate-100">Yhteystiedot</h2>
              </div>
              <dl className="grid grid-cols-1 gap-4 px-6 py-5 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-slate-400">Puhelin</dt>
                  <dd className="text-slate-100">{patient.contact_info?.phone ?? '—'}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Sähköposti</dt>
                  <dd className="text-slate-100">{patient.contact_info?.email ?? '—'}</dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-slate-400">Osoite</dt>
                  <dd className="text-slate-100">
                    {patient.contact_info?.address?.street ?? '—'}
                    {patient.contact_info?.address?.postal_code || patient.contact_info?.address?.city ? (
                      <span className="block text-slate-300">
                        {[patient.contact_info?.address?.postal_code, patient.contact_info?.address?.city]
                          .filter(Boolean)
                          .join(' ')}
                      </span>
                    ) : null}
                  </dd>
                </div>
              </dl>
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-lg border border-slate-800 bg-slate-900/60 shadow-sm">
              <div className="border-b border-slate-800 px-4 py-3">
                <h2 className="text-lg font-semibold text-slate-100">Suostumukset</h2>
              </div>
              {patient.consents && patient.consents.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-slate-800">
                    <thead className="bg-slate-900/70 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">
                      <tr>
                        <th className="px-4 py-3">Tyyppi</th>
                        <th className="px-4 py-3">Tila</th>
                        <th className="px-4 py-3">Myönnetty</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800 text-sm">
                      {patient.consents.map((consent) => (
                        <tr key={consent.id}>
                          <td className="px-4 py-3 text-slate-100">{consent.type}</td>
                          <td className="px-4 py-3 text-slate-100">{consent.status}</td>
                          <td className="px-4 py-3 text-slate-100">{formatDateTime(consent.granted_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="px-6 py-5 text-sm text-slate-300">Ei kirjattuja suostumuksia.</p>
              )}
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-900/60 shadow-sm">
              <div className="border-b border-slate-800 px-4 py-3">
                <h2 className="text-lg font-semibold text-slate-100">Muutoshistoria</h2>
              </div>
              {patient.history && patient.history.length > 0 ? (
                <ul className="divide-y divide-slate-800">
                  {patient.history.map((entry) => (
                    <li key={entry.id} className="px-6 py-4 text-sm text-slate-200">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-semibold">{entry.change_type}</span>
                        <span className="text-xs text-slate-400">{formatDateTime(entry.changed_at)}</span>
                      </div>
                      {entry.reason && <p className="mt-1 text-slate-300">{entry.reason}</p>}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="px-6 py-5 text-sm text-slate-300">Ei kirjattuja muutoksia.</p>
              )}
            </div>
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-900/60 shadow-sm">
            <div className="border-b border-slate-800 px-4 py-3">
              <h2 className="text-lg font-semibold text-slate-100">Käyntihistoria</h2>
              <p className="text-sm text-slate-400">Ensimmäiset kolme käyntiä näytetään alla, loput löytyvät avattavista riveistä.</p>
            </div>
            <div className="space-y-4 px-4 py-5">
              {firstVisits.length > 0 ? (
                firstVisits.map((visit, index) => renderVisitCard(visit, index))
              ) : (
                <p className="text-sm text-slate-300">Ei kirjattuja käyntejä.</p>
              )}

              {extraVisits.length > 0 && (
                <div className="rounded-lg border border-slate-800 bg-slate-950/40">
                  <p className="border-b border-slate-800 px-4 py-2 text-sm font-semibold text-slate-100">
                    Lisäkäynnit ({extraVisits.length})
                  </p>
                  <div className="divide-y divide-slate-800">
                    {extraVisits.map((visit, index) => {
                      const isExpanded = expandedVisitIds.has(visit.id);
                      return (
                        <div key={visit.id}>
                          <button
                            type="button"
                            className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold text-slate-100 hover:bg-slate-900/60"
                            onClick={() => toggleVisit(visit.id)}
                            aria-expanded={isExpanded}
                          >
                            <span>Käynti #{firstVisits.length + index + 1}</span>
                            <span className="text-xs text-slate-400">{getVisitTimeLabel(visit)}</span>
                          </button>
                          {isExpanded && (
                            <div className="space-y-2 border-t border-slate-800 px-4 py-4 text-sm text-slate-200">
                              <p className="text-base font-semibold text-slate-100">{visit.reason ?? 'Ei kirjattua käyntisyytä'}</p>
                              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                                <div>
                                  <p className="text-slate-400">Tyyppi</p>
                                  <p className="text-slate-100">{visit.visit_type ?? '—'}</p>
                                </div>
                                <div>
                                  <p className="text-slate-400">Sijainti</p>
                                  <p className="text-slate-100">{visit.location ?? '—'}</p>
                                </div>
                                <div>
                                  <p className="text-slate-400">Käynnin tila</p>
                                  <p className="text-slate-100">{visit.status}</p>
                                </div>
                                <div>
                                  <p className="text-slate-400">Päättyi</p>
                                  <p className="text-slate-100">{formatDateTime(visit.ended_at)}</p>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

export default PatientDetailPage;
