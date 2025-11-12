import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../contexts/AuthContext';
import { AuthError } from '../services/authService';

type LocationState = { from?: { pathname: string } } | undefined;

const LoginPage = () => {
  const { initializing, isAuthenticated, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const redirectPath = useMemo(() => {
    const state = location.state as LocationState;
    return state?.from?.pathname ?? '/patients';
  }, [location.state]);

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [formErrors, setFormErrors] = useState<{ username?: string; password?: string }>({});
  const [serverError, setServerError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!initializing && isAuthenticated) {
      navigate(redirectPath, { replace: true });
    }
  }, [initializing, isAuthenticated, navigate, redirectPath]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const errors: { username?: string; password?: string } = {};

    if (!username.trim()) {
      errors.username = 'Anna käyttäjätunnus.';
    }

    if (!password) {
      errors.password = 'Anna salasana.';
    }

    setFormErrors(errors);

    if (Object.keys(errors).length > 0) {
      return;
    }

    setServerError('');
    setIsSubmitting(true);

    try {
      await login({ username: username.trim(), password });
      navigate(redirectPath, { replace: true });
    } catch (error) {
      if (error instanceof AuthError && error.status === 401) {
        setServerError('Virheelliset kirjautumistiedot. Tarkista käyttäjätunnus ja salasana.');
      } else {
        console.error('Kirjautumisessa tapahtui virhe', error);
        setServerError('Kirjautuminen epäonnistui. Yritä uudelleen myöhemmin.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (initializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-100">
        <p className="text-sm text-slate-300">Ladataan...</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-6 py-12 text-slate-100">
      <div className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900/80 p-8 shadow-lg">
        <header className="mb-6 text-center">
          <p className="text-xs font-semibold uppercase tracking-widest text-sky-400">Potilastieto</p>
          <h1 className="mt-2 text-2xl font-bold">Kirjaudu sisään</h1>
          <p className="mt-1 text-sm text-slate-400">Syötä tunnuksesi päästäksesi potilaslistaukseen.</p>
        </header>
        <form className="space-y-5" onSubmit={handleSubmit} noValidate>
          <div>
            <label htmlFor="username" className="block text-sm font-medium text-slate-200">
              Käyttäjätunnus
            </label>
            <input
              id="username"
              name="username"
              type="text"
              autoComplete="username"
              className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-base text-slate-100 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
              value={username}
              onChange={(event) => {
                setUsername(event.target.value);
                if (formErrors.username) {
                  setFormErrors((prev) => ({ ...prev, username: undefined }));
                }
                if (serverError) {
                  setServerError('');
                }
              }}
              aria-invalid={Boolean(formErrors.username)}
              aria-describedby="username-error"
              disabled={isSubmitting}
            />
            {formErrors.username && (
              <p id="username-error" className="mt-1 text-sm text-rose-400">
                {formErrors.username}
              </p>
            )}
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-200">
              Salasana
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-base text-slate-100 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
                if (formErrors.password) {
                  setFormErrors((prev) => ({ ...prev, password: undefined }));
                }
                if (serverError) {
                  setServerError('');
                }
              }}
              aria-invalid={Boolean(formErrors.password)}
              aria-describedby="password-error"
              disabled={isSubmitting}
            />
            {formErrors.password && (
              <p id="password-error" className="mt-1 text-sm text-rose-400">
                {formErrors.password}
              </p>
            )}
          </div>
          {serverError && <p className="text-sm text-rose-400">{serverError}</p>}
          <button
            type="submit"
            className="w-full rounded-md bg-sky-500 px-4 py-2 text-center text-base font-semibold text-white transition hover:bg-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-600 disabled:cursor-not-allowed disabled:bg-slate-600"
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Kirjaudutaan...' : 'Kirjaudu sisään'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;
