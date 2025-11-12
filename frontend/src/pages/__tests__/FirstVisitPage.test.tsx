import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import FirstVisitPage from '../FirstVisitPage';
import { useAuth } from '../../contexts/AuthContext';
import { ApiError, InitialVisit, VisitService } from '../../services/visitService';

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

const createServiceMock = () => {
  return {
    getInitialVisit: vi.fn(),
    createInitialVisit: vi.fn(),
    getAppointment: vi.fn(),
    getPatient: vi.fn(),
    createPatient: vi.fn(),
  } as unknown as VisitService;
};

const defaultAppointment = {
  id: 1,
  patient_id: 10,
  provider_id: 5,
  service_type: 'initial',
  location: 'Huone 5',
  start_time: '2024-05-25T08:00:00Z',
  end_time: '2024-05-25T08:30:00Z',
  notes: 'Muistutus',
  status: 'scheduled',
};

const defaultPatient = {
  id: 10,
  identifier: '123456-789A',
  first_name: 'Anna',
  last_name: 'Esimerkki',
  date_of_birth: '1990-05-20',
  sex: 'female',
};

const renderPage = (serviceMock: VisitService, initialEntry = '/first-visit?appointmentId=1') => {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/first-visit" element={<FirstVisitPage service={serviceMock} />} />
      </Routes>
    </MemoryRouter>,
  );
};

describe('FirstVisitPage', () => {
  beforeEach(() => {
    mockedUseAuth.mockReturnValue({
      initializing: false,
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      session: createSession(),
    });
  });

  it('estää tallennuksen kun pakolliset kentät puuttuvat', async () => {
    const serviceMock = createServiceMock();
    serviceMock.getAppointment = vi.fn().mockResolvedValue(defaultAppointment);
    serviceMock.getPatient = vi.fn().mockResolvedValue(defaultPatient);
    serviceMock.createInitialVisit = vi.fn();

    renderPage(serviceMock);

    await waitFor(() => expect(serviceMock.getAppointment).toHaveBeenCalled());

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Tallenna ensikäynti' }));

    expect(await screen.findByText('Syy tuloon on pakollinen.')).toBeInTheDocument();
    expect(screen.getByText('Anamneesi on pakollinen.')).toBeInTheDocument();
    expect(screen.getByText('Statuskuvaus on pakollinen.')).toBeInTheDocument();
    expect(screen.getByText('Diagnoosikoodi on pakollinen.')).toBeInTheDocument();
    expect(screen.getByText('Yhteenveto on pakollinen.')).toBeInTheDocument();
    expect(serviceMock.createInitialVisit).not.toHaveBeenCalled();
  });

  it('näyttää virheilmoituksen kun ensikäynnin tallennus epäonnistuu', async () => {
    const serviceMock = createServiceMock();
    serviceMock.getAppointment = vi.fn().mockResolvedValue(defaultAppointment);
    serviceMock.getPatient = vi.fn().mockResolvedValue(defaultPatient);
    serviceMock.createInitialVisit = vi
      .fn()
      .mockRejectedValue(new ApiError('Virhe', 400, { detail: 'Tallennus epäonnistui' }));

    renderPage(serviceMock);

    await waitFor(() => expect(serviceMock.getAppointment).toHaveBeenCalled());

    const user = userEvent.setup();

    await user.type(screen.getByLabelText('Käynnin syy'), 'Migreeni');
    await user.type(screen.getByLabelText('Anamneesikuvaus'), 'Pitkäaikainen päänsärky.');
    await user.type(screen.getByLabelText('Statuskirjaus'), 'Yleistila hyvä.');
    await user.type(screen.getByLabelText('Diagnoosikoodi'), 'R51');
    await user.type(screen.getByLabelText('Yhteenvetomuistio'), 'Seuranta viikon kuluttua.');

    await user.click(screen.getByRole('button', { name: 'Tallenna ensikäynti' }));

    expect(await screen.findByText('Tallennus epäonnistui')).toBeInTheDocument();
    expect(serviceMock.createInitialVisit).toHaveBeenCalled();
  });

  it('luo uuden potilaan ennen ensikäynnin tallennusta', async () => {
    const serviceMock = createServiceMock();
    const appointmentWithoutPatient = { ...defaultAppointment, id: 55, patient_id: null };
    serviceMock.getAppointment = vi.fn().mockResolvedValue(appointmentWithoutPatient);
    serviceMock.getPatient = vi.fn();

    const createdPatient = { ...defaultPatient, id: 77 };
    serviceMock.createPatient = vi.fn().mockResolvedValue(createdPatient);

    const savedVisit: InitialVisit = {
      id: 99,
      patient_id: createdPatient.id,
      appointment_id: appointmentWithoutPatient.id,
      basics: {
        visit_type: 'initial',
        location: 'Huone 7',
        started_at: '2024-05-25T08:00:00Z',
        ended_at: '2024-05-25T08:30:00Z',
        attending_provider_id: 5,
        updated_at: '2024-05-25T08:30:00Z',
      },
      reason: { reason: 'Päänsärky', updated_at: '2024-05-25T08:30:00Z' },
      anamnesis: { content: 'Kuvaus', updated_at: '2024-05-25T08:30:00Z' },
      status: { content: 'Tila', updated_at: '2024-05-25T08:30:00Z' },
      diagnoses: {
        diagnoses: [{ code: 'R51', description: 'Päänsärky', is_primary: true }],
        updated_at: '2024-05-25T08:30:00Z',
      },
      orders: { orders: [] },
      summary: { content: 'Seuranta', updated_at: '2024-05-25T08:30:00Z' },
      created_at: '2024-05-25T08:30:00Z',
      updated_at: '2024-05-25T08:30:00Z',
    };
    serviceMock.createInitialVisit = vi.fn().mockResolvedValue(savedVisit);

    renderPage(serviceMock, '/first-visit?appointmentId=55');

    await waitFor(() => expect(serviceMock.getAppointment).toHaveBeenCalled());

    const user = userEvent.setup();

    await user.type(screen.getByLabelText('Henkilötunnus'), '010101-123N');
    await user.type(screen.getByLabelText('Etunimi'), 'Matti');
    await user.type(screen.getByLabelText('Sukunimi'), 'Meikäläinen');
    await user.type(screen.getByLabelText('Käynnin syy'), 'Päänsärky');
    await user.type(screen.getByLabelText('Anamneesikuvaus'), 'Potilas raportoi säännöllistä särkyä.');
    await user.type(screen.getByLabelText('Statuskirjaus'), 'Yleistila hyvä.');
    await user.type(screen.getByLabelText('Diagnoosikoodi'), 'R51');
    await user.type(screen.getByLabelText('Yhteenvetomuistio'), 'Seuranta viikon kuluttua.');

    await user.click(screen.getByRole('button', { name: 'Tallenna ensikäynti' }));

    await waitFor(() => expect(serviceMock.createInitialVisit).toHaveBeenCalled());

    expect(serviceMock.createPatient).toHaveBeenCalledWith(
      expect.objectContaining({
        identifier: '010101-123N',
        first_name: 'Matti',
        last_name: 'Meikäläinen',
      }),
      expect.any(Object),
    );

    expect(serviceMock.createInitialVisit).toHaveBeenCalledWith(
      expect.objectContaining({
        appointment_id: appointmentWithoutPatient.id,
        reason: { reason: 'Päänsärky' },
      }),
      expect.any(Object),
    );
  });
});
