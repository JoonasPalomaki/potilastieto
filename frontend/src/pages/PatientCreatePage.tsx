import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { useAuth } from '../contexts/AuthContext';
import { ApiError, PatientCreateRequest, VisitService, visitService } from '../services/visitService';
import { resolveApiErrorMessage } from '../utils/apiErrors';

interface PatientFormState {
  identifier?: string;
  firstName: string;
  lastName: string;
  dateOfBirth: string;
  sex: string;
  phone: string;
  email: string;
}

const initialState: PatientFormState = {
  identifier: '',
  firstName: '',
  lastName: '',
  dateOfBirth: '',
  sex: '',
  phone: '',
  email: '',
};

const HETU_CHECK_CHARS = '0123456789ABCDEFHJKLMNPRSTUVWXY';
const HETU_PATTERN = /^(\d{6})([A+-])(\d{3})([0-9A-Z])$/;

const validateFinnishHetu = (
  identifier: string,
  options: { dateOfBirth?: string; sex?: string },
): string | null => {
  const trimmed = identifier.trim();
  const formatted = trimmed.toUpperCase();
  const match = formatted.match(HETU_PATTERN);
  if (!match) {
    return 'Henkilötunnuksen muoto on virheellinen.';
  }

  const [, datePart, separator, individualPart, checksumChar] = match;
  const day = Number.parseInt(datePart.slice(0, 2), 10);
  const month = Number.parseInt(datePart.slice(2, 4), 10);
  const yearSuffix = Number.parseInt(datePart.slice(4), 10);

  const centuryMap: Record<string, number> = {
    '+': 1800,
    '-': 1900,
    A: 2000,
    B: 2100,
    C: 2200,
    D: 2300,
    E: 2400,
    F: 2500,
  };

  if (!centuryMap[separator]) {
    return 'Henkilötunnuksen vuosisatamerkki on virheellinen.';
  }

  const year = centuryMap[separator] + yearSuffix;
  const date = new Date(Date.UTC(year, month - 1, day));
  if (
    Number.isNaN(date.getTime()) ||
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() + 1 !== month ||
    date.getUTCDate() !== day
  ) {
    return 'Henkilötunnuksen syntymäaika on virheellinen.';
  }

  const checksumSource = `${datePart}${individualPart}`;
  const checksumIndex = Number.parseInt(checksumSource, 10) % 31;
  const expectedChecksum = HETU_CHECK_CHARS[checksumIndex];
  if (checksumChar !== expectedChecksum) {
    return 'Henkilötunnuksen tarkistusmerkki on virheellinen.';
  }

  const derivedBirthDate = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  if (options.dateOfBirth && options.dateOfBirth !== derivedBirthDate) {
    return 'Syntymäaika ei täsmää henkilötunnuksen kanssa.';
  }

  const derivedSex = Number.parseInt(individualPart, 10) % 2 ? 'male' : 'female';
  if (options.sex && options.sex !== derivedSex) {
    return 'Sukupuoli ei täsmää henkilötunnuksen kanssa.';
  }

  return null;
};

const PatientCreatePage = ({ service = visitService }: { service?: VisitService }) => {
  const { session } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [formState, setFormState] = useState<PatientFormState>(initialState);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const redirectTimerRef = useRef<number | null>(null);

  const selectionMode = searchParams.get('select') === 'first-visit';
  const selectionReturnToParam = searchParams.get('returnTo');

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

  const authorization = useMemo(() => {
    if (!session) {
      return null;
    }
    return `${session.tokenType} ${session.accessToken}`;
  }, [session]);

  const handleFieldChange = useCallback((key: keyof PatientFormState) => {
    return (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
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

  const validateForm = useCallback(() => {
    const errors: Record<string, string> = {};
    const trimmedIdentifier = formState.identifier?.trim() ?? '';
    const normalizedSex = formState.sex ? formState.sex.trim().toLowerCase() : '';

    if (!formState.firstName.trim()) {
      errors.firstName = 'Etunimi on pakollinen.';
    }
    if (!formState.lastName.trim()) {
      errors.lastName = 'Sukunimi on pakollinen.';
    }

    if (trimmedIdentifier) {
      const identifierError = validateFinnishHetu(trimmedIdentifier, {
        dateOfBirth: formState.dateOfBirth || undefined,
        sex: normalizedSex || undefined,
      });
      if (identifierError) {
        errors.identifier = identifierError;
      }
    } else {
      if (!formState.dateOfBirth) {
        errors.dateOfBirth = 'Syntymäaika on pakollinen ilman henkilötunnusta.';
      }
      if (!normalizedSex) {
        errors.sex = 'Sukupuoli on pakollinen ilman henkilötunnusta.';
      }
    }

    return errors;
  }, [formState]);

  const buildReturnUrl = useCallback(
    (patientId: number) => {
      if (!selectionMode) {
        return '/patients';
      }
      const basePath = selectionReturnTo || '/first-visit';
      const [pathname, query = ''] = basePath.split('?');
      const params = new URLSearchParams(query);
      params.set('patientId', String(patientId));
      const queryString = params.toString();
      return `${pathname}${queryString ? `?${queryString}` : ''}`;
    },
    [selectionMode, selectionReturnTo],
  );

  useEffect(() => {
    return () => {
      if (redirectTimerRef.current) {
        window.clearTimeout(redirectTimerRef.current);
      }
    };
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitError(null);
    setSubmitSuccess(null);

    const errors = validateForm();
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      return;
    }

    if (!authorization) {
      setSubmitError('Kirjautumistiedot puuttuvat.');
      return;
    }

    setIsSubmitting(true);

    try {
      const trimmedIdentifier = formState.identifier?.trim() ?? '';
      const normalizedSex = formState.sex ? formState.sex.trim().toLowerCase() : '';

      const payload: PatientCreateRequest = {
        first_name: formState.firstName.trim(),
        last_name: formState.lastName.trim(),
        date_of_birth: formState.dateOfBirth ? formState.dateOfBirth : undefined,
        sex: normalizedSex || undefined,
        contact_info:
          formState.phone || formState.email
            ? {
                phone: formState.phone || undefined,
                email: formState.email || undefined,
              }
            : undefined,
      };

      if (trimmedIdentifier) {
        payload.identifier = trimmedIdentifier.toUpperCase();
      }

      const createdPatient = await service.createPatient(payload, { authorization });
      setSubmitSuccess('Potilas lisättiin onnistuneesti. Siirrytään takaisin näkymään.');

      const redirectUrl = buildReturnUrl(createdPatient.id);
      redirectTimerRef.current = window.setTimeout(() => {
        navigate(redirectUrl, { replace: selectionMode });
      }, 1200);
    } catch (error) {
      if (error instanceof ApiError) {
        setSubmitError(resolveApiErrorMessage(error));
      } else {
        setSubmitError('Potilaan tallentaminen epäonnistui.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const cancelUrl = selectionMode ? selectionReturnTo : '/patients';

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-sky-400">Potilaat</p>
        <h2 className="text-2xl font-bold">Lisää uusi potilas</h2>
        <p className="text-sm text-slate-300">
          Täytä potilaan perustiedot ja tallenna ne järjestelmään. Onnistuneen tallennuksen jälkeen palaat
          potilaslistalle{selectionMode ? ' tai ensikäynnille.' : '.'}
        </p>
      </header>

      {selectionMode && (
        <div className="rounded-lg border border-sky-500/40 bg-sky-900/20 p-4 text-sm text-slate-100">
          <p className="font-medium">Uusi potilas liitetään ensikäyntilomakkeelle automaattisesti tallennuksen jälkeen.</p>
          <p className="mt-1 text-slate-200">Voit peruuttaa toiminnon palaamalla ensikäyntiin ilman tallennusta.</p>
        </div>
      )}

      {submitError && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-900/20 px-4 py-3 text-sm text-rose-100">
          {submitError}
        </div>
      )}

      {submitSuccess && (
        <div className="rounded-lg border border-emerald-500/40 bg-emerald-900/20 px-4 py-3 text-sm text-emerald-100">
          {submitSuccess}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid gap-6 md:grid-cols-2">
          <div>
            <label htmlFor="identifier" className="text-sm font-medium text-slate-200">
              Henkilötunnus
            </label>
            <input
              id="identifier"
              name="identifier"
              value={formState.identifier}
              onChange={handleFieldChange('identifier')}
              type="text"
              autoComplete="off"
              className="mt-1 w-full rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            />
            {formErrors.identifier && <p className="mt-1 text-sm text-rose-300">{formErrors.identifier}</p>}
          </div>

          <div>
            <label htmlFor="dateOfBirth" className="text-sm font-medium text-slate-200">
              Syntymäaika
            </label>
            <input
              id="dateOfBirth"
              name="dateOfBirth"
              type="date"
              value={formState.dateOfBirth}
              onChange={handleFieldChange('dateOfBirth')}
              className="mt-1 w-full rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            />
            {formErrors.dateOfBirth && <p className="mt-1 text-sm text-rose-300">{formErrors.dateOfBirth}</p>}
          </div>

          <div>
            <label htmlFor="firstName" className="text-sm font-medium text-slate-200">
              Etunimi
            </label>
            <input
              id="firstName"
              name="firstName"
              type="text"
              value={formState.firstName}
              onChange={handleFieldChange('firstName')}
              className="mt-1 w-full rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            />
            {formErrors.firstName && <p className="mt-1 text-sm text-rose-300">{formErrors.firstName}</p>}
          </div>

          <div>
            <label htmlFor="lastName" className="text-sm font-medium text-slate-200">
              Sukunimi
            </label>
            <input
              id="lastName"
              name="lastName"
              type="text"
              value={formState.lastName}
              onChange={handleFieldChange('lastName')}
              className="mt-1 w-full rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            />
            {formErrors.lastName && <p className="mt-1 text-sm text-rose-300">{formErrors.lastName}</p>}
          </div>

          <div>
            <label htmlFor="sex" className="text-sm font-medium text-slate-200">
              Sukupuoli
            </label>
            <select
              id="sex"
              name="sex"
              value={formState.sex}
              onChange={handleFieldChange('sex')}
              className="mt-1 w-full rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            >
              <option value="">Valitse</option>
              <option value="female">Nainen</option>
              <option value="male">Mies</option>
              <option value="other">Muu</option>
            </select>
            {formErrors.sex && <p className="mt-1 text-sm text-rose-300">{formErrors.sex}</p>}
          </div>

          <div>
            <label htmlFor="phone" className="text-sm font-medium text-slate-200">
              Puhelin
            </label>
            <input
              id="phone"
              name="phone"
              type="tel"
              value={formState.phone}
              onChange={handleFieldChange('phone')}
              className="mt-1 w-full rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            />
          </div>

          <div>
            <label htmlFor="email" className="text-sm font-medium text-slate-200">
              Sähköposti
            </label>
            <input
              id="email"
              name="email"
              type="email"
              value={formState.email}
              onChange={handleFieldChange('email')}
              className="mt-1 w-full rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-3">
          <Link
            to={cancelUrl || '/patients'}
            className="rounded-md border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-slate-500 hover:text-white"
          >
            Peruuta
          </Link>
          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex items-center justify-center rounded-md bg-sky-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-950 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? 'Tallennetaan...' : 'Tallenna potilas'}
          </button>
        </div>
      </form>
    </section>
  );
};

export default PatientCreatePage;
