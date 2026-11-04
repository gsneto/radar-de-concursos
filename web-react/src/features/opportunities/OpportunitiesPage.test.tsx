import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { OpportunitiesPage } from './OpportunitiesPage';

function renderPage(initialEntry = '/oportunidades') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <OpportunitiesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const sampleOpportunity = {
  contest_id: 'c-1',
  competition_id: 'fgv-tjpe',
  contest_label: 'TJ-PE Analista 2026',
  role_id: 'r-1',
  role_name: 'Analista Judiciário - TI',
  scope: 'role:r-1',
  ultima_atualizacao: '2026-11-04T12:00:00Z',
  prontidao: {
    estado: 'candidatos_prontos_para_revisao',
    estado_label: 'Pronto para revisão',
    motivos: ['Propostas extraídas'],
  },
  si: { estado: 'explicito', motivo: 'Sistemas de Informação expresso' },
  indigenas: { estado: 'explicito_imediato', quantidade: 1 },
  localizacao: {
    prova: { text: 'Recife/PE', uf: 'PE', state: 'extraido_nao_revisado' },
    lotacao: { text: 'Recife/PE', uf: 'PE', state: 'extraido_nao_revisado' },
  },
  prazos: [
    {
      contest_id: 'c-1',
      grupo: 'inscricao_fim',
      grupo_label: 'Fim das inscrições',
      valor: '2026-11-20',
      dias_restantes: 16,
      urgencia: 'ate_30_dias',
      urgencia_label: 'Em até 30 dias',
      estado_temporal: 'futuro',
      estado_operacional: 'revalidado_na_fonte',
      estado_operacional_label: 'Revalidado na fonte',
    },
  ],
};

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('OpportunitiesPage', () => {
  it('lista oportunidades e permite filtrar por UF, busca e filtros avançados', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          total: 1,
          referencia: { hoje_local: '2026-11-04', fuso: 'America/Recife' },
          por_urgencia: {},
          por_prontidao: {},
          itens: [sampleOpportunity],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    renderPage();

    expect((await screen.findAllByText('TJ-PE Analista 2026')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Recife/PE').length).toBeGreaterThan(0);

    // Filtro avançado acessível via aria-expanded
    const advButton = screen.getByRole('button', { name: /avançados/i });
    expect(advButton).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(advButton);
    expect(advButton).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByLabelText(/situação documental/i)).toBeInTheDocument();

    // Aplicar busca
    const searchInput = screen.getByRole('searchbox', { name: /buscar oportunidades/i });
    fireEvent.change(searchInput, { target: { value: 'TJ-PE' } });
    fireEvent.submit(searchInput.closest('form')!);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /remover filtro busca: tj-pe/i })).toBeInTheDocument();
    });
  });

  it('mostra estado vazio quando nenhum item corresponde aos filtros', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            total: 0,
            referencia: { hoje_local: '2026-11-04', fuso: 'America/Recife' },
            por_urgencia: {},
            por_prontidao: {},
            itens: [],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    );

    renderPage('/oportunidades?uf=AC');

    expect(await screen.findByText('Nenhuma oportunidade com esses filtros')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /remover filtro uf: ac/i })).toBeInTheDocument();
  });

  it('exibe estado de erro quando a requisição falha', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ error: 'Falha ao consultar carteira' }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    renderPage();

    expect(await screen.findByText(/Falha ao consultar carteira/i)).toBeInTheDocument();
  });
});
