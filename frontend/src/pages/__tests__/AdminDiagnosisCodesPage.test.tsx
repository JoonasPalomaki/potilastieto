import type { ReactElement } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import AdminDiagnosisCodesPage from '../AdminDiagnosisCodesPage';
import { useAuth } from '../../contexts/AuthContext';
import { DiagnosisCodeError, type DiagnosisCodeService } from '../../services/diagnosisCodeService';

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);

const createSession = (role: string) => ({
  accessToken: 'token',
  tokenType: 'Bearer',
  expiresAt: Date.now() + 60_000,
  username: 'Ylläpitäjä',
  role,
});

const renderPage = (element: ReactElement) =>
  render(
    <MemoryRouter initialEntries={["/admin/diagnosis-codes"]}>
      <Routes>
        <Route path="/admin/diagnosis-codes" element={element} />
        <Route path="/start" element={<p>Aloitussivu</p>} />
      </Routes>
    </MemoryRouter>,
  );

describe('AdminDiagnosisCodesPage', () => {
  it('redirects non-admin users to the start page', () => {
    mockedUseAuth.mockReturnValue({
      initializing: false,
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      session: createSession('user'),
    });

    renderPage(<AdminDiagnosisCodesPage />);

    expect(screen.getByText('Aloitussivu')).toBeInTheDocument();
  });

  it('uploads CSV files and displays the summary when successful', async () => {
    const importCodes = vi.fn().mockResolvedValue({
      imported: 12,
      updated: 3,
      skipped: 1,
      auditId: 'AUD-123',
      message: 'Tuonti onnistui.',
      issues: [{ line: 2, code: 'A00', message: 'Korvattiin olemassa oleva kuvaus' }],
    });
    const service = { importCodes } as unknown as DiagnosisCodeService;
    mockedUseAuth.mockReturnValue({
      initializing: false,
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      session: createSession('admin'),
    });

    renderPage(<AdminDiagnosisCodesPage service={service} />);
    const user = userEvent.setup();
    const fileInput = screen.getByLabelText(/valitse csv-tiedosto/i);
    const file = new File(['code,description'], 'codes.csv', { type: 'text/csv' });

    await user.upload(fileInput, file);
    await user.click(screen.getByRole('button', { name: /lataa diagnoosikoodit/i }));

    await waitFor(() => {
      expect(importCodes).toHaveBeenCalledWith({ file, authorization: 'Bearer token' });
    });

    expect(await screen.findByText(/tuonnin yhteenveto/i)).toBeInTheDocument();
    expect(screen.getByText(/auditointitunnus/i)).toHaveTextContent('AUD-123');
    expect(screen.getByText(/rivi 2/i)).toBeInTheDocument();
  });

  it('shows validation errors when the upload fails', async () => {
    const importCodes = vi
      .fn()
      .mockRejectedValue(new DiagnosisCodeError('CSV-tiedostossa oli virheitä', 422, null, [
        { line: 5, code: 'B01', message: 'Puuttuva kuvaus' },
      ]));
    const service = { importCodes } as unknown as DiagnosisCodeService;

    mockedUseAuth.mockReturnValue({
      initializing: false,
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      session: createSession('admin'),
    });

    renderPage(<AdminDiagnosisCodesPage service={service} />);
    const user = userEvent.setup();
    const fileInput = screen.getByLabelText(/valitse csv-tiedosto/i);
    const file = new File(['invalid'], 'codes.csv', { type: 'text/csv' });

    await user.upload(fileInput, file);
    await user.click(screen.getByRole('button', { name: /lataa diagnoosikoodit/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('CSV-tiedostossa oli virheitä');
    expect(screen.getByText(/rivi 5/i)).toBeInTheDocument();
  });
});
