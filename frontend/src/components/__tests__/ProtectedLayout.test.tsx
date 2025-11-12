import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import ProtectedLayout from '../ProtectedLayout';
import { useAuth } from '../../contexts/AuthContext';

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);

const createSession = () => ({
  accessToken: 'token',
  tokenType: 'Bearer',
  expiresAt: Date.now() + 1000 * 60,
  username: 'Testikäyttäjä',
});

const renderWithRouter = (initialPath = '/start') => {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<ProtectedLayout />}>
          <Route path="/start" element={<p>Aloitussivun sisältö</p>} />
          <Route path="/patients" element={<p>Potilaslista sisältö</p>} />
          <Route path="/first-visit" element={<p>Ensikäynnin sisältö</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
};

describe('ProtectedLayout navigation', () => {
  beforeEach(() => {
    mockedUseAuth.mockReturnValue({
      initializing: false,
      isAuthenticated: true,
      logout: vi.fn(),
      session: createSession(),
    });
  });

  it('renders accessible navigation links for authenticated users', () => {
    renderWithRouter();

    const navigation = screen.getByRole('navigation', { name: /päävalikko/i });
    expect(navigation).toBeInTheDocument();

    const startLink = screen.getByRole('link', { name: 'Aloitussivu' });
    const patientsLink = screen.getByRole('link', { name: 'Potilaslista' });
    const firstVisitLink = screen.getByRole('link', { name: 'Ensikäynti' });

    expect(startLink).toHaveAttribute('href', '/start');
    expect(startLink).toHaveAttribute('aria-current', 'page');
    expect(patientsLink).toHaveAttribute('href', '/patients');
    expect(firstVisitLink).toHaveAttribute('href', '/first-visit');
  });

  it('allows navigating between main views using the links', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    await user.click(screen.getByRole('link', { name: 'Potilaslista' }));
    expect(screen.getByText('Potilaslista sisältö')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Potilaslista' })).toHaveAttribute('aria-current', 'page');

    await user.click(screen.getByRole('link', { name: 'Ensikäynti' }));
    expect(screen.getByText('Ensikäynnin sisältö')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ensikäynti' })).toHaveAttribute('aria-current', 'page');
  });
});
