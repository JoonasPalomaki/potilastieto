import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import PatientCreatePage from '../PatientCreatePage';
import { useAuth } from '../../contexts/AuthContext';
import type { VisitService } from '../../services/visitService';

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);

const createSession = () => ({
  accessToken: 'token',
  tokenType: 'Bearer',
  expiresAt: Date.now() + 60_000,
  username: 'Testikäyttäjä',
});

const LocationDisplay = () => {
  const location = useLocation();
  return <div data-testid="location-display">{`${location.pathname}${location.search}`}</div>;
};

const renderWithRouter = (ui: ReactNode, initialPath = '/patients/new') =>
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/patients/new" element={<>{ui}</>} />
        <Route path="/patients" element={<LocationDisplay />} />
        <Route path="/first-visit" element={<LocationDisplay />} />
      </Routes>
    </MemoryRouter>,
  );

describe('PatientCreatePage', () => {
  beforeEach(() => {
    mockedUseAuth.mockReturnValue({
      initializing: false,
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      session: createSession(),
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('tallentaa potilaan ja palaa listalle', async () => {
    vi.useFakeTimers();
    const createPatient = vi.fn().mockResolvedValue({ id: 77 });
    const service = { createPatient } as unknown as VisitService;

    renderWithRouter(<PatientCreatePage service={service} />);

    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Henkilötunnus'), '123456-999A');
    await user.type(screen.getByLabelText('Etunimi'), 'Testi');
    await user.type(screen.getByLabelText('Sukunimi'), 'Potilas');

    await user.click(screen.getByRole('button', { name: 'Tallenna potilas' }));

    await waitFor(() => expect(createPatient).toHaveBeenCalled());
    expect(await screen.findByText(/Potilas lisättiin onnistuneesti/i)).toBeInTheDocument();

    vi.runAllTimers();

    await waitFor(() =>
      expect(screen.getByTestId('location-display')).toHaveTextContent('/patients'),
    );
  });

  it('liittää uuden potilaan ensikäyntiin valintatilassa', async () => {
    vi.useFakeTimers();
    const createPatient = vi.fn().mockResolvedValue({ id: 55 });
    const service = { createPatient } as unknown as VisitService;

    const returnTo = encodeURIComponent('/first-visit?appointmentId=9');
    renderWithRouter(
      <PatientCreatePage service={service} />,
      `/patients/new?select=first-visit&returnTo=${returnTo}`,
    );

    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Henkilötunnus'), '123456-999A');
    await user.type(screen.getByLabelText('Etunimi'), 'Testi');
    await user.type(screen.getByLabelText('Sukunimi'), 'Potilas');

    await user.click(screen.getByRole('button', { name: 'Tallenna potilas' }));

    await waitFor(() => expect(createPatient).toHaveBeenCalled());
    vi.runAllTimers();

    await waitFor(() =>
      expect(screen.getByTestId('location-display')).toHaveTextContent(
        '/first-visit?appointmentId=9&patientId=55',
      ),
    );
  });

  it('näyttää validointivirheet eikä lähetä pyyntöä', async () => {
    const createPatient = vi.fn();
    const service = { createPatient } as unknown as VisitService;

    renderWithRouter(<PatientCreatePage service={service} />);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Tallenna potilas' }));

    expect(await screen.findByText('Henkilötunnus on pakollinen.')).toBeInTheDocument();
    expect(screen.getByText('Etunimi on pakollinen.')).toBeInTheDocument();
    expect(screen.getByText('Sukunimi on pakollinen.')).toBeInTheDocument();
    expect(createPatient).not.toHaveBeenCalled();
  });
});
