import { ChangeEvent, FormEvent, useMemo, useState } from 'react';
import { Navigate } from 'react-router-dom';

import { useAuth } from '../contexts/AuthContext';
import {
  DiagnosisCodeError,
  DiagnosisCodeImportIssue,
  DiagnosisCodeImportSummary,
  DiagnosisCodeService,
  diagnosisCodeService,
} from '../services/diagnosisCodeService';

const AdminDiagnosisCodesPage = ({ service = diagnosisCodeService }: { service?: DiagnosisCodeService }) => {
  const { session } = useAuth();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [summary, setSummary] = useState<DiagnosisCodeImportSummary | null>(null);
  const [issues, setIssues] = useState<DiagnosisCodeImportIssue[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const authorization = useMemo(() => {
    if (!session) {
      return null;
    }
    return `${session.tokenType} ${session.accessToken}`;
  }, [session]);

  if (!session || session.role !== 'admin') {
    return <Navigate to="/start" replace />;
  }

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    setSummary(null);
    setIssues([]);
    setErrorMessage(null);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedFile) {
      setErrorMessage('Valitse CSV-tiedosto ennen lataamista.');
      return;
    }
    if (!authorization) {
      setErrorMessage('Käyttöoikeus puuttuu. Kirjaudu sisään uudelleen.');
      return;
    }

    setIsUploading(true);
    setStatusMessage('Ladataan diagnoosikoodeja...');
    setErrorMessage(null);
    setIssues([]);

    try {
      const result = await service.importCodes({ file: selectedFile, authorization });
      setSummary(result);
      setIssues(result.issues ?? []);
      setStatusMessage('Tuonti valmis.');
    } catch (error) {
      if (error instanceof DiagnosisCodeError) {
        setErrorMessage(error.message);
        setIssues(error.issues ?? []);
      } else {
        setErrorMessage('Diagnoosikoodien tuonti epäonnistui. Yritä uudelleen myöhemmin.');
      }
      setStatusMessage('Tuonti epäonnistui.');
    } finally {
      setIsUploading(false);
    }
  };

  const showSummary = Boolean(summary) || issues.length > 0 || statusMessage || errorMessage;

  return (
    <div className="space-y-8" aria-live="polite">
      <header>
        <p className="text-xs uppercase tracking-wide text-sky-400">Ylläpito</p>
        <h2 className="text-2xl font-bold">Diagnoosikoodien hallinta</h2>
        <p className="mt-2 text-sm text-slate-300">
          Tuo Terveyden ja hyvinvoinnin laitoksen julkaisema diagnoosikoodisto CSV-muodossa. Kaikki tapahtumat audit-
          lokitetaan.
        </p>
      </header>

      <form className="space-y-4 rounded-lg border border-slate-800 bg-slate-900/60 p-6" onSubmit={handleSubmit}>
        <div>
          <label htmlFor="diagnosis-csv" className="block text-sm font-medium text-slate-200">
            Valitse CSV-tiedosto
          </label>
          <input
            id="diagnosis-csv"
            type="file"
            accept=".csv,text/csv"
            onChange={handleFileChange}
            className="mt-2 block w-full cursor-pointer rounded-md border border-slate-700 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
            aria-describedby="diagnosis-csv-help"
          />
          <p id="diagnosis-csv-help" className="mt-1 text-xs text-slate-400">
            Hyväksytyt muodot: .csv (UTF-8).
          </p>
        </div>
        <button
          type="submit"
          className="inline-flex items-center justify-center rounded-md border border-slate-700 bg-sky-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={!selectedFile || isUploading}
          aria-busy={isUploading}
        >
          {isUploading ? 'Lähetetään…' : 'Lataa diagnoosikoodit'}
        </button>
      </form>

      {showSummary && (
        <section className="space-y-4 rounded-lg border border-slate-800 bg-slate-900/60 p-6" aria-live="assertive">
          <h3 className="text-lg font-semibold">Tilannekatsaus</h3>
          {statusMessage && (
            <p role="status" className="text-sm text-slate-200">
              {statusMessage}
            </p>
          )}
          {summary && (
            <div className="text-sm text-slate-200">
              <p className="font-semibold">Tuonnin yhteenveto</p>
              <dl className="mt-2 grid grid-cols-1 gap-3 text-slate-300 sm:grid-cols-3">
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-400">Tuotu</dt>
                  <dd className="text-base font-bold text-slate-100">{summary.imported}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-400">Päivitetty</dt>
                  <dd className="text-base font-bold text-slate-100">{summary.updated ?? 0}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-400">Ohitettu</dt>
                  <dd className="text-base font-bold text-slate-100">{summary.skipped ?? 0}</dd>
                </div>
              </dl>
              {summary.message && <p className="mt-3 text-slate-300">{summary.message}</p>}
              {summary.auditId && (
                <p className="mt-1 text-xs text-slate-400">Auditointitunnus: {summary.auditId}</p>
              )}
            </div>
          )}
          {errorMessage && <p className="text-sm text-rose-300" role="alert">{errorMessage}</p>}
          {issues.length > 0 && (
            <div>
              <p className="text-sm font-semibold text-slate-200">Rivikohtaiset huomautukset</p>
              <ul className="mt-2 space-y-2 text-sm text-slate-300">
                {issues.map((issue, index) => (
                  <li key={`${issue.line ?? index}-${issue.code ?? index}`}>
                    <span className="font-mono text-slate-100">
                      {issue.line ? `Rivi ${issue.line}` : 'Rivi tuntematon'}:
                    </span>{' '}
                    {issue.code && <span className="text-slate-400">[{issue.code}] </span>}
                    {issue.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
};

export default AdminDiagnosisCodesPage;
