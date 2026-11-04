import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsPage } from './SettingsPage';

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe('SettingsPage', () => {
  it('carrega as preferências atuais (Paulo Afonso/BA) e envia atualização via POST /api/preferencias', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url === '/api/preferencias' && (!init || !init.method || init.method === 'GET')) {
        return new Response(
          JSON.stringify({
            reference_municipio: 'Paulo Afonso',
            reference_uf: 'BA',
            interest_states: ['BA', 'PE'],
            practical_distance_km: 300,
            priority: 'equilibrado',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        );
      }
      if (url === '/api/preferencias' && init?.method === 'POST') {
        return new Response(init.body as BodyInit, {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response('{}', { status: 200 });
    });
    vi.stubGlobal('fetch', fetchMock);

    renderPage();

    const municipioInput = await screen.findByLabelText(/município de referência/i);
    expect(municipioInput).toHaveValue('Paulo Afonso');
    expect(screen.getByLabelText(/uf de referência/i)).toHaveValue('BA');
    expect(screen.getByLabelText(/estados de interesse/i)).toHaveValue('BA, PE');
    expect(screen.getByLabelText(/distância prática/i)).toHaveValue(300);

    fireEvent.click(screen.getByRole('button', { name: /salvar preferências/i }));

    await waitFor(() => {
      expect(screen.getByText('Preferências salvas no arquivo local.')).toBeInTheDocument();
    });

    const postCall = fetchMock.mock.calls.find(
      ([callUrl, init]) => callUrl === '/api/preferencias' && init?.method === 'POST',
    );
    expect(postCall).toBeTruthy();
    const sent = JSON.parse(String(postCall![1]?.body));
    expect(sent).toEqual({
      reference_municipio: 'Paulo Afonso',
      reference_uf: 'BA',
      interest_states: ['BA', 'PE'],
      practical_distance_km: 300,
      priority: 'equilibrado',
    });
  });

  it('alterna preferência de menu lateral recolhido no localStorage', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            reference_municipio: null,
            reference_uf: null,
            interest_states: ['BA', 'PE'],
            practical_distance_km: 300,
            priority: 'equilibrado',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    );

    renderPage();

    const checkbox = await screen.findByRole('checkbox', { name: /menu lateral recolhido/i });
    expect(checkbox).not.toBeChecked();
    fireEvent.click(checkbox);
    expect(localStorage.getItem('radar.sidebar.collapsed')).toBe('1');
  });

  it('exibe estado de erro quando a leitura de preferências falha', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ error: 'Configuração inacessível' }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    renderPage();

    expect(await screen.findByText(/Configuração inacessível/i)).toBeInTheDocument();
  });
});
