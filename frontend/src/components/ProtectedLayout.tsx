import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../contexts/AuthContext';

const ProtectedLayout = () => {
  const { isAuthenticated, initializing, logout, session } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  if (initializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-100">
        <p className="text-sm text-slate-300">Ladataan...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/70">
        <div className="mx-auto flex max-w-5xl flex-col gap-2 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-sky-400">Potilastieto</p>
            <h1 className="text-lg font-bold">Potilastietojärjestelmä</h1>
          </div>
          <div className="flex items-center justify-between gap-4 text-sm">
            {session?.username && (
              <span className="text-slate-300">
                Kirjautunut: <span className="font-semibold text-slate-100">{session.username}</span>
              </span>
            )}
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-md border border-slate-700 bg-slate-800 px-3 py-1.5 text-sm font-medium text-slate-100 transition hover:border-slate-600 hover:bg-slate-700"
            >
              Kirjaudu ulos
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
};

export default ProtectedLayout;
