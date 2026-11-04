import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DeadlinesPage } from './DeadlinesPage';

function renderPage(initialEntry = '/prazos') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <DeadlinesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const sampleDeadlines = [
  {
    contest_id: 'c-1',
    grupo: 'inscricao_fim',
    grupo_label: 'Fim das inscrições',
    escopo_rotulo: 'TJ-PE',
    valor: '2026-11-10',
    dias_restantes: 6,
    urgencia: 'ate_7_dias',
    urgencia_label: 'Em até 7 dias',
    estado_temporal: 'futuro',
    estado_operacional: 'revalidado_na_fonte',
    estado_operacional_label: 'Revalidado na fonte',
    documento: 'Edital nº 01/2026',
    pagina: 4,
    proxima_acao: 'Conferir cronograma',
    trecho: 'Inscrições até 10/11/2026',
  },
  {
    contest_id: 'c-2',
    grupo: 'data_prova',
    grupo_label: 'Data da prova',
    escopo_rotulo: 'MP-ES',
    valor: '2026-05-01',
    dias_restantes: -187,
    urgencia: 'vencido',
    urgencia_label: 'Vencido',
    estado_temporal: 'expirado',
    estado_operacional: 'passado_com_evidencia',
    estado_operacional_label: 'Passado com evidência',
    documento: 'Edital MP-ES',
    pagina: 12,
  },
];

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('DeadlinesPage', () => {
  it('renderiza abas de situação, KPIs e permite alternar entre Próximos e Vencidos', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            total: 2,
            limit: 500,
            has_more: false,
            referencia: { hoje_local: '2026-11-04', fuso: 'America/Recife' },
            por_urgencia: { ate_7_dias: 1, vencido: 1 },
            por_conflito: { conflito: 0 },
            itens: sampleDeadlines,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    );

    renderPage();

    expect((await screen.findAllByText('Fim das inscrições')).length).toBeGreaterThan(0);
    expect(screen.getByRole('region', { name: 'Resumo de prazos' })).toBeInTheDocument();
    expect(screen.getByRole('tablist', { name: 'Situação dos prazos' })).toBeInTheDocument();

    // Detalhes avançados
    const detailsBtn = screen.getByRole('button', { name: /mais detalhes/i });
    expect(detailsBtn).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(detailsBtn);
    expect(detailsBtn).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getAllByText(/Inscrições até 10\/11\/2026/).length).toBeGreaterThan(0);

    // Alternar para a aba Vencidos
    const vencidosTab = screen.getByRole('tab', { name: /vencidos/i });
    fireEvent.click(vencidosTab);
    expect(vencidosTab).toHaveAttribute('aria-selected', 'true');
    expect(screen.getAllByText('Data da prova').length).toBeGreaterThan(0);
  });

  it('exibe estado vazio quando a aba ativa não possui prazos', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            total: 0,
            limit: 500,
            has_more: false,
            referencia: { hoje_local: '2026-11-04', fuso: 'America/Recife' },
            por_urgencia: {},
            por_conflito: {},
            itens: [],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    );

    renderPage();

    expect(await screen.findByText('Nenhum prazo em "Próximos"')).toBeInTheDocument();
  });

  it('exibe estado de erro quando a API de calendário falha', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ error: 'Erro no calendário' }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    renderPage();

    expect(await screen.findByText(/Erro no calendário/i)).toBeInTheDocument();
  });
});
