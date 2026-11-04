import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { StudiesPage } from './StudiesPage';

function renderPage(initialEntry = '/estudos') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <StudiesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('StudiesPage', () => {
  it('renderiza indicadores de estudo, abas acessíveis e estados vazios honestos', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.startsWith('/api/estudos/painel')) {
          return new Response(
            JSON.stringify({
              total_segundos: 5400,
              semana_segundos: 1800,
              sessoes_concluidas: 3,
              revisoes_pendentes: 0,
              disciplinas: 1,
              conteudo: {
                topics: { done: 0, total: 0, pct: 0 },
                overall: { done: 0, total: 0, pct: 0 },
              },
              minutos_por_disciplina: [{ disciplina_id: 'd1', nome: 'Banco de Dados', minutos: 90 }],
              revisoes: [],
              sessao_aberta: null,
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.startsWith('/api/estudos/sessoes')) {
          return new Response(JSON.stringify([]), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        if (url.startsWith('/api/estudos/revisoes')) {
          return new Response(JSON.stringify([]), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        if (url.startsWith('/api/estudos/disciplinas')) {
          return new Response(
            JSON.stringify([{ id: 'd1', nome: 'Banco de Dados', peso: 1 }]),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.startsWith('/api/estudos/desempenho')) {
          return new Response(
            JSON.stringify({
              geral: { respondidas: 10, corretas: 8, pct: 80, basis: '8 de 10 questões' },
              por_disciplina: [],
              por_topico: [],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.startsWith('/api/estudos/flashcards/estatisticas')) {
          return new Response(
            JSON.stringify({ ativos: 5, vencidos: 1, novos: 2, basis: '5 ativos' }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        return new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } });
      }),
    );

    renderPage();

    expect(await screen.findByRole('region', { name: 'Indicadores de estudo' })).toBeInTheDocument();
    expect(screen.getByRole('tablist', { name: 'Seções de estudos' })).toBeInTheDocument();
    expect(screen.getAllByText('Banco de Dados').length).toBeGreaterThan(0);
    expect(screen.getByText('Nenhum tópico cadastrado')).toBeInTheDocument();

    // Navegar entre abas
    const questoesTab = screen.getByRole('tab', { name: 'Questões' });
    fireEvent.click(questoesTab);
    expect(questoesTab).toHaveAttribute('aria-selected', 'true');
  });

  it('exibe estado de erro quando o painel de estudos falha', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ error: 'Falha ao carregar estudos' }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    renderPage();

    expect(await screen.findByText(/Falha ao carregar estudos/i)).toBeInTheDocument();
  });
});
