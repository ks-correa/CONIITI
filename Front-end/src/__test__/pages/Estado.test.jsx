import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import Estado from '../../pages/Estado';


describe('Pagina de estado', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('muestra disponibilidad de servicios consultando healthchecks', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ status: 'ok' }),
    })));

    render(<Estado />);

    await waitFor(() => {
      expect(screen.getByText(/servicios disponibles/i)).toBeInTheDocument();
    });

    expect(fetch).toHaveBeenCalledTimes(8);
    expect(screen.getByText('Auth')).toBeInTheDocument();
    expect(screen.getByText('/auth/health')).toBeInTheDocument();
    expect(screen.getByText('Notifications')).toBeInTheDocument();
    expect(screen.getByText('Sorteos')).toBeInTheDocument();
    expect(screen.getByText(/latencia promedio/i)).toBeInTheDocument();
    expect(screen.getAllByText(/verificado/i)).toHaveLength(8);
  });

  it('muestra servicios no disponibles cuando falla la API de estado', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('Network error'))));

    render(<Estado />);

    await waitFor(() => {
      expect(screen.getAllByText(/no disponible/i).length).toBeGreaterThan(0);
    });

    expect(screen.getAllByText(/sin respuesta/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/network error/i).length).toBeGreaterThan(0);
  });
});
