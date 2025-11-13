import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';

import PatientsPage from '../PatientsPage';
import { useAuth } from '../../contexts/AuthContext';

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

describe('PatientsPage selection mode', () => {
  beforeEach(() => {
    mockedUseAuth.mockReturnValue({
      initializing: false,
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      session: createSession(),
    });
  });

  it('palauttaa valitun potilaan ensikäynnille', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        items: [
          { id: 42, identifier: '123456-9999', name: 'Test Potilas', status: 'aktiivinen' },
        ],
      }),
    } as unknown as Response);

    render(
      <MemoryRouter initialEntries={["/patients?select=first-visit&returnTo=%2Ffirst-visit%3FappointmentId%3D9"]}>
        <Routes>
          <Route path="/patients" element={<>
            <PatientsPage />
            <LocationDisplay />
          </>} />
          <Route path="/first-visit" element={<LocationDisplay />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());

    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Valitse' }));

    expect(await screen.findByTestId('location-display')).toHaveTextContent(
      '/first-visit?appointmentId=9&patientId=42',
    );

    fetchSpy.mockRestore();
  });

  it('avaa potilaan luontinäkymän painikkeesta', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [] }),
    } as unknown as Response);

    render(
      <MemoryRouter initialEntries={["/patients"]}>
        <Routes>
          <Route
            path="/patients"
            element={
              <>
                <PatientsPage />
                <LocationDisplay />
              </>
            }
          />
          <Route path="/patients/new" element={<LocationDisplay />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());

    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Lisää potilas' }));

    expect(await screen.findByTestId('location-display')).toHaveTextContent('/patients/new');

    fetchSpy.mockRestore();
  });
});
