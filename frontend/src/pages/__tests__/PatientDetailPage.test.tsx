import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import PatientDetailPage from '../PatientDetailPage';
import { useAuth } from '../../contexts/AuthContext';
import type { PatientDetail, VisitService } from '../../services/visitService';

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

const createServiceMock = (patient: PatientDetail): VisitService => {
  return {
    getPatient: vi.fn().mockResolvedValue(patient),
    getInitialVisit: vi.fn(),
    createInitialVisit: vi.fn(),
    getAppointment: vi.fn(),
    createPatient: vi.fn(),
  } as unknown as VisitService;
};

const createVisit = (id: number, reason: string) => ({
  id,
  visit_type: 'kontrolli',
  reason,
  status: 'valmis',
  location: 'Poliklinikka',
  started_at: `2024-05-${String(id).padStart(2, '0')}T08:00:00Z`,
  ended_at: `2024-05-${String(id).padStart(2, '0')}T09:00:00Z`,
  created_at: `2024-05-${String(id).padStart(2, '0')}T08:00:00Z`,
  updated_at: `2024-05-${String(id).padStart(2, '0')}T09:00:00Z`,
});

describe('PatientDetailPage', () => {
  beforeEach(() => {
    mockedUseAuth.mockReturnValue({
      initializing: false,
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      session: createSession(),
    });
  });

  it('näyttää ensimmäiset kolme käyntiä heti ja loput avautuvissa riveissä', async () => {
    const patient: PatientDetail = {
      id: 1,
      identifier: '010101-123N',
      first_name: 'Testi',
      last_name: 'Potilas',
      date_of_birth: '1980-01-01',
      sex: 'female',
      language: 'fi',
      status: 'active',
      contact_info: {
        phone: '+358401234567',
        email: 'test@example.com',
        address: { street: 'Testikatu 1', postal_code: '00100', city: 'Helsinki' },
      },
      consents: [],
      history: [],
      visits: [
        createVisit(1, 'Ensimmäinen käynti'),
        createVisit(2, 'Toinen käynti'),
        createVisit(3, 'Kolmas käynti'),
        createVisit(4, 'Neljäs käynti'),
        createVisit(5, 'Viides käynti'),
      ],
      visit_count: 5,
    };

    const serviceMock = createServiceMock(patient);

    render(
      <MemoryRouter initialEntries={["/patients/1"]}>
        <Routes>
          <Route path="/patients/:patientId" element={<PatientDetailPage service={serviceMock} />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(serviceMock.getPatient).toHaveBeenCalledWith(1, expect.any(Object)));

    expect(screen.getByText('Ensimmäinen käynti')).toBeInTheDocument();
    expect(screen.getByText('Toinen käynti')).toBeInTheDocument();
    expect(screen.getByText('Kolmas käynti')).toBeInTheDocument();
    expect(screen.queryByText('Neljäs käynti')).not.toBeInTheDocument();

    const user = userEvent.setup();
    const toggleButton = await screen.findByRole('button', { name: /Käynti #4/ });
    await user.click(toggleButton);

    expect(await screen.findByText('Neljäs käynti')).toBeInTheDocument();
  });
});
