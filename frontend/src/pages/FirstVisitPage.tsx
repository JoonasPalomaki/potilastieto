import { ChangeEvent, FormEvent, MutableRefObject, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';

import { useAuth } from '../contexts/AuthContext';
import {
  ApiError,
  AppointmentDetail,
  InitialVisit,
  PatientCreateRequest,
  PatientDetail,
  VisitDiagnosesUpdate,
  VisitOrdersUpdate,
  VisitService,
  visitService,
} from '../services/visitService';

interface FormState {
  visitType: string;
  location: string;
  startedAt: string;
  endedAt: string;
  attendingProviderId: string;
  reason: string;
  anamnesis: string;
  status: string;
  diagnosisCode: string;
  diagnosisDescription: string;
  orderType: string;
  orderDetails: string;
  summary: string;
}

interface PatientFormState {
  identifier: string;
  firstName: string;
  lastName: string;
  dateOfBirth: string;
  sex: string;
  phone: string;
  email: string;
}

const initialFormState: FormState = {
  visitType: '',
  location: '',
  startedAt: '',
  endedAt: '',
  attendingProviderId: '',
  reason: '',
  anamnesis: '',
  status: '',
  diagnosisCode: '',
  diagnosisDescription: '',
  orderType: '',
  orderDetails: '',
  summary: '',
};

const initialPatientForm: PatientFormState = {
  identifier: '',
  firstName: '',
  lastName: '',
  dateOfBirth: '',
  sex: '',
  phone: '',
  email: '',
};

const formatDateTimeLocal = (value: string | null | undefined): string => {
  if (!value) {
    return '';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
};

const toIsoString = (value: string): string | undefined => {
  if (!value) {
    return undefined;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return undefined;
  }
  return date.toISOString();
};

const resolveApiErrorMessage = (error: ApiError): string => {
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

const focusFirstError = (
  errors: Record<string, string>,
  refs: MutableRefObject<Record<string, HTMLInputElement | HTMLTextAreaElement | null>>,
) => {
  const firstKey = Object.keys(errors)[0];
  if (!firstKey) {
    return;
  }
  const element = refs.current[firstKey];
  if (element) {
    element.focus();
  }
};

const FirstVisitPage = ({ service = visitService }: { service?: VisitService }) => {
  const { session, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [formState, setFormState] = useState<FormState>(initialFormState);
  const [patientForm, setPatientForm] = useState<PatientFormState>(initialPatientForm);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [appointment, setAppointment] = useState<AppointmentDetail | null>(null);
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [visit, setVisit] = useState<InitialVisit | null>(null);
  const [createdPatientId, setCreatedPatientId] = useState<number | null>(null);
  const fieldRefs = useRef<Record<string, HTMLInputElement | HTMLTextAreaElement | null>>({});

  const visitId = useMemo(() => {
    const value = searchParams.get('visitId');
    if (!value) {
      return null;
    }
    const parsed = Number(value);
    return Number.isNaN(parsed) ? null : parsed;
  }, [searchParams]);

  const appointmentIdFromParams = useMemo(() => {
    const value = searchParams.get('appointmentId');
    if (!value) {
      return null;
    }
    const parsed = Number(value);
    return Number.isNaN(parsed) ? null : parsed;
  }, [searchParams]);

  const authorization = useMemo(() => {
    if (!session) {
      return null;
    }
    return `${session.tokenType} ${session.accessToken}`;
  }, [session]);

  const needsPatientForm = useMemo(() => !patient && !createdPatientId, [patient, createdPatientId]);

  const registerFieldRef = useCallback(
    (key: string) => (element: HTMLInputElement | HTMLTextAreaElement | null) => {
      fieldRefs.current[key] = element;
    },
    [],
  );

  const handleUnauthorized = useCallback(() => {
    logout();
    navigate('/login', {
      replace: true,
      state: { from: { pathname: location.pathname, search: location.search } },
    });
  }, [location.pathname, location.search, logout, navigate]);

  const applyVisitToForm = useCallback((visitData: InitialVisit) => {
    setFormState((previous) => ({
      ...previous,
      visitType: visitData.basics.visit_type ?? '',
      location: visitData.basics.location ?? '',
      startedAt: formatDateTimeLocal(visitData.basics.started_at),
      endedAt: formatDateTimeLocal(visitData.basics.ended_at),
      attendingProviderId: visitData.basics.attending_provider_id?.toString() ?? '',
      reason: visitData.reason.reason ?? '',
      anamnesis: visitData.anamnesis.content ?? '',
      status: visitData.status.content ?? '',
      diagnosisCode: visitData.diagnoses.diagnoses[0]?.code ?? '',
      diagnosisDescription: visitData.diagnoses.diagnoses[0]?.description ?? '',
      orderType: visitData.orders.orders[0]?.order_type ?? '',
      orderDetails:
        visitData.orders.orders[0]?.details &&
        Object.keys(visitData.orders.orders[0]?.details).length > 0
          ? JSON.stringify(visitData.orders.orders[0]?.details, null, 2)
          : '',
      summary: visitData.summary.content ?? '',
    }));
  }, []);

  const applyAppointmentToForm = useCallback((appointmentData: AppointmentDetail) => {
    setFormState((previous) => ({
      ...previous,
      location: appointmentData.location ?? previous.location,
      startedAt: appointmentData.start_time ? formatDateTimeLocal(appointmentData.start_time) : previous.startedAt,
      endedAt: appointmentData.end_time ? formatDateTimeLocal(appointmentData.end_time) : previous.endedAt,
      attendingProviderId: appointmentData.provider_id?.toString() ?? previous.attendingProviderId,
    }));
  }, []);

  useEffect(() => {
    if (!authorization) {
      return;
    }

    const controller = new AbortController();

    const load = async () => {
      if (!visitId && !appointmentIdFromParams) {
        setLoadError('Ajanvarauksen tai ensikäynnin tunnistetta ei annettu.');
        return;
      }

      setIsLoading(true);
      setLoadError(null);

      try {
        if (visitId) {
          const visitData = await service.getInitialVisit(visitId, {
            authorization,
            signal: controller.signal,
          });
          setVisit(visitData);
          applyVisitToForm(visitData);

          if (visitData.appointment_id) {
            const appointmentData = await service.getAppointment(visitData.appointment_id, {
              authorization,
              signal: controller.signal,
            });
            setAppointment(appointmentData);
            applyAppointmentToForm(appointmentData);
            if (appointmentData.patient_id) {
              const patientData = await service.getPatient(appointmentData.patient_id, {
                authorization,
                signal: controller.signal,
              });
              setPatient(patientData);
            }
          } else if (visitData.patient_id) {
            const patientData = await service.getPatient(visitData.patient_id, {
              authorization,
              signal: controller.signal,
            });
            setPatient(patientData);
          }
        } else if (appointmentIdFromParams) {
          const appointmentData = await service.getAppointment(appointmentIdFromParams, {
            authorization,
            signal: controller.signal,
          });
          setAppointment(appointmentData);
          applyAppointmentToForm(appointmentData);
          if (appointmentData.patient_id) {
            const patientData = await service.getPatient(appointmentData.patient_id, {
              authorization,
              signal: controller.signal,
            });
            setPatient(patientData);
          }
        }
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        if (error instanceof ApiError && error.status === 401) {
          handleUnauthorized();
          return;
        }
        if (error instanceof ApiError && error.status === 404) {
          setLoadError('Ensikäyntiä ei löytynyt.');
        } else {
          setLoadError('Ensikäynnin tietojen hakeminen epäonnistui.');
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    };

    void load();

    return () => {
      controller.abort();
    };
  }, [
    appointmentIdFromParams,
    applyAppointmentToForm,
    applyVisitToForm,
    authorization,
    handleUnauthorized,
    service,
    visitId,
  ]);

  const handleFormChange = useCallback((key: keyof FormState) => {
    return (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const value = event.target.value;
      setFormState((previous) => ({ ...previous, [key]: value }));
      setFormErrors((previous) => {
        if (!previous[key]) {
          return previous;
        }
        const { [key]: _, ...rest } = previous;
        return rest;
      });
    };
  }, []);

  const handlePatientChange = useCallback((key: keyof PatientFormState) => {
    return (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      const value = event.target.value;
      setPatientForm((previous) => ({ ...previous, [key]: value }));
      setFormErrors((previous) => {
        if (!previous[key]) {
          return previous;
        }
        const { [key]: _, ...rest } = previous;
        return rest;
      });
    };
  }, []);

  const validateForm = useCallback(() => {
    const errors: Record<string, string> = {};

    if (!formState.reason.trim()) {
      errors.reason = 'Syy tuloon on pakollinen.';
    }
    if (!formState.anamnesis.trim()) {
      errors.anamnesis = 'Anamneesi on pakollinen.';
    }
    if (!formState.status.trim()) {
      errors.status = 'Statuskuvaus on pakollinen.';
    }
    if (!formState.diagnosisCode.trim()) {
      errors.diagnosisCode = 'Diagnoosikoodi on pakollinen.';
    }
    if (!formState.summary.trim()) {
      errors.summary = 'Yhteenveto on pakollinen.';
    }

    if (needsPatientForm) {
      if (!patientForm.identifier.trim()) {
        errors.identifier = 'Henkilötunnus on pakollinen.';
      }
      if (!patientForm.firstName.trim()) {
        errors.firstName = 'Etunimi on pakollinen.';
      }
      if (!patientForm.lastName.trim()) {
        errors.lastName = 'Sukunimi on pakollinen.';
      }
    }

    return errors;
  }, [formState, needsPatientForm, patientForm]);

  const buildDiagnosesPayload = (): VisitDiagnosesUpdate => ({
    diagnoses: [
      {
        code: formState.diagnosisCode.trim(),
        description: formState.diagnosisDescription.trim() || undefined,
        is_primary: true,
      },
    ],
  });

  const buildOrdersPayload = (): VisitOrdersUpdate | undefined => {
    if (!formState.orderType.trim() && !formState.orderDetails.trim()) {
      return undefined;
    }

    let details: Record<string, unknown> | undefined;
    if (formState.orderDetails.trim()) {
      try {
        details = JSON.parse(formState.orderDetails);
      } catch (error) {
        details = { kuvaus: formState.orderDetails.trim() };
      }
    }

    return {
      orders: [
        {
          order_type: formState.orderType.trim() || 'muu',
          status: 'planned',
          details,
        },
      ],
    };
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!authorization) {
      setSaveError('Kirjautumistiedot puuttuvat.');
      return;
    }

    setSaveError(null);
    setSaveSuccess(null);

    const validationErrors = validateForm();
    if (Object.keys(validationErrors).length > 0) {
      setFormErrors(validationErrors);
      focusFirstError(validationErrors, fieldRefs);
      return;
    }

    const appointmentId = visit?.appointment_id ?? appointment?.id ?? appointmentIdFromParams;
    if (!appointmentId) {
      setSaveError('Ajanvarausta ei ole valittu.');
      return;
    }

    setIsSaving(true);

    try {
      let activePatient = patient;

      if (!activePatient) {
        const payload: PatientCreateRequest = {
          identifier: patientForm.identifier.trim(),
          first_name: patientForm.firstName.trim(),
          last_name: patientForm.lastName.trim(),
          date_of_birth: patientForm.dateOfBirth ? patientForm.dateOfBirth : undefined,
          sex: patientForm.sex ? patientForm.sex.toLowerCase() : undefined,
          contact_info:
            patientForm.phone || patientForm.email
              ? {
                  phone: patientForm.phone || undefined,
                  email: patientForm.email || undefined,
                }
              : undefined,
        };
        activePatient = await service.createPatient(payload, { authorization });
        setPatient(activePatient);
        setCreatedPatientId(activePatient.id);
      }

      const basics = {
        visit_type: formState.visitType.trim() || undefined,
        location: formState.location.trim() || undefined,
        started_at: toIsoString(formState.startedAt),
        ended_at: toIsoString(formState.endedAt),
        attending_provider_id: formState.attendingProviderId
          ? Number(formState.attendingProviderId)
          : undefined,
      };

      const visitPayload = {
        appointment_id: appointmentId,
        basics,
        reason: { reason: formState.reason.trim() },
        anamnesis: { content: formState.anamnesis.trim() },
        status: { content: formState.status.trim() },
        diagnoses: buildDiagnosesPayload(),
        orders: buildOrdersPayload(),
        summary: { content: formState.summary.trim() },
      };

      const savedVisit = await service.createInitialVisit(visitPayload, { authorization });
      setVisit(savedVisit);
      applyVisitToForm(savedVisit);
      setSaveSuccess('Ensikäynti tallennettiin onnistuneesti.');
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        handleUnauthorized();
        return;
      }
      if (error instanceof ApiError) {
        setSaveError(resolveApiErrorMessage(error));
      } else {
        setSaveError('Ensikäynnin tallennus epäonnistui.');
      }
    } finally {
      setIsSaving(false);
    }
  };

  if (!session) {
    return (
      <section className="space-y-6">
        <header className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-sky-400">Ensikäynti</p>
          <h2 className="text-3xl font-bold text-slate-100">Ensikäynnin valmistelu</h2>
        </header>
        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-200">
          Kirjaudu sisään tarkastellaksesi ensikäynnin tietoja.
        </div>
      </section>
    );
  }

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-sky-400">Ensikäynti</p>
        <h2 className="text-3xl font-bold text-slate-100">Ensikäynnin valmistelu</h2>
        <p className="text-sm text-slate-300">
          Täytä potilaan esitiedot ja vastaanotolla tarvittavat kirjaukset ennen ensikäynnin aloittamista.
        </p>
      </header>

      {isLoading && (
        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-200">
          Ladataan ensikäynnin tietoja...
        </div>
      )}

      {loadError && !isLoading && (
        <div
          role="alert"
          aria-live="assertive"
          className="rounded-lg border border-rose-500/40 bg-rose-900/20 p-6 text-sm text-rose-200"
        >
          {loadError}
        </div>
      )}

      {!isLoading && !loadError && (
        <form className="space-y-6" onSubmit={handleSubmit} noValidate>
          {saveError && (
            <div
              role="alert"
              aria-live="assertive"
              className="rounded-lg border border-rose-500/40 bg-rose-900/20 p-4 text-sm text-rose-200"
            >
              {saveError}
            </div>
          )}

          {saveSuccess && (
            <div
              role="status"
              aria-live="polite"
              className="rounded-lg border border-emerald-500/30 bg-emerald-900/20 p-4 text-sm text-emerald-200"
            >
              {saveSuccess}
            </div>
          )}

          <div className="grid gap-6 lg:grid-cols-2">
            <fieldset className="space-y-4 rounded-lg border border-slate-800 bg-slate-900/60 p-6" aria-describedby="patient-panel">
              <legend className="px-2 text-sm font-semibold uppercase tracking-wide text-slate-300">Potilas</legend>
              <p id="patient-panel" className="text-sm text-slate-400">
                Tarkista potilaan perustiedot ennen käynnin kirjaamista.
              </p>
              {patient ? (
                <dl className="divide-y divide-slate-800 text-sm text-slate-200">
                  <div className="flex items-center justify-between py-2">
                    <dt className="font-medium text-slate-300">Nimi</dt>
                    <dd>
                      {patient.last_name} {patient.first_name}
                    </dd>
                  </div>
                  <div className="flex items-center justify-between py-2">
                    <dt className="font-medium text-slate-300">Henkilötunnus</dt>
                    <dd>{patient.identifier ?? '—'}</dd>
                  </div>
                  <div className="flex items-center justify-between py-2">
                    <dt className="font-medium text-slate-300">Syntymäaika</dt>
                    <dd>{patient.date_of_birth ?? '—'}</dd>
                  </div>
                </dl>
              ) : (
                <div className="space-y-4">
                  <div>
                    <label htmlFor="patient-identifier" className="flex items-center justify-between text-sm font-medium text-slate-200">
                      Henkilötunnus
                      <span className="text-xs font-normal text-rose-300">pakollinen</span>
                    </label>
                    <input
                      id="patient-identifier"
                      name="patient-identifier"
                      ref={registerFieldRef('identifier')}
                      value={patientForm.identifier}
                      onChange={handlePatientChange('identifier')}
                      className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
                      aria-invalid={formErrors.identifier ? 'true' : 'false'}
                      aria-describedby={formErrors.identifier ? 'patient-identifier-error' : undefined}
                      autoComplete="off"
                    />
                    {formErrors.identifier && (
                      <p id="patient-identifier-error" className="mt-1 text-sm text-rose-300">
                        {formErrors.identifier}
                      </p>
                    )}
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <label htmlFor="patient-first-name" className="flex items-center justify-between text-sm font-medium text-slate-200">
                        Etunimi
                        <span className="text-xs font-normal text-rose-300">pakollinen</span>
                      </label>
                      <input
                        id="patient-first-name"
                        name="patient-first-name"
                        ref={registerFieldRef('firstName')}
                        value={patientForm.firstName}
                        onChange={handlePatientChange('firstName')}
                        className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
                        aria-invalid={formErrors.firstName ? 'true' : 'false'}
                        aria-describedby={formErrors.firstName ? 'patient-first-name-error' : undefined}
                        autoComplete="given-name"
                      />
                      {formErrors.firstName && (
                        <p id="patient-first-name-error" className="mt-1 text-sm text-rose-300">
                          {formErrors.firstName}
                        </p>
                      )}
                    </div>
                    <div>
                      <label htmlFor="patient-last-name" className="flex items-center justify-between text-sm font-medium text-slate-200">
                        Sukunimi
                        <span className="text-xs font-normal text-rose-300">pakollinen</span>
                      </label>
                      <input
                        id="patient-last-name"
                        name="patient-last-name"
                        ref={registerFieldRef('lastName')}
                        value={patientForm.lastName}
                        onChange={handlePatientChange('lastName')}
                        className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
                        aria-invalid={formErrors.lastName ? 'true' : 'false'}
                        aria-describedby={formErrors.lastName ? 'patient-last-name-error' : undefined}
                        autoComplete="family-name"
                      />
                      {formErrors.lastName && (
                        <p id="patient-last-name-error" className="mt-1 text-sm text-rose-300">
                          {formErrors.lastName}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <label htmlFor="patient-date-of-birth" className="text-sm font-medium text-slate-200">
                        Syntymäaika
                      </label>
                      <input
                        id="patient-date-of-birth"
                        name="patient-date-of-birth"
                        type="date"
                        value={patientForm.dateOfBirth}
                        onChange={handlePatientChange('dateOfBirth')}
                        className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
                        autoComplete="bday"
                      />
                    </div>
                    <div>
                      <label htmlFor="patient-sex" className="text-sm font-medium text-slate-200">
                        Sukupuoli
                      </label>
                      <select
                        id="patient-sex"
                        name="patient-sex"
                        value={patientForm.sex}
                        onChange={handlePatientChange('sex')}
                        className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
                      >
                        <option value="">Valitse</option>
                        <option value="female">Nainen</option>
                        <option value="male">Mies</option>
                        <option value="other">Muu</option>
                      </select>
                    </div>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <label htmlFor="patient-phone" className="text-sm font-medium text-slate-200">
                        Puhelin
                      </label>
                      <input
                        id="patient-phone"
                        name="patient-phone"
                        value={patientForm.phone}
                        onChange={handlePatientChange('phone')}
                        className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
                        autoComplete="tel"
                      />
                    </div>
                    <div>
                      <label htmlFor="patient-email" className="text-sm font-medium text-slate-200">
                        Sähköposti
                      </label>
                      <input
                        id="patient-email"
                        name="patient-email"
                        type="email"
                        value={patientForm.email}
                        onChange={handlePatientChange('email')}
                        className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
                        autoComplete="email"
                      />
                    </div>
                  </div>
                </div>
              )}
            </fieldset>

            <fieldset className="space-y-4 rounded-lg border border-slate-800 bg-slate-900/60 p-6" aria-describedby="basics-panel">
              <legend className="px-2 text-sm font-semibold uppercase tracking-wide text-slate-300">Perustiedot</legend>
              <p id="basics-panel" className="text-sm text-slate-400">
                Vastaanoton perusasetukset ja ajanvarauksen tiedot.
              </p>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="visit-location" className="text-sm font-medium text-slate-200">
                    Vastaanottopaikka
                  </label>
                  <input
                    id="visit-location"
                    name="visit-location"
                    ref={registerFieldRef('location')}
                    value={formState.location}
                    onChange={handleFormChange('location')}
                    className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
                  />
                </div>
                <div>
                  <label htmlFor="visit-type" className="text-sm font-medium text-slate-200">
                    Käyntityyppi
                  </label>
                  <input
                    id="visit-type"
                    name="visit-type"
                    value={formState.visitType}
                    onChange={handleFormChange('visitType')}
                    className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
                  />
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="visit-start" className="text-sm font-medium text-slate-200">
                    Alkamisaika
                  </label>
                  <input
                    id="visit-start"
                    name="visit-start"
                    type="datetime-local"
                    value={formState.startedAt}
                    onChange={handleFormChange('startedAt')}
                    className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
                  />
                </div>
                <div>
                  <label htmlFor="visit-end" className="text-sm font-medium text-slate-200">
                    Päättymisaika
                  </label>
                  <input
                    id="visit-end"
                    name="visit-end"
                    type="datetime-local"
                    value={formState.endedAt}
                    onChange={handleFormChange('endedAt')}
                    className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
                  />
                </div>
              </div>
              <div>
                <label htmlFor="visit-provider" className="text-sm font-medium text-slate-200">
                  Hoitava ammattilainen (ID)
                </label>
                <input
                  id="visit-provider"
                  name="visit-provider"
                  value={formState.attendingProviderId}
                  onChange={handleFormChange('attendingProviderId')}
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
                  inputMode="numeric"
                />
              </div>
            </fieldset>
          </div>

          <fieldset className="space-y-4 rounded-lg border border-slate-800 bg-slate-900/60 p-6" aria-describedby="reason-panel">
            <legend className="px-2 text-sm font-semibold uppercase tracking-wide text-slate-300">Syy tuloon</legend>
            <label htmlFor="visit-reason" className="flex items-center justify-between text-sm font-medium text-slate-200">
              Käynnin syy
              <span className="text-xs font-normal text-rose-300">pakollinen</span>
            </label>
            <textarea
              id="visit-reason"
              name="visit-reason"
              ref={registerFieldRef('reason')}
              value={formState.reason}
              onChange={handleFormChange('reason')}
              className="h-24 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
              aria-invalid={formErrors.reason ? 'true' : 'false'}
              aria-describedby={formErrors.reason ? 'visit-reason-error' : undefined}
            />
            {formErrors.reason && (
              <p id="visit-reason-error" className="text-sm text-rose-300">
                {formErrors.reason}
              </p>
            )}
          </fieldset>

          <fieldset className="space-y-4 rounded-lg border border-slate-800 bg-slate-900/60 p-6" aria-describedby="anamnesis-panel">
            <legend className="px-2 text-sm font-semibold uppercase tracking-wide text-slate-300">Anamneesi</legend>
            <label htmlFor="visit-anamnesis" className="flex items-center justify-between text-sm font-medium text-slate-200">
              Anamneesikuvaus
              <span className="text-xs font-normal text-rose-300">pakollinen</span>
            </label>
            <textarea
              id="visit-anamnesis"
              name="visit-anamnesis"
              ref={registerFieldRef('anamnesis')}
              value={formState.anamnesis}
              onChange={handleFormChange('anamnesis')}
              className="h-32 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
              aria-invalid={formErrors.anamnesis ? 'true' : 'false'}
              aria-describedby={formErrors.anamnesis ? 'visit-anamnesis-error' : undefined}
            />
            {formErrors.anamnesis && (
              <p id="visit-anamnesis-error" className="text-sm text-rose-300">
                {formErrors.anamnesis}
              </p>
            )}
          </fieldset>

          <fieldset className="space-y-4 rounded-lg border border-slate-800 bg-slate-900/60 p-6" aria-describedby="status-panel">
            <legend className="px-2 text-sm font-semibold uppercase tracking-wide text-slate-300">Status</legend>
            <label htmlFor="visit-status" className="flex items-center justify-between text-sm font-medium text-slate-200">
              Statuskirjaus
              <span className="text-xs font-normal text-rose-300">pakollinen</span>
            </label>
            <textarea
              id="visit-status"
              name="visit-status"
              ref={registerFieldRef('status')}
              value={formState.status}
              onChange={handleFormChange('status')}
              className="h-32 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
              aria-invalid={formErrors.status ? 'true' : 'false'}
              aria-describedby={formErrors.status ? 'visit-status-error' : undefined}
            />
            {formErrors.status && (
              <p id="visit-status-error" className="text-sm text-rose-300">
                {formErrors.status}
              </p>
            )}
          </fieldset>

          <fieldset className="space-y-4 rounded-lg border border-slate-800 bg-slate-900/60 p-6" aria-describedby="diagnoses-panel">
            <legend className="px-2 text-sm font-semibold uppercase tracking-wide text-slate-300">Diagnoosit</legend>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="diagnosis-code" className="flex items-center justify-between text-sm font-medium text-slate-200">
                  Diagnoosikoodi
                  <span className="text-xs font-normal text-rose-300">pakollinen</span>
                </label>
                <input
                  id="diagnosis-code"
                  name="diagnosis-code"
                  ref={registerFieldRef('diagnosisCode')}
                  value={formState.diagnosisCode}
                  onChange={handleFormChange('diagnosisCode')}
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
                  aria-invalid={formErrors.diagnosisCode ? 'true' : 'false'}
                  aria-describedby={formErrors.diagnosisCode ? 'diagnosis-code-error' : undefined}
                />
                {formErrors.diagnosisCode && (
                  <p id="diagnosis-code-error" className="mt-1 text-sm text-rose-300">
                    {formErrors.diagnosisCode}
                  </p>
                )}
              </div>
              <div>
                <label htmlFor="diagnosis-description" className="text-sm font-medium text-slate-200">
                  Diagnoosin kuvaus
                </label>
                <input
                  id="diagnosis-description"
                  name="diagnosis-description"
                  value={formState.diagnosisDescription}
                  onChange={handleFormChange('diagnosisDescription')}
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
              </div>
            </div>
          </fieldset>

          <fieldset className="space-y-4 rounded-lg border border-slate-800 bg-slate-900/60 p-6" aria-describedby="orders-panel">
            <legend className="px-2 text-sm font-semibold uppercase tracking-wide text-slate-300">Määräykset</legend>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="order-type" className="text-sm font-medium text-slate-200">
                  Määräyksen tyyppi
                </label>
                <input
                  id="order-type"
                  name="order-type"
                  value={formState.orderType}
                  onChange={handleFormChange('orderType')}
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
              </div>
              <div>
                <label htmlFor="order-details" className="text-sm font-medium text-slate-200">
                  Lisätiedot
                </label>
                <textarea
                  id="order-details"
                  name="order-details"
                  value={formState.orderDetails}
                  onChange={handleFormChange('orderDetails')}
                  className="h-24 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
              </div>
            </div>
          </fieldset>

          <fieldset className="space-y-4 rounded-lg border border-slate-800 bg-slate-900/60 p-6" aria-describedby="summary-panel">
            <legend className="px-2 text-sm font-semibold uppercase tracking-wide text-slate-300">Yhteenveto</legend>
            <label htmlFor="visit-summary" className="flex items-center justify-between text-sm font-medium text-slate-200">
              Yhteenvetomuistio
              <span className="text-xs font-normal text-rose-300">pakollinen</span>
            </label>
            <textarea
              id="visit-summary"
              name="visit-summary"
              ref={registerFieldRef('summary')}
              value={formState.summary}
              onChange={handleFormChange('summary')}
              className="h-32 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
              aria-invalid={formErrors.summary ? 'true' : 'false'}
              aria-describedby={formErrors.summary ? 'visit-summary-error' : undefined}
            />
            {formErrors.summary && (
              <p id="visit-summary-error" className="text-sm text-rose-300">
                {formErrors.summary}
              </p>
            )}
          </fieldset>

          <div className="flex items-center justify-end gap-3">
            <button
              type="submit"
              className="rounded-md bg-sky-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition focus:outline-none focus:ring-2 focus:ring-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isSaving}
              aria-disabled={isSaving ? 'true' : 'false'}
              aria-busy={isSaving ? 'true' : 'false'}
            >
              {isSaving ? 'Tallennetaan…' : 'Tallenna ensikäynti'}
            </button>
          </div>
        </form>
      )}
    </section>
  );
};

export default FirstVisitPage;
